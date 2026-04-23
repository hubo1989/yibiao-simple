"""全文一致性校验 API 路由

提供独立的一致性校验端点：
- POST /api/consistency/check      执行校验（调用 AI）
- GET  /api/consistency/{project_id}/latest   最近一次校验结果
- GET  /api/consistency/{project_id}/history  校验历史列表
"""
import uuid
import json
import re
import logging
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.user import User
from ..models.project import Project, project_members
from ..models.chapter import Chapter
from ..models.consistency_result import (
    ConsistencyResult,
    ConsistencySeverity,
    ConsistencyCategory,
)
from ..services.openai_service import OpenAIService
from ..auth.dependencies import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/consistency", tags=["一致性校验"])


# ==================== Pydantic 模型 ====================

class ConsistencyCheckRequest(BaseModel):
    """一致性校验请求"""
    project_id: str = Field(..., description="项目ID")
    provider_config_id: Optional[str] = Field(None, description="指定 Provider 配置ID（可选）")
    model_name: Optional[str] = Field(None, description="指定模型名称（可选）")


class ContradictionLocation(BaseModel):
    chapter_id: Optional[str] = None
    chapter_title: str = ""
    chapter_number: str = ""
    text: str = ""


class ConsistencyIssue(BaseModel):
    """单个一致性问题"""
    severity: str = Field(..., description="error（严重矛盾）或 warning（可能不一致）或 info（轻微差异）")
    category: str = Field(..., description="data / terminology / timeline / commitment / scope")
    description: str = Field(..., description="问题描述")
    chapter_a: str = Field("", description="章节A编号标题")
    chapter_b: str = Field("", description="章节B编号标题")
    chapter_id_a: Optional[str] = None
    chapter_id_b: Optional[str] = None
    detail_a: str = Field("", description="章节A关键内容")
    detail_b: str = Field("", description="章节B关键内容")
    suggestion: str = Field("", description="修改建议")


class ConsistencyCheckResult(BaseModel):
    """一致性校验结果"""
    status: str = "completed"
    total_chapters_checked: int = 0
    issues: List[ConsistencyIssue] = Field(default_factory=list)
    summary: str = ""
    overall_consistency: str = "consistent"
    contradiction_count: int = 0
    critical_count: int = 0
    created_at: Optional[str] = None
    check_id: Optional[str] = None


class ConsistencyHistoryItem(BaseModel):
    """校验历史条目"""
    id: str
    project_id: str
    summary: str
    overall_consistency: str
    contradiction_count: int
    critical_count: int
    created_at: str


# ==================== 辅助函数 ====================

async def _get_project_for_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Project:
    """验证用户是项目成员并返回项目"""
    from sqlalchemy import exists

    member_check = await db.execute(
        select(
            exists().where(
                and_(
                    project_members.c.project_id == project_id,
                    project_members.c.user_id == user_id,
                )
            )
        )
    )
    if not member_check.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或您没有访问权限",
        )

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    return project


def _build_chapter_summary(chapter: Chapter) -> str:
    """构建章节摘要：前 500 字 + 包含数字/日期/金额的句子"""
    content = chapter.content or ""
    if not content.strip():
        return ""

    # 取前 500 字
    head = content[:500]

    # 提取含数字/日期/金额的句子（超出前500字的部分）
    remaining = content[500:]
    numeric_sentences: List[str] = []
    # 按句号、换行分句
    for sentence in re.split(r"[。\n；;]", remaining):
        sentence = sentence.strip()
        if not sentence:
            continue
        # 匹配数字、百分比、金额符号、日期关键词
        if re.search(r"\d|元|万|亿|%|天|月|年|人|名|台|套|项|个", sentence):
            numeric_sentences.append(sentence)
        if len(numeric_sentences) >= 20:  # 最多取 20 句
            break

    parts = [head]
    if numeric_sentences:
        parts.append("……（关键数据句）：" + "；".join(numeric_sentences[:10]))

    return "\n".join(parts)


def _parse_consistency_json(full_content: str) -> dict:
    """解析 AI 返回的一致性 JSON，带容错处理"""
    json_content = full_content.strip()

    # 去掉 markdown 代码块标记
    if json_content.startswith("```"):
        json_content = re.sub(r'^```(?:json)?\s*\n?', '', json_content)
        json_content = re.sub(r'\n?```\s*$', '', json_content)
        json_content = json_content.strip()

    # 提取 JSON 对象
    if not json_content.startswith('{'):
        start = json_content.find('{')
        end = json_content.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_content = json_content[start:end + 1]

    # 修复中文引号和冒号
    json_content = json_content.replace('\u201c', '"').replace('\u201d', '"')
    json_content = json_content.replace('：', ':')

    return json.loads(json_content)


def _result_to_issues(result_data: dict, chapter_id_map: dict) -> List[ConsistencyIssue]:
    """将 AI 返回的 contradictions 转换为 ConsistencyIssue 列表"""
    issues = []
    for c in result_data.get("contradictions", []):
        severity = c.get("severity", "info")
        # 将 AI 返回的 critical 映射为 error（前端设计用 error/warning/info）
        if severity == "critical":
            severity = "error"

        chapter_a_ref = c.get("chapter_a", "")
        chapter_b_ref = c.get("chapter_b", "")

        # 从 "编号 标题" 格式中提取编号
        def extract_number(ref: str) -> str:
            parts = ref.split(" ", 1)
            return parts[0] if parts else ref

        chapter_id_a = chapter_id_map.get(extract_number(chapter_a_ref))
        chapter_id_b = chapter_id_map.get(extract_number(chapter_b_ref))

        issues.append(ConsistencyIssue(
            severity=severity,
            category=c.get("category", "data"),
            description=c.get("description", ""),
            chapter_a=chapter_a_ref,
            chapter_b=chapter_b_ref,
            chapter_id_a=chapter_id_a,
            chapter_id_b=chapter_id_b,
            detail_a=c.get("detail_a", ""),
            detail_b=c.get("detail_b", ""),
            suggestion=c.get("suggestion", ""),
        ))
    return issues


# ==================== 路由处理 ====================

@router.post("/check", response_model=ConsistencyCheckResult)
async def run_consistency_check(
    request: ConsistencyCheckRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    执行全文一致性校验

    1. 加载项目所有章节及内容
    2. 提取每章关键摘要（前500字 + 数字/日期句子）
    3. 调用 AI 交叉检查，检测矛盾
    4. 保存并返回矛盾列表
    """
    try:
        project_uuid = uuid.UUID(request.project_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的项目ID格式")

    project = await _get_project_for_member(project_uuid, current_user.id, db)

    # 加载所有有内容的章节
    result = await db.execute(
        select(Chapter)
        .where(
            and_(
                Chapter.project_id == project_uuid,
                Chapter.content.isnot(None),
                Chapter.content != "",
            )
        )
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()

    if len(chapters) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要 2 个有内容的章节才能进行一致性校验",
        )

    # 构建章节摘要
    chapter_summaries = []
    chapter_id_map: dict = {}  # chapter_number -> str(chapter.id)
    for ch in chapters:
        summary = _build_chapter_summary(ch)
        if not summary.strip():
            continue
        chapter_summaries.append({
            "chapter_number": ch.chapter_number,
            "title": ch.title,
            "summary": summary,
            "chapter_id": str(ch.id),
        })
        chapter_id_map[ch.chapter_number] = str(ch.id)

    if len(chapter_summaries) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="有效内容章节不足 2 个，无法进行一致性校验",
        )

    # 初始化 AI 服务
    openai_service = OpenAIService(db=db, project_id=project_uuid)
    if request.provider_config_id:
        configured = await openai_service.use_config_by_id(request.provider_config_id)
        if not configured:
            raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
    else:
        await openai_service._ensure_initialized()

    if not openai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 API 密钥")

    if request.model_name:
        openai_service.set_model(request.model_name)

    logger.info(f"开始一致性校验，项目 {project_uuid}，章节数 {len(chapter_summaries)}")

    # 调用 AI
    full_content = ""
    async for chunk in openai_service.check_consistency(
        chapter_summaries=chapter_summaries,
        project_overview=project.project_overview,
        tech_requirements=project.tech_requirements,
    ):
        full_content += chunk

    if not full_content.strip():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 返回空内容，请重试",
        )

    # 解析 JSON
    try:
        result_data = _parse_consistency_json(full_content)
    except json.JSONDecodeError as e:
        logger.error(f"一致性校验 JSON 解析失败: {e}\n内容: {full_content[:500]}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 返回结果格式无效，请重试",
        )

    issues = _result_to_issues(result_data, chapter_id_map)
    contradiction_count = len(issues)
    critical_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")

    # 持久化到 consistency_results 表
    db_record = ConsistencyResult(
        project_id=project_uuid,
        contradictions=json.dumps(
            [i.model_dump() for i in issues], ensure_ascii=False
        ),
        summary=result_data.get("summary", ""),
        overall_consistency=result_data.get("overall_consistency", "consistent"),
        contradiction_count=contradiction_count,
        critical_count=critical_count,
        warning_count=warning_count,
    )
    db.add(db_record)
    await db.flush()
    await db.refresh(db_record)
    await db.commit()

    logger.info(
        f"一致性校验完成：项目 {project_uuid}，"
        f"矛盾 {contradiction_count} 个（严重 {critical_count} 个）"
    )

    summary_text = result_data.get("summary", "")
    if not summary_text:
        summary_text = (
            f"共检查 {len(chapter_summaries)} 个章节，"
            f"发现 {contradiction_count} 个矛盾点"
            + (f"（{critical_count} 个严重）" if critical_count else "")
        )

    return ConsistencyCheckResult(
        status="completed",
        total_chapters_checked=len(chapter_summaries),
        issues=issues,
        summary=summary_text,
        overall_consistency=result_data.get("overall_consistency", "consistent"),
        contradiction_count=contradiction_count,
        critical_count=critical_count,
        created_at=db_record.created_at.isoformat(),
        check_id=str(db_record.id),
    )


@router.get("/{project_id}/latest", response_model=ConsistencyCheckResult)
async def get_latest_consistency_result(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取项目最近一次一致性校验结果"""
    await _get_project_for_member(project_id, current_user.id, db)

    result = await db.execute(
        select(ConsistencyResult)
        .where(ConsistencyResult.project_id == project_id)
        .order_by(ConsistencyResult.created_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该项目尚未进行一致性校验",
        )

    try:
        raw_issues = json.loads(record.contradictions)
    except json.JSONDecodeError:
        raw_issues = []

    issues = [ConsistencyIssue(**i) for i in raw_issues]

    return ConsistencyCheckResult(
        status="completed",
        total_chapters_checked=0,  # 历史记录中未存储章节数，置 0
        issues=issues,
        summary=record.summary or "",
        overall_consistency=record.overall_consistency,
        contradiction_count=record.contradiction_count,
        critical_count=record.critical_count,
        created_at=record.created_at.isoformat(),
        check_id=str(record.id),
    )


@router.get("/{project_id}/history", response_model=List[ConsistencyHistoryItem])
async def get_consistency_history(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取项目一致性校验历史（最近 10 次）"""
    await _get_project_for_member(project_id, current_user.id, db)

    result = await db.execute(
        select(ConsistencyResult)
        .where(ConsistencyResult.project_id == project_id)
        .order_by(ConsistencyResult.created_at.desc())
        .limit(10)
    )
    records = result.scalars().all()

    return [
        ConsistencyHistoryItem(
            id=str(r.id),
            project_id=str(r.project_id),
            summary=r.summary or "",
            overall_consistency=r.overall_consistency,
            contradiction_count=r.contradiction_count,
            critical_count=r.critical_count,
            created_at=r.created_at.isoformat(),
        )
        for r in records
    ]
