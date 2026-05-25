"""响应矩阵 API 路由"""

import uuid
import logging
from typing import Annotated, Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project import Project, project_members
from ..models.response_matrix import TenderClause, ResponseMatrixItem, ResponseStatus
from ..models.user import User
from ..db.database import get_db
from ..auth.dependencies import require_editor
from ..schemas.response_matrix import (
    TenderClauseResponse,
    ResponseMatrixItemResponse,
    ResponseMatrixSummary,
    BindClauseRequest,
    UpdateMatrixItemRequest,
    RebuildMatrixRequest,
    ResponseMatrixPreflight,
)
from ..services import response_matrix_service as svc

router = APIRouter(prefix="/api/response-matrix", tags=["响应矩阵"])


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


def _clause_response(tc: TenderClause) -> TenderClauseResponse:
    return TenderClauseResponse(
        id=str(tc.id),
        project_id=str(tc.project_id),
        clause_type=tc.clause_type.value,
        title=tc.title,
        content=tc.content,
        source_page=tc.source_page,
        source_location=tc.source_location,
        score_value=float(tc.score_value) if tc.score_value is not None else None,
        is_fatal=tc.is_fatal,
    )


def _item_response(item: ResponseMatrixItem) -> ResponseMatrixItemResponse:
    return ResponseMatrixItemResponse(
        id=str(item.id),
        project_id=str(item.project_id),
        clause_id=str(item.clause_id),
        chapter_id=item.chapter_id,
        chapter_title=item.chapter_title,
        response_status=item.response_status.value,
        response_summary=item.response_summary,
        evidence_summary=item.evidence_summary,
        risk_note=item.risk_note,
        confidence=item.confidence,
        updated_at=item.updated_at,
    )


# ============ 路由 ============


@router.get("/{project_id}/summary", response_model=ResponseMatrixSummary)
async def get_matrix_summary(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> ResponseMatrixSummary:
    """获取响应矩阵摘要"""
    await _verify_project_access(project_id, current_user.id, db)
    return await svc.summarize(db, project_id)


@router.get("/{project_id}/preflight", response_model=ResponseMatrixPreflight)
async def get_matrix_preflight(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> ResponseMatrixPreflight:
    """导出前检查响应矩阵：返回摘要和阻塞项。"""
    await _verify_project_access(project_id, current_user.id, db)
    return ResponseMatrixPreflight(**await svc.preflight(db, project_id))


@router.get("/{project_id}/clauses", response_model=list[TenderClauseResponse])
async def list_clauses(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> list[TenderClauseResponse]:
    """获取项目的所有统一条款"""
    await _verify_project_access(project_id, current_user.id, db)
    result = await db.execute(
        select(TenderClause)
        .where(TenderClause.project_id == project_id)
        .order_by(TenderClause.created_at)
    )
    clauses = result.scalars().all()
    return [_clause_response(tc) for tc in clauses]


@router.get("/{project_id}/items", response_model=list[ResponseMatrixItemResponse])
async def list_items(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> list[ResponseMatrixItemResponse]:
    """获取项目的所有响应矩阵条目"""
    await _verify_project_access(project_id, current_user.id, db)
    result = await db.execute(
        select(ResponseMatrixItem)
        .where(ResponseMatrixItem.project_id == project_id)
        .order_by(ResponseMatrixItem.updated_at.desc())
    )
    items = result.scalars().all()
    return [_item_response(item) for item in items]


@router.post("/{project_id}/rebuild", response_model=ResponseMatrixSummary)
async def rebuild_matrix(
    project_id: uuid.UUID,
    request: RebuildMatrixRequest | None = None,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> ResponseMatrixSummary:
    """重建响应矩阵（从现有评分标准/废标检查数据重新提取）"""
    await _verify_project_access(project_id, current_user.id, db)
    return await svc.rebuild(db, project_id)


@router.post("/{project_id}/bind", response_model=ResponseMatrixItemResponse)
async def bind_clause(
    project_id: uuid.UUID,
    request: BindClauseRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> ResponseMatrixItemResponse:
    """手动绑定条款到章节"""
    await _verify_project_access(project_id, current_user.id, db)

    try:
        clause_uuid = uuid.UUID(request.clause_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 clause_id 格式")

    # Verify clause belongs to this project
    result = await db.execute(
        select(TenderClause).where(
            and_(
                TenderClause.id == clause_uuid,
                TenderClause.project_id == project_id,
            )
        )
    )
    clause = result.scalar_one_or_none()
    if not clause:
        raise HTTPException(status_code=404, detail="条款不存在")

    # Upsert: find existing item or create new
    existing = await db.execute(
        select(ResponseMatrixItem).where(
            and_(
                ResponseMatrixItem.clause_id == clause_uuid,
                ResponseMatrixItem.project_id == project_id,
            )
        )
    )
    item = existing.scalar_one_or_none()

    if item:
        item.chapter_id = request.chapter_id
        item.chapter_title = request.chapter_title
        item.response_status = ResponseStatus.covered
    else:
        item = ResponseMatrixItem(
            project_id=project_id,
            clause_id=clause_uuid,
            chapter_id=request.chapter_id,
            chapter_title=request.chapter_title,
            response_status=ResponseStatus.covered,
        )
        db.add(item)

    await db.flush()
    await db.commit()
    await db.refresh(item)
    return _item_response(item)


@router.patch("/items/{item_id}", response_model=ResponseMatrixItemResponse)
async def update_item(
    item_id: uuid.UUID,
    request: UpdateMatrixItemRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> ResponseMatrixItemResponse:
    """更新响应矩阵条目状态"""
    updated = await svc.update_item_status(
        db,
        item_id,
        status=request.response_status,
        summary=request.response_summary,
        evidence=request.evidence_summary,
        risk_note=request.risk_note,
        confidence=request.confidence,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="矩阵条目不存在")

    await db.commit()
    await db.refresh(updated)
    return _item_response(updated)
