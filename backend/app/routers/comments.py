"""评论批注相关 API 路由"""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.comment import Comment
from ..models.chapter import Chapter
from ..models.project import project_members, ProjectMemberRole
from ..models.user import User, UserRole
from ..db.database import get_db
from ..auth.dependencies import require_reviewer

router = APIRouter(prefix="/api", tags=["评论批注管理"])


# ============ Schemas ============

class CommentCreateRequest(BaseModel):
    """创建批注请求"""
    content: str = Field(..., min_length=1, max_length=5000, description="批注内容")
    position_start: int | None = Field(None, ge=0, description="批注起始位置")
    position_end: int | None = Field(None, ge=0, description="批注结束位置")


class CommentUpdateRequest(BaseModel):
    """更新批注请求"""
    content: str = Field(..., min_length=1, max_length=5000, description="批注内容")


class CommentResponse(BaseModel):
    """批注响应"""
    id: str
    chapter_id: str
    user_id: str
    username: str
    content: str
    position_start: int | None
    position_end: int | None
    is_resolved: bool
    resolved_by: str | None = None
    resolved_by_username: str | None = None
    resolved_at: str | None = None
    created_at: str
    updated_at: str


class CommentListResponse(BaseModel):
    """批注列表响应"""
    items: list[CommentResponse]
    total: int


# ============ Helper Functions ============

async def _verify_chapter_access(
    chapter_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[Chapter | None, ProjectMemberRole | None]:
    """
    验证用户是否有章节访问权限

    Returns:
        tuple: (chapter, role) - 章节对象和用户在项目中的角色
    """
    # 获取章节
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = result.scalar_one_or_none()

    if not chapter:
        return None, None

    # 检查项目成员资格
    role = await db.execute(
        select(project_members.c.role).where(
            and_(
                project_members.c.project_id == chapter.project_id,
                project_members.c.user_id == user_id,
            )
        )
    )
    member_role = role.scalar_one_or_none()

    return chapter, member_role


async def _build_comment_response(comment: Comment) -> CommentResponse:
    """构建批注响应对象"""
    resolved_by_username = None
    if comment.resolver:
        resolved_by_username = comment.resolver.username

    return CommentResponse(
        id=str(comment.id),
        chapter_id=str(comment.chapter_id),
        user_id=str(comment.user_id),
        username=comment.user.username,
        content=comment.content,
        position_start=comment.position_start,
        position_end=comment.position_end,
        is_resolved=comment.is_resolved,
        resolved_by=str(comment.resolved_by) if comment.resolved_by else None,
        resolved_by_username=resolved_by_username,
        resolved_at=comment.resolved_at.isoformat() if comment.resolved_at else None,
        created_at=comment.created_at.isoformat(),
        updated_at=comment.updated_at.isoformat(),
    )


# ============ API Endpoints ============

@router.post("/chapters/{chapter_id}/comments", response_model=CommentResponse)
async def create_comment(
    chapter_id: uuid.UUID,
    request: CommentCreateRequest,
    current_user: Annotated[User, Depends(require_reviewer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    添加批注到章节

    - 审阅者和编辑者都可添加批注
    - 需要是项目成员
    """
    # 验证章节访问权限
    chapter, role = await _verify_chapter_access(chapter_id, current_user.id, db)

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是该项目的成员，无法添加批注",
        )

    # 验证位置范围
    if request.position_start is not None and request.position_end is not None:
        if request.position_start > request.position_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="起始位置不能大于结束位置",
            )

    # 创建批注
    comment = Comment(
        chapter_id=chapter_id,
        user_id=current_user.id,
        content=request.content,
        position_start=request.position_start,
        position_end=request.position_end,
        is_resolved=False,
    )

    db.add(comment)
    await db.flush()

    # 重新加载以获取关联的用户信息
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.user))
        .where(Comment.id == comment.id)
    )
    comment = result.scalar_one()

    return await _build_comment_response(comment)


@router.get("/chapters/{chapter_id}/comments", response_model=CommentListResponse)
async def list_chapter_comments(
    chapter_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_reviewer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_resolved: bool = False,
):
    """
    获取章节批注列表

    - 默认只返回未解决的批注
    - 设置 include_resolved=true 返回所有批注
    """
    # 验证章节访问权限
    chapter, role = await _verify_chapter_access(chapter_id, current_user.id, db)

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是该项目的成员",
        )

    # 构建查询
    query = (
        select(Comment)
        .options(
            selectinload(Comment.user),
            selectinload(Comment.resolver),
        )
        .where(Comment.chapter_id == chapter_id)
        .order_by(Comment.created_at.desc())
    )

    if not include_resolved:
        query = query.where(Comment.is_resolved == False)

    result = await db.execute(query)
    comments = result.scalars().all()

    # 构建响应
    items = []
    for comment in comments:
        items.append(await _build_comment_response(comment))

    return CommentListResponse(
        items=items,
        total=len(items),
    )


@router.put("/comments/{comment_id}/resolve", response_model=CommentResponse)
async def resolve_comment(
    comment_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_reviewer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    标记批注为已解决

    - 只有批注作者、项目 Owner 或 Admin 可以解决批注
    - 解决后记录解决者和解决时间
    """
    # 获取批注
    result = await db.execute(
        select(Comment)
        .options(
            selectinload(Comment.user),
            selectinload(Comment.resolver),
            selectinload(Comment.chapter),
        )
        .where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="批注不存在",
        )

    # 验证项目成员资格
    chapter = comment.chapter
    role_result = await db.execute(
        select(project_members.c.role).where(
            and_(
                project_members.c.project_id == chapter.project_id,
                project_members.c.user_id == current_user.id,
            )
        )
    )
    member_role = role_result.scalar_one_or_none()

    if member_role is None and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您不是该项目的成员",
        )

    # 检查解决权限：批注作者、Owner、Admin 或系统管理员
    is_author = comment.user_id == current_user.id
    is_owner = member_role == ProjectMemberRole.OWNER
    is_admin = current_user.role == UserRole.ADMIN

    if not is_author and not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有批注作者、项目 Owner 或 Admin 可以标记批注为已解决",
        )

    # 如果已经解决，返回当前状态
    if comment.is_resolved:
        return await _build_comment_response(comment)

    # 标记为已解决
    comment.is_resolved = True
    comment.resolved_by = current_user.id
    comment.resolved_at = datetime.now(timezone.utc)

    await db.flush()

    # 重新加载以获取解决者信息
    result = await db.execute(
        select(Comment)
        .options(
            selectinload(Comment.user),
            selectinload(Comment.resolver),
        )
        .where(Comment.id == comment.id)
    )
    comment = result.scalar_one()

    return await _build_comment_response(comment)


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_reviewer)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    删除批注

    - 只有批注作者或 Admin 可以删除批注
    """
    # 获取批注
    result = await db.execute(
        select(Comment)
        .options(selectinload(Comment.chapter))
        .where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="批注不存在",
        )

    # 检查删除权限：批注作者或 Admin
    is_author = comment.user_id == current_user.id
    is_admin = current_user.role == UserRole.ADMIN

    if not is_author and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有批注作者或 Admin 可以删除批注",
        )

    # 删除批注
    await db.delete(comment)
    await db.flush()

    return {"success": True, "message": "批注已删除"}
