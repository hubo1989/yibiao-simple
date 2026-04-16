"""导出格式模板 API 路由

提供 CRUD 接口和 AI 格式提取接口。
"""

import json
import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import require_editor
from ..db.database import get_db
from ..models.export_template import ExportTemplate
from ..models.project import Project, project_members
from ..models.schemas import (
    ExportTemplateCreate,
    ExportTemplateResponse,
    ExportTemplateUpdate,
    ExtractFormatRequest,
)
from ..models.user import User
from ..services.openai_service import OpenAIService
from ..services.prompt_service import PromptService

router = APIRouter(prefix="/api/export-templates", tags=["导出格式模板"])


# ============ 辅助函数 ============

def _to_response(tmpl: ExportTemplate) -> ExportTemplateResponse:
    return ExportTemplateResponse(
        id=str(tmpl.id),
        name=tmpl.name,
        description=tmpl.description,
        is_builtin=tmpl.is_builtin,
        created_by=str(tmpl.created_by) if tmpl.created_by else None,
        format_config=tmpl.format_config,
        source_file_path=tmpl.source_file_path,
        created_at=tmpl.created_at.isoformat(),
        updated_at=tmpl.updated_at.isoformat(),
    )


# ============ CRUD 接口 ============

@router.get("", response_model=List[ExportTemplateResponse])
async def list_export_templates(
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """列出所有导出格式模板（内置 + 当前用户创建）"""
    result = await db.execute(
        select(ExportTemplate).order_by(
            ExportTemplate.is_builtin.desc(),
            ExportTemplate.created_at.asc(),
        )
    )
    templates = result.scalars().all()
    return [_to_response(t) for t in templates]


@router.get("/{template_id}", response_model=ExportTemplateResponse)
async def get_export_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取单个导出格式模板详情"""
    tmpl = await db.get(ExportTemplate, template_id)
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    return _to_response(tmpl)


@router.post("", response_model=ExportTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_export_template(
    body: ExportTemplateCreate,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """新建导出格式模板（is_builtin=False）"""
    tmpl = ExportTemplate(
        name=body.name,
        description=body.description,
        is_builtin=False,
        created_by=current_user.id,
        format_config=body.format_config,
    )
    db.add(tmpl)
    await db.flush()
    await db.refresh(tmpl)
    return _to_response(tmpl)


@router.put("/{template_id}", response_model=ExportTemplateResponse)
async def update_export_template(
    template_id: uuid.UUID,
    body: ExportTemplateUpdate,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """更新导出格式模板（内置模板只能改 name/description，不能改 format_config）"""
    tmpl = await db.get(ExportTemplate, template_id)
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")

    if body.name is not None:
        tmpl.name = body.name
    if body.description is not None:
        tmpl.description = body.description

    if body.format_config is not None:
        if tmpl.is_builtin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="内置模板的 format_config 不可修改",
            )
        tmpl.format_config = body.format_config

    await db.flush()
    await db.refresh(tmpl)
    return _to_response(tmpl)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """删除导出格式模板（内置模板不可删除）"""
    tmpl = await db.get(ExportTemplate, template_id)
    if not tmpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    if tmpl.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="内置模板不可删除",
        )
    await db.delete(tmpl)
    await db.flush()


# ============ P3: AI 格式提取接口 ============

@router.post("/extract-from-document")
async def extract_format_from_document(
    request: ExtractFormatRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    从招标文件中 AI 提取格式要求，返回 format_config JSON。

    不自动保存，前端确认后可调用 POST /api/export-templates 创建模板。
    """
    # 获取文档内容
    file_content: str | None = request.file_content

    if not file_content and request.project_id:
        try:
            project_uuid = uuid.UUID(request.project_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的项目ID格式") from exc

        result = await db.execute(select(Project).where(Project.id == project_uuid))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        file_content = project.file_content

    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须提供 file_content 或有文件内容的 project_id",
        )

    # 获取提示词
    prompt_service = PromptService(db)
    try:
        prompt, _ = await prompt_service.get_prompt("extract_format_requirements")
    except ValueError:
        # 使用内置 fallback prompt
        prompt = _EXTRACT_FORMAT_FALLBACK_PROMPT

    system_prompt, user_template = PromptService.split_prompt(prompt)
    user_prompt = prompt_service.render_prompt(
        user_template, {"file_content": file_content}
    )

    # 调用 AI
    project_uuid_for_ai = None
    if request.project_id:
        try:
            project_uuid_for_ai = uuid.UUID(request.project_id)
        except ValueError:
            pass

    openai_service = OpenAIService(db=db, project_id=project_uuid_for_ai)
    if request.provider_config_id:
        configured = await openai_service.use_config_by_id(request.provider_config_id)
        if not configured:
            raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
    else:
        await openai_service._ensure_initialized()

    if not openai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 OpenAI API 密钥")

    if request.model_name:
        openai_service.set_model(request.model_name)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    full_response = ""
    async for chunk in openai_service.stream_chat_completion(messages, temperature=0.1):
        full_response += chunk

    # 解析 JSON
    format_config = _parse_json_response(full_response)

    return {
        "success": True,
        "format_config": format_config,
        "raw_response": full_response,
    }


def _parse_json_response(text: str) -> dict:
    """从 AI 返回中提取 JSON 对象"""
    import re

    # 尝试直接解析
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 提取 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 提取第一个 { ... }
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"AI 返回内容无法解析为 JSON，原始内容：{text[:500]}",
    )


# ============ 内置 Fallback Prompt ============

_EXTRACT_FORMAT_FALLBACK_PROMPT = """# 系统指令

你是一名专业的投标文件格式分析专家。从招标文件中提取文档格式要求，输出严格的 JSON 格式。

## 输出格式
输出一个符合以下结构的 JSON 对象，所有字段均为可选，未提及则使用 null：

```json
{
  "font": {
    "body_font": "仿宋",
    "body_size": 12,
    "h1_font": "黑体",
    "h1_size": 16,
    "h2_font": "黑体",
    "h2_size": 14,
    "h3_font": "黑体",
    "h3_size": 12,
    "table_font": "仿宋",
    "table_size": 10.5
  },
  "spacing": {
    "line_spacing_pt": 28,
    "first_indent_chars": 2,
    "h1_before": 24,
    "h1_after": 12,
    "h2_before": 12,
    "h2_after": 6,
    "h3_before": 6,
    "h3_after": 3
  },
  "margin": {
    "top": 37,
    "bottom": 35,
    "left": 28,
    "right": 26
  },
  "page": {
    "page_number_format": "第X页 共Y页",
    "header_text": "{project_name}",
    "header_position": "center"
  },
  "cover": {
    "show_cover": true,
    "title_font": "黑体",
    "title_size": 22,
    "subtitle": "投标技术文件",
    "show_bidder_info": true,
    "cover_fields": ["投标人", "编制日期"]
  },
  "toc": {
    "show_toc": true,
    "toc_title": "目  录",
    "toc_levels": 3
  }
}
```

## 提取规则
1. 字体名称保留中文原文（如"仿宋"、"黑体"、"宋体"）
2. 字号转换为磅值（小四=12pt，四号=14pt，三号=16pt，小三=15pt，小二=18pt，二号=22pt）
3. 页边距单位为毫米
4. 行间距单位为磅
5. 若文件未明确规定某项，则沿用字段默认值，不要输出 null
6. 只输出 JSON，不要输出任何解释文字

---

# 用户输入

请分析以下招标文件内容，提取文档格式要求：

{{file_content}}"""
