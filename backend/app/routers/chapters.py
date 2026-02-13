"""章节相关 API 路由 - 包含锁定机制和状态流转"""
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter import Chapter, ChapterStatus
from ..models.project import project_members, ProjectMemberRole, Project
from ..models.version import ProjectVersion, ChangeType
from ..models.user import User, UserRole
from ..models.operation_log import OperationLog, ActionType
from ..models.proofread_result import ProofreadResult, IssueSeverity, IssueCategory
from ..db.database import get_db
from ..auth.dependencies import require_editor, get_current_active_user
from ..services.version_service import VersionService
from ..services.openai_service import OpenAIService

router = APIRouter(prefix="/api/chapters", tags=["章节管理"])

# 锁定超时时间（30 分钟）
LOCK_TIMEOUT_MINUTES = 30


# ============ Schemas ============

class ChapterContentUpdateRequest(BaseModel):
    """章节内容更新请求"""
    content: str = Field(..., description="章节内容")
    change_summary: str | None = Field(None, description="变更摘要")


class LockResponse(BaseModel):
    """锁定响应"""
    success: bool
    chapter_id: str
    locked_by: str | None = None
    locked_at: str | None = None
    locked_by_username: str | None = None
    message: str = ""


class ChapterContentResponse(BaseModel):
    """章节内容响应"""
    id: str
    chapter_number: str
    title: str
    content: str | None
    status: str
    locked_by: str | None = None
    locked_at: str | None = None
    locked_by_username: str | None = None
    is_locked: bool = False
    lock_expired: bool = False


class StatusUpdateRequest(BaseModel):
    """章节状态更新请求"""
    status: ChapterStatus = Field(..., description="目标状态")


class StatusUpdateResponse(BaseModel):
    """章节状态更新响应"""
    id: str
    chapter_number: str
    title: str
    old_status: str
    new_status: str
    message: str


# ============ Helper Functions ============

async def _verify_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> ProjectMemberRole | None:
    """验证用户是项目成员，返回角色"""
    result = await db.execute(
        select(project_members.c.role).where(
            and_(
                project_members.c.project_id == project_id,
                project_members.c.user_id == user_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def _get_chapter_with_lock_info(
    chapter_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[Chapter | None, User | None]:
    """
    获取章节并检查锁定状态

    Returns:
        tuple: (chapter, locked_by_user)
    """
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()

    if not chapter:
        return None, None

    locked_by_user = None
    if chapter.locked_by:
        user_result = await db.execute(
            select(User).where(User.id == chapter.locked_by)
        )
        locked_by_user = user_result.scalar_one_or_none()

    return chapter, locked_by_user


def _is_lock_expired(chapter: Chapter) -> bool:
    """检查锁定是否已过期（30 分钟）"""
    if not chapter.locked_at:
        return True

    now = datetime.now(timezone.utc)
    # 确保 locked_at 有时区信息
    locked_at = chapter.locked_at
    if locked_at.tzinfo is None:
        locked_at = locked_at.replace(tzinfo=timezone.utc)

    expiry_time = locked_at + timedelta(minutes=LOCK_TIMEOUT_MINUTES)
    return now > expiry_time


async def _check_edit_permission(
    chapter: Chapter,
    current_user: User,
    db: AsyncSession,
) -> tuple[bool, str, User | None]:
    """
    检查用户是否可以编辑章节

    Returns:
        tuple: (can_edit, error_message, locked_by_user)
    """
    # 检查项目成员资格
    role = await _verify_project_member(chapter.project_id, current_user.id, db)
    if role is None:
        return False, "您不是该项目的成员", None

    # 检查角色权限（reviewer 不能编辑）
    if role == ProjectMemberRole.REVIEWER:
        return False, "Reviewer 角色没有编辑权限", None

    # 获取锁定者信息
    _, locked_by_user = await _get_chapter_with_lock_info(chapter.id, db)

    # 检查锁定状态
    if chapter.locked_by and not _is_lock_expired(chapter):
        # 如果是锁定者本人，允许编辑
        if chapter.locked_by == current_user.id:
            return True, "", locked_by_user
        # 其他人不能编辑
        locker_name = locked_by_user.username if locked_by_user else "未知用户"
        return False, f"章节已被 {locker_name} 锁定", locked_by_user

    return True, "", locked_by_user


# ============ API Endpoints ============

@router.post("/{chapter_id}/lock", response_model=LockResponse)
async def lock_chapter(
    chapter_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    锁定章节

    - 设置 locked_by 和 locked_at
    - 如果已锁定且未过期，返回 409 Conflict
    - 如果锁已过期，自动解锁后重新锁定
    """
    # 获取章节
    chapter, locked_by_user = await _get_chapter_with_lock_info(chapter_id, db)

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )

    # 验证项目成员资格
    role = await _verify_project_member(chapter.project_id, current_user.id, db)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是该项目的成员",
        )

    # Reviewer 不能锁定
    if role == ProjectMemberRole.REVIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer 角色没有锁定权限",
        )

    # 检查当前锁定状态
    if chapter.locked_by and not _is_lock_expired(chapter):
        # 已被锁定且未过期
        if chapter.locked_by != current_user.id:
            locker_name = locked_by_user.username if locked_by_user else "未知用户"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"章节已被 {locker_name} 锁定",
                headers={
                    "X-Locked-By": str(chapter.locked_by),
                    "X-Locked-At": chapter.locked_at.isoformat() if chapter.locked_at else "",
                    "X-Locked-By-Username": locker_name,
                },
            )
        # 锁定者重复锁定，刷新锁定时间
        chapter.locked_at = datetime.now(timezone.utc)
        await db.flush()

        return LockResponse(
            success=True,
            chapter_id=str(chapter.id),
            locked_by=str(current_user.id),
            locked_at=chapter.locked_at.isoformat(),
            locked_by_username=current_user.username,
            message="锁定时间已刷新",
        )

    # 锁定章节
    chapter.locked_by = current_user.id
    chapter.locked_at = datetime.now(timezone.utc)
    await db.flush()

    return LockResponse(
        success=True,
        chapter_id=str(chapter.id),
        locked_by=str(current_user.id),
        locked_at=chapter.locked_at.isoformat(),
        locked_by_username=current_user.username,
        message="章节锁定成功",
    )


@router.post("/{chapter_id}/unlock", response_model=LockResponse)
async def unlock_chapter(
    chapter_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    解锁章节

    - 只有锁定者本人或 Owner/Admin 角色可以解锁
    - 如果未锁定，返回成功
    """
    # 获取章节
    chapter, locked_by_user = await _get_chapter_with_lock_info(chapter_id, db)

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )

    # 验证项目成员资格
    role = await _verify_project_member(chapter.project_id, current_user.id, db)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是该项目的成员",
        )

    # 如果未锁定，直接返回成功
    if not chapter.locked_by:
        return LockResponse(
            success=True,
            chapter_id=str(chapter.id),
            message="章节未被锁定",
        )

    # 检查解锁权限：锁定者本人 或 Owner
    is_locker = chapter.locked_by == current_user.id
    is_owner = role == ProjectMemberRole.OWNER

    if not is_locker and not is_owner:
        locker_name = locked_by_user.username if locked_by_user else "未知用户"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"只有锁定者 ({locker_name}) 或项目 Owner 可以解锁",
        )

    # 解锁
    chapter.locked_by = None
    chapter.locked_at = None
    await db.flush()

    return LockResponse(
        success=True,
        chapter_id=str(chapter.id),
        message="章节解锁成功",
    )


@router.put("/{chapter_id}/content", response_model=ChapterContentResponse)
async def update_chapter_content(
    chapter_id: uuid.UUID,
    request: ChapterContentUpdateRequest,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    保存章节内容

    - 需要先锁定章节（或锁已过期）
    - 保存内容后自动创建版本快照
    - 更新章节状态为 GENERATED
    """
    # 获取章节
    chapter, locked_by_user = await _get_chapter_with_lock_info(chapter_id, db)

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )

    # 检查编辑权限
    can_edit, error_message, _ = await _check_edit_permission(chapter, current_user, db)

    if not can_edit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_message,
        )

    # 如果章节未锁定或锁已过期，自动为当前用户锁定
    if not chapter.locked_by or _is_lock_expired(chapter):
        chapter.locked_by = current_user.id
        chapter.locked_at = datetime.now(timezone.utc)

    # 更新内容
    old_content = chapter.content
    chapter.content = request.content
    chapter.status = ChapterStatus.GENERATED
    chapter.updated_at = datetime.now(timezone.utc)

    # 创建版本快照
    version_service = VersionService(db)
    snapshot_data = {
        "chapter_id": str(chapter.id),
        "chapter_number": chapter.chapter_number,
        "title": chapter.title,
        "old_content": old_content,
        "new_content": request.content,
    }

    await version_service.create_version(
        project_id=chapter.project_id,
        chapter_id=chapter.id,
        user_id=current_user.id,
        change_type=ChangeType.MANUAL_EDIT,
        snapshot_data=snapshot_data,
        change_summary=request.change_summary or f"手动编辑章节: {chapter.chapter_number} {chapter.title}",
    )

    await db.flush()

    # 获取锁定者用户名
    locker_username = None
    if chapter.locked_by:
        if chapter.locked_by == current_user.id:
            locker_username = current_user.username
        elif locked_by_user:
            locker_username = locked_by_user.username

    return ChapterContentResponse(
        id=str(chapter.id),
        chapter_number=chapter.chapter_number,
        title=chapter.title,
        content=chapter.content,
        status=chapter.status.value,
        locked_by=str(chapter.locked_by) if chapter.locked_by else None,
        locked_at=chapter.locked_at.isoformat() if chapter.locked_at else None,
        locked_by_username=locker_username,
        is_locked=chapter.locked_by is not None,
        lock_expired=_is_lock_expired(chapter) if chapter.locked_by else False,
    )


@router.get("/{chapter_id}", response_model=ChapterContentResponse)
async def get_chapter(
    chapter_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    获取章节详情

    - 返回章节内容和锁定状态
    - 查询时检查锁定是否过期
    """
    # 获取章节
    chapter, locked_by_user = await _get_chapter_with_lock_info(chapter_id, db)

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )

    # 验证项目成员资格
    role = await _verify_project_member(chapter.project_id, current_user.id, db)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是该项目的成员",
        )

    # 检查锁定是否过期
    lock_expired = False
    if chapter.locked_by:
        lock_expired = _is_lock_expired(chapter)
        # 如果锁已过期，清除锁定状态
        if lock_expired:
            chapter.locked_by = None
            chapter.locked_at = None
            await db.flush()
            locked_by_user = None

    # 获取锁定者用户名
    locker_username = None
    if chapter.locked_by:
        if chapter.locked_by == current_user.id:
            locker_username = current_user.username
        elif locked_by_user:
            locker_username = locked_by_user.username

    return ChapterContentResponse(
        id=str(chapter.id),
        chapter_number=chapter.chapter_number,
        title=chapter.title,
        content=chapter.content,
        status=chapter.status.value,
        locked_by=str(chapter.locked_by) if chapter.locked_by else None,
        locked_at=chapter.locked_at.isoformat() if chapter.locked_at else None,
        locked_by_username=locker_username,
        is_locked=chapter.locked_by is not None,
        lock_expired=lock_expired,
    )


# ============ 状态流转 API ============

# 定义允许的状态转换规则
# 格式: {当前状态: {目标状态: [允许的项目角色列表]}}
STATUS_TRANSITIONS: dict[ChapterStatus, dict[ChapterStatus, list[ProjectMemberRole]]] = {
    ChapterStatus.PENDING: {
        ChapterStatus.GENERATED: [ProjectMemberRole.OWNER, ProjectMemberRole.EDITOR],
    },
    ChapterStatus.GENERATED: {
        ChapterStatus.REVIEWING: [ProjectMemberRole.OWNER, ProjectMemberRole.EDITOR],
    },
    ChapterStatus.REVIEWING: {
        ChapterStatus.FINALIZED: [ProjectMemberRole.OWNER, ProjectMemberRole.REVIEWER],
        ChapterStatus.GENERATED: [ProjectMemberRole.OWNER, ProjectMemberRole.REVIEWER],  # 打回
    },
    ChapterStatus.FINALIZED: {
        # finalized 状态不能再变更，除非是 admin
    },
}


def _validate_status_transition(
    current_status: ChapterStatus,
    target_status: ChapterStatus,
    project_role: ProjectMemberRole,
    user_global_role: UserRole,
) -> tuple[bool, str]:
    """
    验证状态转换是否合法

    Returns:
        tuple: (is_valid, error_message)
    """
    # 全局 Admin 可以任意转换状态
    if user_global_role == UserRole.ADMIN:
        return True, ""

    # 检查是否是有效的转换
    if current_status not in STATUS_TRANSITIONS:
        return False, f"当前状态 {current_status.value} 不允许变更"

    allowed_transitions = STATUS_TRANSITIONS[current_status]
    if target_status not in allowed_transitions:
        return False, f"不允许从 {current_status.value} 转换到 {target_status.value}"

    # 检查角色权限
    allowed_roles = allowed_transitions[target_status]
    if project_role not in allowed_roles:
        roles_str = "、".join(r.value for r in allowed_roles)
        return False, f"当前角色 ({project_role.value}) 无权执行此状态转换，需要角色：{roles_str}"

    return True, ""


@router.put("/{chapter_id}/status", response_model=StatusUpdateResponse)
async def update_chapter_status(
    chapter_id: uuid.UUID,
    request: StatusUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    更新章节状态

    状态流转规则：
    - pending -> generated: editor/owner
    - generated -> reviewing: editor/owner
    - reviewing -> finalized: reviewer/owner
    - reviewing -> generated: reviewer/owner (打回)
    - admin 可以任意转换状态
    """
    # 获取章节
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )

    # 验证项目成员资格
    project_role = await _verify_project_member(chapter.project_id, current_user.id, db)
    if project_role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是该项目的成员",
        )

    # 验证状态转换
    old_status = chapter.status
    new_status = request.status

    is_valid, error_message = _validate_status_transition(
        old_status, new_status, project_role, current_user.role
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_message,
        )

    # 更新状态
    chapter.status = new_status
    chapter.updated_at = datetime.now(timezone.utc)

    # 记录操作日志
    log_entry = OperationLog(
        user_id=current_user.id,
        project_id=chapter.project_id,
        action=ActionType.CHAPTER_STATUS_CHANGE,
        detail={
            "chapter_id": str(chapter.id),
            "chapter_number": chapter.chapter_number,
            "chapter_title": chapter.title,
            "old_status": old_status.value,
            "new_status": new_status.value,
        },
    )
    db.add(log_entry)

    await db.flush()

    return StatusUpdateResponse(
        id=str(chapter.id),
        chapter_number=chapter.chapter_number,
        title=chapter.title,
        old_status=old_status.value,
        new_status=new_status.value,
        message=f"章节状态已从 {old_status.value} 更新为 {new_status.value}",
    )


# ============ 校对 API Schemas ============

class ProofreadIssueItem(BaseModel):
    """单个校对问题"""
    severity: str = Field(..., description="严重程度: critical/warning/info")
    category: str = Field(..., description="问题类别: compliance/language/consistency/redundancy")
    position: str = Field(..., description="问题所在位置描述")
    issue: str = Field(..., description="问题描述")
    suggestion: str = Field(..., description="修改建议")


class ProofreadResultData(BaseModel):
    """校对结果数据"""
    issues: list[ProofreadIssueItem] = Field(default_factory=list, description="问题列表")
    summary: str = Field(default="", description="整体问题摘要")


class ProofreadResponse(BaseModel):
    """校对响应"""
    id: str
    chapter_id: str
    project_id: str
    issues: list[ProofreadIssueItem]
    summary: str
    issue_count: int
    critical_count: int
    status_changed: bool = Field(..., description="章节状态是否已变为 reviewing")
    created_at: str


# ============ 校对 API Endpoint ============

@router.post("/{chapter_id}/proofread")
async def proofread_chapter(
    chapter_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    触发章节校对（流式返回结果）

    - 使用 AI 对章节内容进行合规性检查和语言质量校对
    - 校对结果保存到数据库
    - 校对完成后章节状态自动变为 reviewing
    - 返回 SSE 流式响应
    """
    # 获取章节
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )

    # 验证项目成员资格
    role = await _verify_project_member(chapter.project_id, current_user.id, db)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是该项目的成员",
        )

    # 检查章节是否有内容
    if not chapter.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="章节内容为空，无法校对",
        )

    # 获取项目信息（包含评分要求）
    project_result = await db.execute(select(Project).where(Project.id == chapter.project_id))
    project = project_result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    # 获取同级章节标题
    sibling_titles = []
    if chapter.parent_id:
        # 有父章节，获取同级章节
        sibling_result = await db.execute(
            select(Chapter.title).where(
                and_(
                    Chapter.parent_id == chapter.parent_id,
                    Chapter.id != chapter_id,
                )
            ).order_by(Chapter.order_index)
        )
        sibling_titles = [row[0] for row in sibling_result.fetchall()]
    elif chapter.parent_id is None:
        # 一级章节，获取其他一级章节
        sibling_result = await db.execute(
            select(Chapter.title).where(
                and_(
                    Chapter.project_id == chapter.project_id,
                    Chapter.parent_id.is_(None),
                    Chapter.id != chapter_id,
                )
            ).order_by(Chapter.order_index)
        )
        sibling_titles = [row[0] for row in sibling_result.fetchall()]

    # 准备校对参数
    tech_requirements = project.tech_requirements or ""
    project_overview = project.project_overview or ""

    async def generate_proofread_stream() -> AsyncGenerator[str, None]:
        """生成流式校对结果"""
        openai_service = OpenAIService(db)
        full_content = ""

        try:
            async for chunk in openai_service.proofread_chapter(
                chapter_title=chapter.title,
                chapter_content=chapter.content,
                tech_requirements=tech_requirements,
                sibling_chapter_titles=sibling_titles,
                project_overview=project_overview,
            ):
                full_content += chunk
                # 发送 SSE 事件
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

            # 解析校对结果
            try:
                result_data = json.loads(full_content.strip())
                issues = result_data.get("issues", [])
                summary = result_data.get("summary", "")
            except json.JSONDecodeError:
                issues = []
                summary = "校对结果解析失败"
                full_content = json.dumps({"issues": [], "summary": summary}, ensure_ascii=False)

            # 统计问题数量
            issue_count = len(issues)
            critical_count = sum(1 for i in issues if i.get("severity") == "critical")

            # 保存校对结果到数据库
            proofread_result = ProofreadResult(
                chapter_id=chapter.id,
                project_id=chapter.project_id,
                issues=json.dumps(issues, ensure_ascii=False),
                summary=summary,
                issue_count=issue_count,
                critical_count=critical_count,
            )
            db.add(proofread_result)

            # 更新章节状态为 reviewing
            old_status = chapter.status
            status_changed = False
            if chapter.status != ChapterStatus.REVIEWING:
                chapter.status = ChapterStatus.REVIEWING
                chapter.updated_at = datetime.now(timezone.utc)
                status_changed = True

            # 记录操作日志
            log_entry = OperationLog(
                user_id=current_user.id,
                project_id=chapter.project_id,
                action=ActionType.AI_PROOFREAD,
                detail={
                    "chapter_id": str(chapter.id),
                    "chapter_number": chapter.chapter_number,
                    "chapter_title": chapter.title,
                    "issue_count": issue_count,
                    "critical_count": critical_count,
                    "status_changed": status_changed,
                    "old_status": old_status.value if status_changed else None,
                    "new_status": ChapterStatus.REVIEWING.value if status_changed else None,
                },
            )
            db.add(log_entry)

            await db.commit()

            # 发送最终结果
            final_result = {
                "done": True,
                "result": {
                    "id": str(proofread_result.id),
                    "chapter_id": str(chapter.id),
                    "project_id": str(chapter.project_id),
                    "issues": issues,
                    "summary": summary,
                    "issue_count": issue_count,
                    "critical_count": critical_count,
                    "status_changed": status_changed,
                    "created_at": proofread_result.created_at.isoformat(),
                }
            }
            yield f"data: {json.dumps(final_result, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_proofread_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
