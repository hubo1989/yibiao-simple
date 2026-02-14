"""项目 CRUD API 路由"""

import uuid
import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, and_, exists, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.user import User
from ..models.project import Project, ProjectStatus, ProjectMemberRole, project_members
from ..models.chapter import Chapter, ChapterStatus
from ..models.consistency_result import (
    ConsistencyResult,
    ConsistencySeverity,
    ConsistencyCategory,
)
from ..models.operation_log import OperationLog, ActionType
from ..services.openai_service import OpenAIService
from ..schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectSummary,
    ProjectMemberAdd,
    ProjectMemberResponse,
    ProjectMemberWithUser,
    ProjectProgress,
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
    ContradictionItem,
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
        select(
            exists().where(
                and_(
                    project_members.c.project_id == project_id,
                    project_members.c.user_id == user_id,
                )
            )
        )
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
    status_filter: ProjectStatus | None = Query(
        None, alias="status", description="按状态筛选"
    ),
    sort_by: str = Query(
        "updated_at", description="排序字段：created_at, updated_at, status"
    ),
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


@router.get("/{project_id}/members", response_model=list[ProjectMemberWithUser])
async def list_project_members(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取项目成员列表（包含用户信息）"""
    # 验证项目存在且用户是成员
    await get_project_for_user(project_id, current_user.id, db)

    # 查询项目成员及用户信息
    result = await db.execute(
        select(
            project_members.c.user_id,
            User.username,
            User.email,
            project_members.c.role,
            project_members.c.joined_at,
        )
        .select_from(project_members)
        .join(User, project_members.c.user_id == User.id)
        .where(project_members.c.project_id == project_id)
        .order_by(project_members.c.joined_at.asc())
    )
    rows = result.fetchall()

    return [
        ProjectMemberWithUser(
            user_id=row.user_id,
            username=row.username,
            email=row.email,
            role=row.role,
            joined_at=row.joined_at,
        )
        for row in rows
    ]


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
    """邀请项目成员（需要 OWNER 或 EDITOR 角色）"""
    # 验证项目存在且当前用户是成员
    project = await get_project_for_user(project_id, current_user.id, db)

    # 检查当前用户是否有权限添加成员（仅 OWNER 或 EDITOR）
    current_user_role = await get_project_member_role(project_id, current_user.id, db)
    if current_user_role not in (ProjectMemberRole.OWNER, ProjectMemberRole.EDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有项目负责人或编辑才能添加成员",
        )

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
        select(
            exists().where(
                and_(
                    project_members.c.project_id == project_id,
                    project_members.c.user_id == data.user_id,
                )
            )
        )
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


@router.delete(
    "/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """移除项目成员（需要 OWNER 或 EDITOR 角色）"""
    # 验证项目存在且当前用户是成员
    await get_project_for_user(project_id, current_user.id, db)

    # 检查当前用户是否有权限移除成员（仅 OWNER 或 EDITOR）
    current_user_role = await get_project_member_role(project_id, current_user.id, db)
    if current_user_role not in (ProjectMemberRole.OWNER, ProjectMemberRole.EDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有项目负责人或编辑才能移除成员",
        )

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
        select(
            exists().where(
                and_(
                    project_members.c.project_id == project_id,
                    project_members.c.user_id == user_id,
                )
            )
        )
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


@router.get("/{project_id}/progress", response_model=ProjectProgress)
async def get_project_progress(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    获取项目进度统计

    返回各状态的章节数量和完成百分比
    """
    # 验证项目存在且用户是成员
    await get_project_for_user(project_id, current_user.id, db)

    # 统计各状态章节数量
    status_counts = {}
    for chapter_status in ChapterStatus:
        result = await db.execute(
            select(func.count(Chapter.id)).where(
                and_(
                    Chapter.project_id == project_id,
                    Chapter.status == chapter_status,
                )
            )
        )
        status_counts[chapter_status] = result.scalar() or 0

    total = sum(status_counts.values())

    # 计算完成百分比 (finalized / total)
    completion_percentage = 0.0
    if total > 0:
        completion_percentage = round(
            status_counts[ChapterStatus.FINALIZED] / total * 100, 2
        )

    return ProjectProgress(
        total_chapters=total,
        pending=status_counts[ChapterStatus.PENDING],
        generated=status_counts[ChapterStatus.GENERATED],
        reviewing=status_counts[ChapterStatus.REVIEWING],
        finalized=status_counts[ChapterStatus.FINALIZED],
        completion_percentage=completion_percentage,
    )


@router.post(
    "/{project_id}/consistency-check",
    response_model=ConsistencyCheckResponse,
    status_code=status.HTTP_200_OK,
)
async def check_project_consistency(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    检查项目跨章节一致性

    自动提取项目中所有已生成内容的章节摘要，进行跨章节一致性检查，
    检测数据、术语、时间线、承诺和范围等方面的矛盾。
    """
    from datetime import datetime

    # 验证项目存在且用户是成员
    project = await get_project_for_user(project_id, current_user.id, db)

    # 获取项目中所有有内容的章节
    result = await db.execute(
        select(Chapter)
        .where(
            and_(
                Chapter.project_id == project_id,
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
            detail="至少需要2个有内容的章节才能进行跨章节一致性检查",
        )

    # 准备章节摘要（截取内容前2000字符作为摘要）
    chapter_summaries = [
        {
            "chapter_number": ch.chapter_number,
            "title": ch.title,
            "summary": (
                ch.content[:2000]
                if ch.content and len(ch.content) > 2000
                else ch.content
            )
            or "",
        }
        for ch in chapters
    ]

    # 调用 AI 服务进行一致性检查
    openai_service = OpenAIService(db=db)

    full_content = ""
    async for chunk in openai_service.check_consistency(
        chapter_summaries=chapter_summaries,
        project_overview=project.project_overview,
        tech_requirements=project.tech_requirements,
    ):
        full_content += chunk

    # 解析 AI 返回的 JSON
    try:
        result_data = json.loads(full_content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 返回的结果格式无效",
        )

    # 统计矛盾数量
    contradictions = result_data.get("contradictions", [])
    contradiction_count = len(contradictions)
    critical_count = sum(1 for c in contradictions if c.get("severity") == "critical")

    # 保存检查结果到数据库
    consistency_result = ConsistencyResult(
        project_id=project_id,
        contradictions=json.dumps(contradictions, ensure_ascii=False),
        summary=result_data.get("summary", ""),
        overall_consistency=result_data.get("overall_consistency", "consistent"),
        contradiction_count=contradiction_count,
        critical_count=critical_count,
    )
    db.add(consistency_result)
    await db.flush()
    await db.refresh(consistency_result)

    # 记录操作日志
    log_entry = OperationLog(
        user_id=current_user.id,
        project_id=project_id,
        action=ActionType.CONSISTENCY_CHECK,
        detail={"message": f"完成跨章节一致性检查，发现 {contradiction_count} 个矛盾"},
    )
    db.add(log_entry)

    await db.commit()

    # 构建响应
    return ConsistencyCheckResponse(
        contradictions=[
            ContradictionItem(
                severity=ConsistencySeverity(c.get("severity", "info")),
                category=ConsistencyCategory(c.get("category", "data")),
                description=c.get("description", ""),
                chapter_a=c.get("chapter_a", ""),
                chapter_b=c.get("chapter_b", ""),
                detail_a=c.get("detail_a", ""),
                detail_b=c.get("detail_b", ""),
                suggestion=c.get("suggestion", ""),
            )
            for c in contradictions
        ],
        summary=result_data.get("summary", ""),
        overall_consistency=result_data.get("overall_consistency", "consistent"),
        contradiction_count=contradiction_count,
        critical_count=critical_count,
        created_at=consistency_result.created_at,
    )
