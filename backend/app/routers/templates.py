"""模板 CRUD API 路由"""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.database import get_db
from ..models.user import User, UserRole
from ..models.project import Project, ProjectStatus, ProjectMemberRole, project_members
from ..models.chapter import Chapter
from ..models.template import Template
from ..schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateSummary,
    ProjectFromTemplateCreate,
)
from ..schemas.project import ProjectResponse
from ..auth.dependencies import get_current_active_user, require_editor

router = APIRouter(prefix="/api/templates", tags=["模板"])


def build_chapter_tree(chapters: list[Chapter]) -> list[dict]:
    """将章节列表转换为树形结构字典"""
    # 按父ID分组
    children_by_parent: dict[uuid.UUID | None, list[Chapter]] = {}
    for ch in chapters:
        parent_id = ch.parent_id
        if parent_id not in children_by_parent:
            children_by_parent[parent_id] = []
        children_by_parent[parent_id].append(ch)

    def build_node(chapter: Chapter) -> dict:
        """递归构建节点"""
        node = {
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "order_index": chapter.order_index,
        }
        children = children_by_parent.get(chapter.id, [])
        if children:
            node["children"] = [
                build_node(child)
                for child in sorted(children, key=lambda x: x.order_index)
            ]
        return node

    # 获取根章节
    root_chapters = children_by_parent.get(None, [])
    return [build_node(ch) for ch in sorted(root_chapters, key=lambda x: x.order_index)]


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """创建模板（需要 Editor 或更高角色）"""
    outline_data = None
    source_project_id = data.source_project_id

    # 如果提供了来源项目ID，从项目复制目录结构
    if source_project_id:
        # 验证用户有权访问该项目
        member_exists = await db.execute(
            select(project_members.c.user_id).where(
                project_members.c.project_id == source_project_id,
                project_members.c.user_id == current_user.id,
            )
        )
        if not member_exists.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="来源项目不存在或您没有访问权限",
            )

        # 获取项目的所有章节
        result = await db.execute(
            select(Chapter)
            .where(Chapter.project_id == source_project_id)
            .order_by(Chapter.order_index)
        )
        chapters = list(result.scalars().all())

        if chapters:
            outline_data = build_chapter_tree(chapters)

    # 创建模板
    new_template = Template(
        name=data.name,
        description=data.description,
        outline_data=outline_data,
        source_project_id=source_project_id,
        created_by=current_user.id,
    )
    db.add(new_template)
    await db.flush()
    await db.refresh(new_template)

    return new_template


@router.get("", response_model=list[TemplateSummary])
async def list_templates(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取模板列表"""
    result = await db.execute(
        select(Template).order_by(Template.created_at.desc()).offset(skip).limit(limit)
    )
    templates = result.scalars().all()
    return templates


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取模板详情"""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在",
        )
    return template


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """更新模板（仅创建者或管理员）"""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在",
        )

    if template.created_by != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有模板创建者或管理员才能更新模板",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    await db.flush()
    await db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """删除模板（仅创建者或管理员）"""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在",
        )

    if template.created_by != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有模板创建者或管理员才能删除模板",
        )

    await db.delete(template)


@router.post(
    "/{template_id}/create-project",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_from_template(
    template_id: uuid.UUID,
    data: ProjectFromTemplateCreate,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """基于模板创建新项目（复制目录结构）"""
    # 获取模板
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在",
        )

    # 创建新项目
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

    # 从模板复制目录结构
    if template.outline_data and isinstance(template.outline_data, list):
        await create_chapters_from_outline(
            db=db,
            project_id=new_project.id,
            outline_nodes=template.outline_data,
            parent_id=None,
        )
        await db.flush()

    await db.refresh(new_project)
    return new_project


async def create_chapters_from_outline(
    db: AsyncSession,
    project_id: uuid.UUID,
    outline_nodes: list[dict],
    parent_id: uuid.UUID | None,
) -> None:
    """递归创建章节"""
    from ..models.chapter import Chapter, ChapterStatus

    for node in outline_nodes:
        chapter = Chapter(
            project_id=project_id,
            parent_id=parent_id,
            chapter_number=node.get("chapter_number", ""),
            title=node.get("title", ""),
            order_index=node.get("order_index", 0),
            status=ChapterStatus.PENDING,
        )
        db.add(chapter)
        await db.flush()
        await db.refresh(chapter)

        # 递归创建子章节
        children = node.get("children", [])
        if children:
            await create_chapters_from_outline(
                db=db,
                project_id=project_id,
                outline_nodes=children,
                parent_id=chapter.id,
            )
