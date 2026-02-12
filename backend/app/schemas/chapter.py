"""章节相关 Pydantic schema"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from ..models.chapter import ChapterStatus


class ChapterBase(BaseModel):
    """章节基础字段"""
    chapter_number: str = Field(..., min_length=1, max_length=50, description="章节编号，如 1.2.3")
    title: str = Field(..., min_length=1, max_length=500, description="章节标题")


class ChapterCreate(ChapterBase):
    """创建章节请求"""
    project_id: uuid.UUID = Field(..., description="所属项目 ID")
    parent_id: uuid.UUID | None = Field(None, description="父章节 ID")
    order_index: int = Field(default=0, ge=0, description="排序索引")


class ChapterUpdate(BaseModel):
    """更新章节请求（所有字段可选）"""
    chapter_number: str | None = Field(None, min_length=1, max_length=50)
    title: str | None = Field(None, min_length=1, max_length=500)
    content: str | None = None
    status: ChapterStatus | None = None
    order_index: int | None = Field(None, ge=0)
    locked_by: uuid.UUID | None = None
    locked_at: datetime | None = None


class ChapterLockRequest(BaseModel):
    """章节锁定/解锁请求"""
    lock: bool = Field(..., description="True 为锁定，False 为解锁")


class ChapterResponse(ChapterBase):
    """章节响应"""
    id: uuid.UUID
    project_id: uuid.UUID
    parent_id: uuid.UUID | None
    content: str | None
    status: ChapterStatus
    order_index: int
    locked_by: uuid.UUID | None
    locked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterSummary(BaseModel):
    """章节摘要（列表/树形结构用，不含大内容字段）"""
    id: uuid.UUID
    project_id: uuid.UUID
    parent_id: uuid.UUID | None
    chapter_number: str
    title: str
    status: ChapterStatus
    order_index: int
    locked_by: uuid.UUID | None

    model_config = {"from_attributes": True}


class ChapterTree(ChapterSummary):
    """章节树形结构（包含子章节）"""
    children: list["ChapterTree"] = []

    model_config = {"from_attributes": True}


# 解决自引用模型的 forward reference
ChapterTree.model_rebuild()
