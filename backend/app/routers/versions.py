"""版本快照 API 路由"""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy import select, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.user import User
from ..models.project import project_members, ProjectMemberRole
from ..models.version import ChangeType, ProjectVersion
from ..schemas.version import (
    VersionResponse,
    VersionSummary,
    VersionList,
    VersionDiffResponse,
    VersionRollbackResponse,
    RestoredChapter,
)
from ..services.version_service import VersionService
from ..auth.dependencies import get_current_active_user, require_editor

router = APIRouter(prefix="/api/projects", tags=["版本"])


async def verify_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """验证用户是否是项目成员"""
    member_exists = await db.execute(
        select(exists().where(
            and_(
                project_members.c.project_id == project_id,
                project_members.c.user_id == user_id,
            )
        ))
    )
    if not member_exists.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或您没有访问权限",
        )


async def verify_editor_role(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """验证用户是否具有编辑权限（owner 或 editor）"""
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或您没有访问权限",
        )

    if role not in (ProjectMemberRole.OWNER, ProjectMemberRole.EDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要编辑或管理员权限",
        )


@router.get("/{project_id}/versions", response_model=VersionList)
async def list_project_versions(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    chapter_id: uuid.UUID | None = Query(None, description="按章节 ID 过滤"),
    change_type: ChangeType | None = Query(None, description="按变更类型过滤"),
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(20, ge=1, le=100, description="返回记录数"),
):
    """
    获取项目版本列表（分页）

    - **project_id**: 项目 ID
    - **chapter_id**: 可选，按章节 ID 过滤
    - **change_type**: 可选，按变更类型过滤
    - **skip**: 分页偏移
    - **limit**: 每页数量
    """
    await verify_project_member(project_id, current_user.id, db)

    version_service = VersionService(db)
    versions, total = await version_service.list_versions(
        project_id=project_id,
        chapter_id=chapter_id,
        change_type=change_type,
        skip=skip,
        limit=limit,
    )

    # 转换为摘要格式
    summaries = [
        VersionSummary.model_validate(v)
        for v in versions
    ]

    return VersionList(
        items=summaries,
        total=total,
        project_id=project_id,
    )


@router.get("/{project_id}/versions/{version_id}", response_model=VersionResponse)
async def get_project_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    获取版本详情（含完整快照）

    - **project_id**: 项目 ID
    - **version_id**: 版本 ID
    """
    await verify_project_member(project_id, current_user.id, db)

    version_service = VersionService(db)
    version = await version_service.get_version(project_id, version_id)

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在",
        )

    return VersionResponse.model_validate(version)


@router.get("/{project_id}/versions/diff", response_model=VersionDiffResponse)
async def diff_project_versions(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    v1: uuid.UUID = Query(..., description="第一个版本 ID"),
    v2: uuid.UUID = Query(..., description="第二个版本 ID"),
):
    """
    对比两个版本间的差异（章节级别）

    - **project_id**: 项目 ID
    - **v1**: 第一个版本 ID
    - **v2**: 第二个版本 ID
    """
    await verify_project_member(project_id, current_user.id, db)

    version_service = VersionService(db)
    diff_result = await version_service.diff_versions(project_id, v1, v2)

    # 检查是否有错误
    if "error" in diff_result and diff_result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=diff_result["error"],
        )

    return VersionDiffResponse(**diff_result)


@router.post(
    "/{project_id}/versions/{version_id}/rollback",
    response_model=VersionRollbackResponse,
)
async def rollback_to_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    create_snapshot: bool = Query(True, description="回滚前是否创建当前状态快照"),
):
    """
    回滚到指定版本，自动创建新版本记录

    - **project_id**: 项目 ID
    - **version_id**: 目标版本 ID
    - **create_snapshot**: 是否在回滚前创建当前状态快照（默认 True）
    """
    await verify_editor_role(project_id, current_user.id, db)

    version_service = VersionService(db)
    result = await version_service.rollback_to_version(
        project_id=project_id,
        version_id=version_id,
        user_id=current_user.id,
        create_pre_snapshot=create_snapshot,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "回滚失败"),
        )

    return VersionRollbackResponse(
        success=True,
        target_version_number=result.get("target_version_number"),
        new_version_id=result.get("new_version_id"),
        new_version_number=result.get("new_version_number"),
        pre_snapshot_id=result.get("pre_snapshot_id"),
        restored_chapters=[
            RestoredChapter(**ch) for ch in result.get("restored_chapters", [])
        ],
        error=None,
    )


@router.post(
    "/{project_id}/versions",
    response_model=VersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_manual_snapshot(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    change_summary: str | None = Query(None, description="变更摘要说明"),
):
    """
    手动创建项目完整快照

    - **project_id**: 项目 ID
    - **change_summary**: 可选的变更摘要说明
    """
    await verify_editor_role(project_id, current_user.id, db)

    version_service = VersionService(db)
    version = await version_service.create_project_snapshot(
        project_id=project_id,
        user_id=current_user.id,
        change_type=ChangeType.MANUAL_EDIT,
        change_summary=change_summary or "手动创建快照",
    )

    return VersionResponse.model_validate(version)
