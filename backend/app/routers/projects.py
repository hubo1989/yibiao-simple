"""项目 CRUD API 路由"""

import uuid
import json
import logging
import re
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, exists, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.user import User
from ..models.project import Project, ProjectStatus, ProjectMemberRole, project_members
from ..models.chapter import Chapter, ChapterStatus

logger = logging.getLogger(__name__)
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
    RatingChecklistItem,
    RatingChecklistResponse,
    ClauseResponseRequest,
    ClauseResponseResult,
    ChapterReverseEnhanceResponse,
)
from ..schemas.prompt import (
    ProjectPromptConfig,
    ProjectPromptConfigListResponse,
    ProjectPromptOverride,
)
from ..services.prompt_service import PromptService
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


class DashboardChapterStats(BaseModel):
    """章节状态统计"""
    total: int = 0
    pending: int = 0
    generated: int = 0
    reviewing: int = 0
    finalized: int = 0


class DashboardProjectItem(BaseModel):
    """看板中单个项目的概览"""
    id: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    chapter_stats: DashboardChapterStats
    completion_percentage: float


class DashboardStatusCount(BaseModel):
    """按状态分组的项目数"""
    draft: int = 0
    in_progress: int = 0
    reviewing: int = 0
    completed: int = 0


class DashboardChapterStatusCount(BaseModel):
    """全局章节状态统计"""
    pending: int = 0
    generated: int = 0
    reviewing: int = 0
    finalized: int = 0


class DashboardResponse(BaseModel):
    """进度看板响应"""
    total_projects: int
    by_status: DashboardStatusCount
    total_chapters: int
    chapter_by_status: DashboardChapterStatusCount
    projects: list[DashboardProjectItem]


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    进度看板 — 返回当前用户参与的所有项目的进度概览

    包含全局汇总统计和逐项目的章节状态明细。
    """
    # 获取用户参与的所有项目
    query = (
        select(Project)
        .join(project_members, Project.id == project_members.c.project_id)
        .where(project_members.c.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
    )
    result = await db.execute(query)
    projects = result.scalars().all()

    # 全局状态统计
    by_status = DashboardStatusCount()
    total_chapters = 0
    chapter_by_status = DashboardChapterStatusCount()

    project_items: list[DashboardProjectItem] = []

    for proj in projects:
        # 更新项目状态计数
        status_val = proj.status.value if isinstance(proj.status, ProjectStatus) else proj.status
        if hasattr(by_status, status_val):
            setattr(by_status, status_val, getattr(by_status, status_val) + 1)

        # 统计该项目的章节状态
        chapter_counts_result = await db.execute(
            select(Chapter.status, func.count(Chapter.id))
            .where(Chapter.project_id == proj.id)
            .group_by(Chapter.status)
        )
        chapter_counts = dict(chapter_counts_result.all())

        stats = DashboardChapterStats(
            total=sum(chapter_counts.values()),
            pending=chapter_counts.get(ChapterStatus.PENDING, 0),
            generated=chapter_counts.get(ChapterStatus.GENERATED, 0),
            reviewing=chapter_counts.get(ChapterStatus.REVIEWING, 0),
            finalized=chapter_counts.get(ChapterStatus.FINALIZED, 0),
        )

        # 计算完成百分比
        completion = 0.0
        if stats.total > 0:
            completion = round(stats.finalized / stats.total * 100, 1)

        # 累计全局章节统计
        total_chapters += stats.total
        chapter_by_status.pending += stats.pending
        chapter_by_status.generated += stats.generated
        chapter_by_status.reviewing += stats.reviewing
        chapter_by_status.finalized += stats.finalized

        project_items.append(
            DashboardProjectItem(
                id=str(proj.id),
                name=proj.name,
                status=status_val,
                created_at=proj.created_at,
                updated_at=proj.updated_at,
                chapter_stats=stats,
                completion_percentage=completion,
            )
        )

    return DashboardResponse(
        total_projects=len(projects),
        by_status=by_status,
        total_chapters=total_chapters,
        chapter_by_status=chapter_by_status,
        projects=project_items,
    )


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
    request: ConsistencyCheckRequest | None = None,
):
    """
    检查项目跨章节一致性

    如果前端传递了章节摘要，使用前端数据；否则从数据库读取。
    检测数据、术语、时间线、承诺和范围等方面的矛盾。
    """
    from datetime import datetime

    # 验证项目存在且用户是成员
    project = await get_project_for_user(project_id, current_user.id, db)

    logger.info(f"一致性检查请求: request={request}, chapter_summaries_count={len(request.chapter_summaries) if request else 0}")

    # 如果前端传递了章节摘要，直接使用
    if request and request.chapter_summaries:
        chapter_summaries = [
            {
                "chapter_number": ch.chapter_number,
                "title": ch.title,
                "summary": ch.summary[:2000] if len(ch.summary) > 2000 else ch.summary,
                "chapter_id": ch.chapter_id or ch.chapter_number,
            }
            for ch in request.chapter_summaries
            if ch.summary and ch.summary.strip()  # 过滤掉空内容
        ]
        logger.info(f"使用前端传递的章节摘要: {len(chapter_summaries)} 个")
    else:
        # 从数据库获取项目中所有有内容的章节
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
                "chapter_id": str(ch.id),
            }
            for ch in chapters
        ]

    if len(chapter_summaries) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要2个有内容的章节才能进行跨章节一致性检查",
        )

    # 构建 chapter_number -> chapter_id 的映射
    chapter_id_map = {ch["chapter_number"]: ch.get("chapter_id", ch["chapter_number"]) for ch in chapter_summaries}

    # 调用 AI 服务进行一致性检查
    openai_service = OpenAIService(db=db)

    logger.info(f"开始调用 AI 一致性检查，章节数: {len(chapter_summaries)}")
    for i, ch in enumerate(chapter_summaries):
        logger.info(f"  章节 {i+1}: {ch.get('chapter_number')} {ch.get('title')}, 内容长度: {len(ch.get('summary', ''))}")

    full_content = ""
    async for chunk in openai_service.check_consistency(
        chapter_summaries=chapter_summaries,
        project_overview=project.project_overview,
        tech_requirements=project.tech_requirements,
    ):
        full_content += chunk

    logger.info(f"一致性检查 AI 返回内容长度: {len(full_content)}")

    # 检查是否返回了空内容
    if not full_content or not full_content.strip():
        logger.error("一致性检查 AI 返回空内容")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 返回了空内容，请重试",
        )

    # 解析 AI 返回的 JSON
    # 先尝试清理可能存在的 markdown 代码块标记
    json_content = full_content.strip()
    if json_content.startswith("```"):
        # 移除 markdown 代码块标记
        json_content = re.sub(r'^```(?:json)?\s*\n?', '', json_content)
        json_content = re.sub(r'\n?```\s*$', '', json_content)
        json_content = json_content.strip()

    # 如果不是有效的 JSON，尝试从文本中提取 JSON 对象
    if not json_content.startswith('{'):
        # 尝试找到第一个 { 和最后一个 }
        start = json_content.find('{')
        end = json_content.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_content = json_content[start:end+1]

    # 修复中文引号问题：将中文引号替换为英文引号
    json_content = json_content.replace('"', '"').replace('"', '"')
    # 修复中文冒号
    json_content = json_content.replace('：', ':')

    try:
        result_data = json.loads(json_content)
    except json.JSONDecodeError as e:
        logger.error(f"一致性检查 JSON 解析失败: {e}")
        logger.error(f"AI 返回内容长度: {len(full_content)}")
        logger.error(f"清理后内容长度: {len(json_content)}")
        # 打印出错位置附近的内容
        error_pos = e.pos if hasattr(e, 'pos') else 0
        start_pos = max(0, error_pos - 100)
        end_pos = min(len(json_content), error_pos + 100)
        logger.error(f"出错位置附近的内容 (pos={error_pos}): {json_content[start_pos:end_pos]}")
        logger.error(f"清理后内容: {json_content}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 返回的结果格式无效，请重试",
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
    def get_chapter_id(chapter_ref: str) -> str | None:
        """从 'chapter_number title' 格式中提取 chapter_id"""
        # chapter_ref 格式可能是 "1.2.3 标题" 或直接是 ID
        parts = chapter_ref.split(" ", 1)
        chapter_number = parts[0] if parts else chapter_ref
        return chapter_id_map.get(chapter_number, chapter_number if chapter_number else None)

    return ConsistencyCheckResponse(
        contradictions=[
            ContradictionItem(
                severity=ConsistencySeverity(c.get("severity", "info")),
                category=ConsistencyCategory(c.get("category", "data")),
                description=c.get("description", ""),
                chapter_a=c.get("chapter_a", ""),
                chapter_b=c.get("chapter_b", ""),
                chapter_id_a=get_chapter_id(c.get("chapter_a", "")),
                chapter_id_b=get_chapter_id(c.get("chapter_b", "")),
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


# ==================== 高分投标专用接口 ====================

@router.post(
    "/{project_id}/rating-response-checklist",
    response_model=RatingChecklistResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_rating_response_checklist(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """按项目评分要求生成响应清单"""
    project = await get_project_for_user(project_id, current_user.id, db)

    if not project.tech_requirements:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目缺少技术评分要求，无法生成响应清单",
        )

    openai_service = OpenAIService(db=db, project_id=project_id)
    result_text = await openai_service.generate_rating_response_checklist(
        overview=project.project_overview or "",
        requirements=project.tech_requirements or "",
    )

    try:
        items = json.loads(result_text)
    except json.JSONDecodeError as e:
        logger.error(f"评分项响应清单 JSON 解析失败: {e}; content={result_text[:500]}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 返回的评分响应清单格式无效，请重试",
        )

    return RatingChecklistResponse(
        items=[RatingChecklistItem(**item) for item in items]
    )


@router.post(
    "/{project_id}/chapters/{chapter_id}/reverse-enhance",
    response_model=ChapterReverseEnhanceResponse,
    status_code=status.HTTP_200_OK,
)
async def reverse_enhance_project_chapter(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """根据评分点对指定章节进行反向补强分析"""
    project = await get_project_for_user(project_id, current_user.id, db)

    chapter_result = await db.execute(
        select(Chapter).where(
            and_(Chapter.id == chapter_id, Chapter.project_id == project_id)
        )
    )
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    if not project.tech_requirements:
        raise HTTPException(status_code=400, detail="项目缺少技术评分要求")
    if not chapter.content or not chapter.content.strip():
        raise HTTPException(status_code=400, detail="章节内容为空，无法补强")

    openai_service = OpenAIService(db=db, project_id=project_id)
    result_text = await openai_service.reverse_enhance_chapter(
        chapter_title=chapter.title,
        chapter_content=chapter.content,
        tech_requirements=project.tech_requirements,
        project_overview=project.project_overview,
    )

    try:
        result_data = json.loads(result_text)
    except json.JSONDecodeError as e:
        logger.error(f"章节反向补强 JSON 解析失败: {e}; content={result_text[:500]}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 返回的章节补强结果格式无效，请重试",
        )

    return ChapterReverseEnhanceResponse(**result_data)


@router.post(
    "/{project_id}/clause-response",
    response_model=ClauseResponseResult,
    status_code=status.HTTP_200_OK,
)
async def generate_clause_response(
    project_id: uuid.UUID,
    request: ClauseResponseRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """生成技术参数/条款逐条响应正文"""
    project = await get_project_for_user(project_id, current_user.id, db)

    openai_service = OpenAIService(db=db, project_id=project_id)
    content = await openai_service.generate_clause_response(
        clause_text=request.clause_text,
        project_overview=project.project_overview,
        knowledge_context=request.knowledge_context,
    )

    return ClauseResponseResult(content=content.strip())


# ==================== 章节重写接口 ====================

class RewriteChapterRequest(BaseModel):
    """重写章节请求"""
    chapter_title: str = Field(..., description="章节标题")
    chapter_content: str = Field(..., description="原始章节内容")
    suggestions: list[str] = Field(..., description="修改建议列表")


class RewriteChapterResponse(BaseModel):
    """重写章节响应"""
    rewritten_content: str = Field(..., description="重写后的章节内容")


@router.post(
    "/{project_id}/chapters/rewrite",
    response_model=RewriteChapterResponse,
    status_code=status.HTTP_200_OK,
)
async def rewrite_chapter(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    request: RewriteChapterRequest,
):
    """
    使用 LLM 根据修改建议重写章节内容

    将章节内容和修改建议发送给 LLM，让它根据建议重写内容。
    """
    from ..services.openai_service import OpenAIService

    # 验证项目存在且用户是成员
    await get_project_for_user(project_id, current_user.id, db)

    logger.info(f"重写章节请求: project_id={project_id}, chapter_title={request.chapter_title}")
    logger.info(f"修改建议: {request.suggestions}")

    # 检查参数
    if not request.suggestions or len(request.suggestions) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="修改建议不能为空",
        )

    # 调用 LLM 重写/生成章节（内容可以为空，空时生成新内容）
    openai_service = OpenAIService(db=db, project_id=project_id)

    try:
        rewritten_content = await openai_service.rewrite_chapter_with_suggestions(
            chapter_title=request.chapter_title,
            chapter_content=request.chapter_content,
            suggestions=request.suggestions,
        )
    except Exception as e:
        logger.error(f"重写章节失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重写章节失败: {str(e)}",
        )

    logger.info(f"重写章节成功: 原长度={len(request.chapter_content)}, 新长度={len(rewritten_content)}")

    return RewriteChapterResponse(rewritten_content=rewritten_content)


# ==================== 项目提示词配置接口 ====================

@router.get("/{project_id}/prompts", response_model=ProjectPromptConfigListResponse)
async def list_project_prompts(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(None, description="按类别筛选：analysis/generation/check"),
):
    """
    获取项目的所有提示词配置

    显示每个场景的最终配置及继承状态（项目级 > 全局 > 内置）
    """
    # 验证项目存在且用户是成员
    await get_project_for_user(project_id, current_user.id, db)

    prompt_service = PromptService(db)
    prompts = await prompt_service.list_project_prompts(project_id)

    # 按类别筛选
    if category:
        prompts = [p for p in prompts if p["category"] == category]

    return ProjectPromptConfigListResponse(
        items=[ProjectPromptConfig(**p) for p in prompts],
        total=len(prompts),
    )


@router.get("/{project_id}/prompts/{scene_key}", response_model=ProjectPromptConfig)
async def get_project_prompt(
    project_id: uuid.UUID,
    scene_key: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取项目中特定场景的提示词配置"""
    # 验证项目存在且用户是成员
    await get_project_for_user(project_id, current_user.id, db)

    prompt_service = PromptService(db)
    prompts = await prompt_service.list_project_prompts(project_id)

    for p in prompts:
        if p["scene_key"] == scene_key:
            return ProjectPromptConfig(**p)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"场景 {scene_key} 不存在",
    )


@router.put("/{project_id}/prompts/{scene_key}", response_model=ProjectPromptConfig)
async def set_project_prompt(
    project_id: uuid.UUID,
    scene_key: str,
    data: ProjectPromptOverride,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    设置项目级提示词覆盖（需要 EDITOR 或更高角色）

    项目级配置优先于全局配置和内置默认
    """
    # 验证项目存在和权限
    await get_project_for_user(project_id, current_user.id, db)

    # 检查是否有编辑权限（仅 OWNER 或 EDITOR）
    current_user_role = await get_project_member_role(project_id, current_user.id, db)
    if current_user_role not in (ProjectMemberRole.OWNER, ProjectMemberRole.EDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有项目负责人或编辑才能设置提示词",
        )

    prompt_service = PromptService(db)

    try:
        await prompt_service.set_project_prompt(
            project_id=project_id,
            scene_key=scene_key,
            prompt=data.prompt,
        )

        # 返回更新后的配置
        prompts = await prompt_service.list_project_prompts(project_id)
        for p in prompts:
            if p["scene_key"] == scene_key:
                return ProjectPromptConfig(**p)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{project_id}/prompts/{scene_key}", response_model=ProjectPromptConfig)
async def delete_project_prompt(
    project_id: uuid.UUID,
    scene_key: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    删除项目级提示词覆盖（需要 EDITOR 或更高角色）

    删除后将回退到全局配置或内置默认
    """
    # 验证项目存在和权限
    await get_project_for_user(project_id, current_user.id, db)

    # 检查是否有编辑权限（仅 OWNER 或 EDITOR）
    current_user_role = await get_project_member_role(project_id, current_user.id, db)
    if current_user_role not in (ProjectMemberRole.OWNER, ProjectMemberRole.EDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有项目负责人或编辑才能删除提示词",
        )

    prompt_service = PromptService(db)

    deleted = await prompt_service.delete_project_prompt(project_id, scene_key)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"场景 {scene_key} 没有项目级覆盖",
        )

    # 返回删除后的配置（回退到全局或内置）
    prompts = await prompt_service.list_project_prompts(project_id)
    for p in prompts:
        if p["scene_key"] == scene_key:
            return ProjectPromptConfig(**p)
