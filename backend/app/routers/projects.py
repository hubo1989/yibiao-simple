"""项目 CRUD API 路由"""
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy import select, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.user import User
from ..models.project import Project, ProjectStatus, ProjectMemberRole, project_members
from ..schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectSummary,
    ProjectMemberAdd,
    ProjectMemberResponse,
)
from ..auth.dependencies import get_current_active_user, require_editor

router = APIRouter(prefix="/api/projects", tags=["项目"])


async def get_project_for_user(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Project:
    """获取项目并验证用户是否是项目成员"""
    # 检查用户是否是项目成员
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

    # 获取项目
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )
    return project


async def get_project_member_role(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> ProjectMemberRole | None:
    """获取用户在项目中的角色"""
    result = await db.execute(
        select(project_members.c.role).where(
            and_(
                project_members.c.project_id == project_id,
                project_members.c.user_id == user_id,
            )
        )
    )
    return result.scalar_one_or_none()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """创建项目（需要 Editor 或更高角色）"""
    # 创建项目
    new_project = Project(
        name=data.name,
        description=data.description,
        creator_id=current_user.id,
        status=ProjectStatus.DRAFT,
    )
    db.add(new_project)
    await db.flush()
    await db.refresh(new_project)

    # 将创建者添加为项目成员（owner 角色）
    await db.execute(
        project_members.insert().values(
            user_id=current_user.id,
            project_id=new_project.id,
            role=ProjectMemberRole.OWNER,
        )
    )
    await db.flush()

    return new_project


@router.get("", response_model=list[ProjectSummary])
async def list_projects(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: ProjectStatus | None = Query(None, alias="status", description="按状态筛选"),
    sort_by: str = Query("updated_at", description="排序字段：created_at, updated_at, status"),
    sort_order: str = Query("desc", description="排序方向：asc, desc"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取当前用户参与的项目列表（支持按状态和时间排序）"""
    # 基础查询：只获取用户参与的项目
    query = (
        select(Project)
        .join(project_members, Project.id == project_members.c.project_id)
        .where(project_members.c.user_id == current_user.id)
    )

    # 状态筛选
    if status_filter:
        query = query.where(Project.status == status_filter)

    # 排序
    order_column = getattr(Project, sort_by, Project.updated_at)
    if sort_order == "asc":
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())

    # 分页
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    projects = result.scalars().all()

    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取项目详情"""
    project = await get_project_for_user(project_id, current_user.id, db)
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """更新项目（需要项目成员身份）"""
    project = await get_project_for_user(project_id, current_user.id, db)

    # 更新字段
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.flush()
    await db.refresh(project)

    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """删除项目（仅创建者）"""
    project = await get_project_for_user(project_id, current_user.id, db)

    # 验证是否是创建者
    if project.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有项目创建者才能删除项目",
        )

    await db.delete(project)


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_project_member(
    project_id: uuid.UUID,
    data: ProjectMemberAdd,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """邀请项目成员（需要项目成员身份）"""
    # 验证项目存在且当前用户是成员
    project = await get_project_for_user(project_id, current_user.id, db)

    # 检查被邀请用户是否存在
    user_result = await db.execute(select(User).where(User.id == data.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 检查是否已经是项目成员
    existing = await db.execute(
        select(exists().where(
            and_(
                project_members.c.project_id == project_id,
                project_members.c.user_id == data.user_id,
            )
        ))
    )
    if existing.scalar():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户已经是项目成员",
        )

    # 添加成员
    await db.execute(
        project_members.insert().values(
            user_id=data.user_id,
            project_id=project_id,
            role=data.role,
        )
    )
    await db.flush()

    # 返回成员信息
    return ProjectMemberResponse(
        user_id=data.user_id,
        project_id=project_id,
        role=data.role,
        joined_at=project.updated_at,  # 使用当前时间作为 joined_at
    )


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """移除项目成员（需要项目成员身份）"""
    # 验证项目存在且当前用户是成员
    await get_project_for_user(project_id, current_user.id, db)

    # 不能移除创建者
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if project and project.creator_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除项目创建者",
        )

    # 检查要移除的成员是否存在
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
            detail="该用户不是项目成员",
        )

    # 删除成员
    await db.execute(
        project_members.delete().where(
            and_(
                project_members.c.project_id == project_id,
                project_members.c.user_id == user_id,
            )
        )
    )
