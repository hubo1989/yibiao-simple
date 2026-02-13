"""知识库相关 Pydantic schema"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# 文档类型枚举
DocTypeEnum = Literal["qualification", "case", "technical", "other"]


class KnowledgeDocBase(BaseModel):
    """知识库文档基础字段"""
    name: str = Field(..., min_length=1, max_length=255, description="文档名称")
    doc_type: DocTypeEnum = Field("other", description="文档类型")


class KnowledgeDocCreate(KnowledgeDocBase):
    """创建知识库文档请求（上传文件时使用）"""
    pass


class KnowledgeDocUpdate(BaseModel):
    """更新知识库文档请求"""
    name: str | None = Field(None, min_length=1, max_length=255)
    doc_type: DocTypeEnum | None = None


class ContentChunk(BaseModel):
    """文本分块"""
    chunk_id: int = Field(..., description="分块ID")
    text: str = Field(..., description="分块文本内容")
    keywords: list[str] = Field(default_factory=list, description="关键词列表")


class KnowledgeDocResponse(KnowledgeDocBase):
    """知识库文档响应"""
    id: uuid.UUID
    original_file_name: str | None
    embedding_status: str
    uploaded_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeDocDetail(KnowledgeDocResponse):
    """知识库文档详情（包含分块内容）"""
    content_chunks: list[ContentChunk] | None = None

    model_config = {"from_attributes": True}


class KnowledgeDocSummary(BaseModel):
    """知识库文档摘要（列表用）"""
    id: uuid.UUID
    name: str
    doc_type: str
    original_file_name: str | None
    embedding_status: str
    uploaded_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    """知识库搜索请求"""
    query: str = Field(..., min_length=1, max_length=1000, description="搜索关键词")
    doc_types: list[DocTypeEnum] | None = Field(None, description="限制文档类型")
    limit: int = Field(5, ge=1, le=20, description="返回结果数量限制")


class SearchResult(BaseModel):
    """搜索结果"""
    doc_id: uuid.UUID
    doc_name: str
    doc_type: str
    chunk_id: int
    text: str
    score: float = Field(..., description="相关性得分")


class SearchResponse(BaseModel):
    """搜索响应"""
    results: list[SearchResult]
    total: int = Field(..., description="总结果数")
