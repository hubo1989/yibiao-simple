"""章节模板（标书知识库）API 路由"""
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.chapter_template import ChapterTemplate
from ..models.chapter import Chapter
from ..models.project import Project
from ..models.user import User
from ..auth.dependencies import require_editor, get_current_active_user

router = APIRouter(prefix="/api/chapter-templates", tags=["章节模板（标书知识库）"])


# ============ Schemas ============

class ChapterTemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    content: str
    source_project_id: Optional[str] = None
    source_project_name: Optional[str] = None
    source_chapter_id: Optional[str] = None
    created_by: str
    usage_count: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ChapterTemplateCreate(BaseModel):
    name: str = Field(..., max_length=200, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    category: Optional[str] = Field(None, max_length=50, description="分类")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    content: str = Field(..., description="章节内容（Markdown）")


class ChapterTemplateFromChapter(BaseModel):
    chapter_id: str = Field(..., description="来源章节 ID")
    name: Optional[str] = Field(None, max_length=200, description="模板名称（留空则使用章节标题）")
    category: Optional[str] = Field(None, max_length=50, description="分类")
    tags: list[str] = Field(default_factory=list, description="标签列表")


class ChapterTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    tags: Optional[list[str]] = None
    content: Optional[str] = None


class ChapterTemplateApply(BaseModel):
    target_chapter_id: str = Field(..., description="目标章节 ID（数据库 UUID）")


class ChapterTemplateSearch(BaseModel):
    query: str = Field(..., description="搜索关键词（通常为章节标题）")


def _to_response(tpl: ChapterTemplate) -> ChapterTemplateResponse:
    return ChapterTemplateResponse(
        id=str(tpl.id),
        name=tpl.name,
        description=tpl.description,
        category=tpl.category,
        tags=tpl.tags or [],
        content=tpl.content,
        source_project_id=str(tpl.source_project_id) if tpl.source_project_id else None,
        source_project_name=tpl.source_project_name,
        source_chapter_id=str(tpl.source_chapter_id) if tpl.source_chapter_id else None,
        created_by=str(tpl.created_by),
        usage_count=tpl.usage_count,
        created_at=tpl.created_at.isoformat(),
        updated_at=tpl.updated_at.isoformat(),
    )


# ============ Endpoints ============

@router.get("", response_model=list[ChapterTemplateResponse])
async def list_templates(
    category: Optional[str] = Query(None, description="按分类筛选"),
    keyword: Optional[str] = Query(None, description="按名称/描述关键词搜索"),
    tags: Optional[str] = Query(None, description="按标签筛选（逗号分隔）"),
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """获取章节模板列表，支持分类、标签、关键词筛选"""
    query = select(ChapterTemplate).order_by(ChapterTemplate.created_at.desc())

    if category:
        query = query.where(ChapterTemplate.category == category)

    if keyword:
        query = query.where(
            or_(
                ChapterTemplate.name.ilike(f"%{keyword}%"),
                ChapterTemplate.description.ilike(f"%{keyword}%"),
            )
        )

    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        for tag in tag_list:
            query = query.where(ChapterTemplate.tags.contains([tag]))

    result = await db.execute(query)
    templates = result.scalars().all()
    return [_to_response(t) for t in templates]


@router.get("/{template_id}", response_model=ChapterTemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """获取章节模板详情"""
    result = await db.execute(
        select(ChapterTemplate).where(ChapterTemplate.id == template_id)
    )
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    return _to_response(tpl)


@router.post("", response_model=ChapterTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: ChapterTemplateCreate,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """手动创建章节模板"""
    tpl = ChapterTemplate(
        name=data.name,
        description=data.description,
        category=data.category,
        tags=data.tags,
        content=data.content,
        created_by=current_user.id,
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return _to_response(tpl)


@router.post("/from-chapter", response_model=ChapterTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template_from_chapter(
    data: ChapterTemplateFromChapter,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """从现有章节创建模板"""
    # 查找章节
    try:
        chapter_uuid = uuid.UUID(data.chapter_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的章节 ID")

    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_uuid)
    )
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

    if not chapter.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="章节内容为空，无法保存为模板",
        )

    # 获取来源项目名
    source_project_name: str | None = None
    project_result = await db.execute(
        select(Project).where(Project.id == chapter.project_id)
    )
    project = project_result.scalar_one_or_none()
    if project:
        source_project_name = project.name

    tpl = ChapterTemplate(
        name=data.name or f"{chapter.chapter_number} {chapter.title}",
        description=None,
        category=data.category,
        tags=data.tags,
        content=chapter.content,
        source_project_id=chapter.project_id,
        source_chapter_id=chapter.id,
        source_project_name=source_project_name,
        created_by=current_user.id,
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return _to_response(tpl)


@router.put("/{template_id}", response_model=ChapterTemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    data: ChapterTemplateUpdate,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """编辑章节模板"""
    result = await db.execute(
        select(ChapterTemplate).where(ChapterTemplate.id == template_id)
    )
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")

    if data.name is not None:
        tpl.name = data.name
    if data.description is not None:
        tpl.description = data.description
    if data.category is not None:
        tpl.category = data.category
    if data.tags is not None:
        tpl.tags = data.tags
    if data.content is not None:
        tpl.content = data.content

    tpl.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(tpl)
    return _to_response(tpl)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """删除章节模板"""
    result = await db.execute(
        select(ChapterTemplate).where(ChapterTemplate.id == template_id)
    )
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")

    await db.delete(tpl)
    await db.commit()


@router.post("/{template_id}/apply")
async def apply_template(
    template_id: uuid.UUID,
    data: ChapterTemplateApply,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """将模板内容套用到目标章节"""
    # 查找模板
    tpl_result = await db.execute(
        select(ChapterTemplate).where(ChapterTemplate.id == template_id)
    )
    tpl = tpl_result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")

    # 查找目标章节
    try:
        target_uuid = uuid.UUID(data.target_chapter_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的目标章节 ID")

    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == target_uuid)
    )
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标章节不存在")

    # 写入内容
    chapter.content = tpl.content
    chapter.updated_at = datetime.now(timezone.utc)

    # 更新使用次数
    tpl.usage_count = (tpl.usage_count or 0) + 1

    await db.commit()

    return {
        "success": True,
        "message": f"已将模板「{tpl.name}」套用到章节「{chapter.title}」",
        "template_id": str(tpl.id),
        "chapter_id": str(chapter.id),
        "content": tpl.content,
    }


@router.post("/search", response_model=list[ChapterTemplateResponse])
async def search_templates(
    data: ChapterTemplateSearch,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """智能搜索：根据章节标题/关键词推荐相关模板（按名称相似度排序）"""
    keyword = data.query.strip()
    if not keyword:
        # 无关键词则返回最近 20 条
        result = await db.execute(
            select(ChapterTemplate)
            .order_by(ChapterTemplate.usage_count.desc(), ChapterTemplate.created_at.desc())
            .limit(20)
        )
        return [_to_response(t) for t in result.scalars().all()]

    # 多关键词分词搜索
    words = keyword.split()
    query = select(ChapterTemplate)
    conditions = []
    for word in words:
        conditions.append(
            or_(
                ChapterTemplate.name.ilike(f"%{word}%"),
                ChapterTemplate.description.ilike(f"%{word}%"),
                ChapterTemplate.category.ilike(f"%{word}%"),
            )
        )
    if conditions:
        from sqlalchemy import or_ as sa_or_
        # ANY match is fine (OR across words)
        combined = conditions[0]
        for c in conditions[1:]:
            combined = combined | c
        query = query.where(combined)

    query = query.order_by(
        ChapterTemplate.usage_count.desc(),
        ChapterTemplate.created_at.desc(),
    ).limit(20)

    result = await db.execute(query)
    return [_to_response(t) for t in result.scalars().all()]
