"""标书多轮精修 API 路由 — SSE 流式输出 3 轮闭合精修过程。"""
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import require_editor
from ..db.database import get_db
from ..models.user import User
from ..services.refinement_service import RefinementService
from ..utils.sse import sse_response

router = APIRouter(prefix="/api/refine", tags=["标书精修"])


# ── 请求体 ───────────────────────────────────────────────────────────

class RefineChapterRequest(BaseModel):
    """多轮精修请求"""
    project_id: str = Field(..., description="项目 ID")
    chapter: dict = Field(..., description="章节信息 {id, title, description, ...}")
    chapter_rating_focus: str = Field("", description="本章需回答的核心评分问题")
    chapter_role: str = Field("", description="本章职责定位")
    adjacent_boundary: str = Field("", description="与相邻章节的去重边界")
    parent_chapters: list | None = Field(None, description="上级章节列表")
    sibling_chapters: list | None = Field(None, description="同级章节列表")
    project_overview: str = Field("", description="项目概述")
    tech_requirements: str = Field("", description="技术评分要求")
    project_response_matrix: str = Field("", description="项目响应矩阵")
    knowledge_context: str = Field("", description="知识库上下文（可选，不传则自动检索）")
    provider_config_id: str | None = Field(None, description="Provider 配置 ID")
    model_name: str | None = Field(None, description="模型名称")
    max_rounds: int = Field(3, ge=1, le=5, description="最大精修轮数（1-5，默认 3）")


# ── SSE 端点 ─────────────────────────────────────────────────────────

@router.post("/chapter")
async def refine_chapter(
    request: RefineChapterRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """多轮精修章节内容（SSE 流）。

    管道：生成 → 审查 → 自动修复 → 再审查，最多 3 轮闭合。

    SSE 事件类型：
    - round_start: 每轮开始
    - progress: 进度提示
    - round_issues: 每轮审查发现的问题列表
    - round_complete: 每轮结束（含问题统计）
    - error: 异常中断
    - refine_complete: 整体完成（含最终内容和质量分）
    """
    # ── 校验 project_id ──
    try:
        project_uuid = uuid.UUID(request.project_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的项目 ID 格式",
        )

    service = RefinementService(db)

    async def generate():
        try:
            async for event in service.execute_refinement_pipeline(
                project_id=project_uuid,
                chapter=request.chapter,
                chapter_rating_focus=request.chapter_rating_focus,
                chapter_role=request.chapter_role,
                adjacent_boundary=request.adjacent_boundary,
                parent_chapters=request.parent_chapters,
                sibling_chapters=request.sibling_chapters,
                project_overview=request.project_overview,
                tech_requirements=request.tech_requirements,
                project_response_matrix=request.project_response_matrix,
                knowledge_context=request.knowledge_context,
                provider_config_id=request.provider_config_id,
                model_name=request.model_name,
                max_rounds=request.max_rounds,
                user_id=current_user.id if current_user else None,
            ):
                event_type = event.get("type", "")
                event_data = event.get("data", {})

                if event_type == "error":
                    yield f"event: error\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                    return

                yield (
                    f"event: {event_type}\n"
                    f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                )

            yield "data: [DONE]\n\n"

        except ValueError as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': f'精修流程异常: {str(e)}'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return sse_response(generate())
