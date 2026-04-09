"""历史标书解析 API 路由"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import require_editor
from ..db.database import get_db
from ..models.user import User
from ..schemas.material import (
    IngestionTaskCreate,
    IngestionTaskResponse,
    MaterialCandidateResponse,
    IngestionConfirmRequest,
)
from ..services.ingestion_service import HistoricalBidIngestionService

router = APIRouter(prefix="/api/ingestion", tags=["历史标书解析"])


@router.post("/tasks", response_model=IngestionTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_ingestion_task(
    request: IngestionTaskCreate,
    current_user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """创建历史标书解析任务"""
    service = HistoricalBidIngestionService(db)
    try:
        task = await service.create_ingestion_task(
            document_id=request.document_id,
            created_by=current_user.id,
        )
        return IngestionTaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/tasks/{task_id}", response_model=IngestionTaskResponse)
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取解析任务状态"""
    import uuid
    service = HistoricalBidIngestionService(db)
    task = await service.get_task_status(uuid.UUID(task_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return IngestionTaskResponse.model_validate(task)


@router.post("/tasks/{task_id}/process", response_model=list[MaterialCandidateResponse])
async def process_document(
    task_id: str,
    current_user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """执行文档解析"""
    import uuid
    service = HistoricalBidIngestionService(db)
    try:
        candidates = await service.process_document(uuid.UUID(task_id))
        return [MaterialCandidateResponse.model_validate(c) for c in candidates]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/tasks/{task_id}/candidates", response_model=list[MaterialCandidateResponse])
async def list_candidates(
    task_id: str,
    current_user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """获取任务的候选素材列表"""
    import uuid
    service = HistoricalBidIngestionService(db)
    candidates = await service.list_candidates(uuid.UUID(task_id))
    return [MaterialCandidateResponse.model_validate(c) for c in candidates]


@router.post("/tasks/{task_id}/confirm")
async def confirm_candidates(
    task_id: str,
    request: IngestionConfirmRequest,
    current_user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """确认候选素材并入库"""
    import uuid
    service = HistoricalBidIngestionService(db)
    try:
        confirmed, rejected = await service.confirm_candidates(
            task_id=uuid.UUID(task_id),
            confirm_ids=request.confirm_ids,
            reject_ids=request.reject_ids,
            owner_id=current_user.id,
        )
        return {
            "success": True,
            "confirmed_count": confirmed,
            "rejected_count": rejected,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
