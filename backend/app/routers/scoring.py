"""评分标准相关 API 路由"""

import uuid
import json
import logging
import re
from typing import Annotated, Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project, project_members, ProjectMemberRole
from ..models.chapter import Chapter
from ..models.scoring import ScoringCriteria
from ..models.user import User
from ..db.database import get_db
from ..services.openai_service import OpenAIService
from ..services.prompt_service import PromptService
from ..auth.dependencies import require_editor

router = APIRouter(prefix="/api/scoring", tags=["评分标准"])


# ============ Pydantic Schema ============


class ScoringCriteriaItem(BaseModel):
    id: str
    item_id: str | None = None
    category: str | None = None
    item: str
    max_score: float | None = None
    scoring_rule: str | None = None
    keywords: list[str] = []
    source_text: str | None = None
    bound_chapter_id: str | None = None


class ScoringExtractRequest(BaseModel):
    project_id: str
    model_name: str | None = None
    provider_config_id: str | None = None


class ScoringUpdateRequest(BaseModel):
    category: str | None = None
    item: str | None = None
    max_score: float | None = None
    scoring_rule: str | None = None
    keywords: list[str] | None = None
    bound_chapter_id: str | None = None


class ScoringCoverageResponse(BaseModel):
    total: int
    bound: int
    unbound: int
    bound_score: float
    unbound_score: float
    total_score: float
    coverage_rate: float
    high_score_unbound: list[ScoringCriteriaItem]


# ============ 权限辅助 ============


async def _verify_project_access(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Project:
    result = await db.execute(
        select(project_members.c.role).where(
            and_(
                project_members.c.project_id == project_id,
                project_members.c.user_id == user_id,
            )
        )
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=404, detail="项目不存在或您没有访问权限")

    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


def _to_item(sc: ScoringCriteria) -> ScoringCriteriaItem:
    return ScoringCriteriaItem(
        id=str(sc.id),
        item_id=sc.item_id or "",
        category=sc.category,
        item=sc.item,
        max_score=sc.max_score,
        scoring_rule=sc.scoring_rule,
        keywords=sc.keywords or [],
        source_text=sc.source_text,
        bound_chapter_id=str(sc.bound_chapter_id) if sc.bound_chapter_id else None,
    )


# ============ 路由 ============


@router.post("/extract")
async def extract_scoring_criteria(
    request: ScoringExtractRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """从项目招标文档中 AI 提取评分标准，保存到数据库"""
    try:
        project_uuid = uuid.UUID(request.project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的项目ID格式")

    project = await _verify_project_access(project_uuid, current_user.id, db)

    if not project.file_content:
        raise HTTPException(status_code=400, detail="项目尚未上传招标文件")

    # 调用 AI 提取
    openai_service = OpenAIService(db=db, project_id=project_uuid)
    if request.provider_config_id:
        configured = await openai_service.use_config_by_id(request.provider_config_id)
        if not configured:
            raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
    else:
        await openai_service._ensure_initialized()

    if not openai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 AI API 密钥")

    if request.model_name:
        openai_service.set_model(request.model_name)

    # 获取 prompt
    prompt_service = PromptService(db)
    prompt, _ = await prompt_service.get_prompt("extract_scoring_criteria", project_uuid)
    system_prompt, user_template = PromptService.split_prompt(prompt)

    user_prompt = prompt_service.render_prompt(
        user_template,
        {"file_content": project.file_content[:30000]},  # 截断避免超长
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    raw = await openai_service._collect_stream_text(messages, temperature=0.2)

    # 解析 JSON
    raw = raw.strip()
    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r',\s*([}\]])', r'\1', raw)
        last = max(cleaned.rfind(']'), cleaned.rfind('}'))
        if last > 0:
            cleaned = cleaned[:last + 1]
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"评分标准 JSON 解析失败: {e}\n原文: {raw[:500]}")
            raise HTTPException(status_code=500, detail="AI 返回格式异常，请重试")

    criteria_list = data.get("scoring_criteria", [])
    if not isinstance(criteria_list, list):
        raise HTTPException(status_code=500, detail="AI 返回格式异常：scoring_criteria 不是列表")

    # 删除旧评分标准，重新保存
    await db.execute(
        delete(ScoringCriteria).where(ScoringCriteria.project_id == project_uuid)
    )

    created = []
    for idx, c in enumerate(criteria_list):
        if not isinstance(c, dict):
            continue
        sc = ScoringCriteria(
            project_id=project_uuid,
            item_id=c.get("id") or f"SC{idx + 1:03d}",
            category=c.get("category"),
            item=c.get("item") or "",
            max_score=c.get("max_score"),
            scoring_rule=c.get("scoring_rule"),
            keywords=c.get("keywords") or [],
            source_text=c.get("source_text"),
        )
        db.add(sc)
        created.append(sc)

    await db.flush()
    await db.commit()

    return {
        "success": True,
        "count": len(created),
        "total_score": data.get("total_score"),
        "technical_score": data.get("technical_score"),
        "commercial_score": data.get("commercial_score"),
        "other_score": data.get("other_score"),
        "items": [_to_item(sc) for sc in created],
    }


@router.get("/{project_id}")
async def list_scoring_criteria(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> list[ScoringCriteriaItem]:
    """获取项目的评分标准列表"""
    await _verify_project_access(project_id, current_user.id, db)

    result = await db.execute(
        select(ScoringCriteria)
        .where(ScoringCriteria.project_id == project_id)
        .order_by(ScoringCriteria.created_at)
    )
    items = result.scalars().all()
    return [_to_item(sc) for sc in items]


@router.put("/{project_id}/{scoring_id}")
async def update_scoring_criteria(
    project_id: uuid.UUID,
    scoring_id: uuid.UUID,
    request: ScoringUpdateRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> ScoringCriteriaItem:
    """修改评分项（编辑字段 / 绑定章节）"""
    await _verify_project_access(project_id, current_user.id, db)

    result = await db.execute(
        select(ScoringCriteria).where(
            and_(
                ScoringCriteria.id == scoring_id,
                ScoringCriteria.project_id == project_id,
            )
        )
    )
    sc = result.scalar_one_or_none()
    if not sc:
        raise HTTPException(status_code=404, detail="评分项不存在")

    if request.category is not None:
        sc.category = request.category
    if request.item is not None:
        sc.item = request.item
    if request.max_score is not None:
        sc.max_score = request.max_score
    if request.scoring_rule is not None:
        sc.scoring_rule = request.scoring_rule
    if request.keywords is not None:
        sc.keywords = request.keywords
    if "bound_chapter_id" in request.model_fields_set:
        if request.bound_chapter_id:
            sc.bound_chapter_id = uuid.UUID(request.bound_chapter_id)
        else:
            sc.bound_chapter_id = None

    await db.flush()
    await db.commit()
    await db.refresh(sc)
    return _to_item(sc)


@router.post("/{project_id}/auto-bind")
async def auto_bind_scoring_criteria(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """AI 自动根据 keywords 匹配评分项到章节"""
    await _verify_project_access(project_id, current_user.id, db)

    # 加载评分标准
    sc_result = await db.execute(
        select(ScoringCriteria).where(ScoringCriteria.project_id == project_id)
    )
    scoring_items = sc_result.scalars().all()

    if not scoring_items:
        raise HTTPException(status_code=400, detail="请先提取评分标准")

    # 加载章节
    ch_result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id)
    )
    chapters = ch_result.scalars().all()

    if not chapters:
        raise HTTPException(status_code=400, detail="请先生成目录章节")

    bound_count = 0

    for sc in scoring_items:
        if sc.bound_chapter_id:
            # 已绑定，跳过
            continue

        keywords: list[str] = sc.keywords or []
        item_name = sc.item.lower()

        best_chapter = None
        best_score = 0

        for chapter in chapters:
            ch_title = chapter.title.lower()
            ch_desc = (chapter.content or "").lower()
            ch_role = (chapter.chapter_role or "").lower()

            score = 0
            # 匹配评分项名称
            if item_name in ch_title:
                score += 5
            # 匹配关键词
            for kw in keywords:
                kw_l = kw.lower()
                if kw_l in ch_title:
                    score += 3
                elif kw_l in ch_role:
                    score += 2
                elif kw_l in ch_desc:
                    score += 1

            if score > best_score:
                best_score = score
                best_chapter = chapter

        if best_chapter and best_score >= 2:
            sc.bound_chapter_id = best_chapter.id
            bound_count += 1

    await db.flush()
    await db.commit()

    return {
        "success": True,
        "bound_count": bound_count,
        "total_count": len(scoring_items),
    }


@router.get("/{project_id}/coverage")
async def get_scoring_coverage(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> ScoringCoverageResponse:
    """获取评分覆盖率报告"""
    await _verify_project_access(project_id, current_user.id, db)

    result = await db.execute(
        select(ScoringCriteria).where(ScoringCriteria.project_id == project_id)
    )
    items = result.scalars().all()

    total = len(items)
    bound = sum(1 for sc in items if sc.bound_chapter_id)
    unbound = total - bound

    total_score = sum(sc.max_score or 0 for sc in items)
    bound_score = sum(sc.max_score or 0 for sc in items if sc.bound_chapter_id)
    unbound_score = total_score - bound_score

    coverage_rate = (bound_score / total_score * 100) if total_score > 0 else 0.0

    # 未绑定的高分项（≥8分）
    high_score_unbound = [
        _to_item(sc)
        for sc in items
        if not sc.bound_chapter_id and (sc.max_score or 0) >= 8
    ]
    high_score_unbound.sort(key=lambda x: x.max_score or 0, reverse=True)

    return ScoringCoverageResponse(
        total=total,
        bound=bound,
        unbound=unbound,
        bound_score=bound_score,
        unbound_score=unbound_score,
        total_score=total_score,
        coverage_rate=coverage_rate,
        high_score_unbound=high_score_unbound,
    )
