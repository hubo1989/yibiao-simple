"""知识库文档 ORM 模型"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User


class DocType(str, enum.Enum):
    """文档类型"""
    HISTORY_BID = "history_bid"      # 历史标书
    COMPANY_INFO = "company_info"    # 企业资料
    CASE_FRAGMENT = "case_fragment"  # 案例片段
    OTHER = "other"                  # 其他


class ContentSource(str, enum.Enum):
    """内容来源"""
    FILE = "file"      # 文件上传
    MANUAL = "manual"  # 手动输入


class IndexStatus(str, enum.Enum):
    """PageIndex 索引状态"""
    PENDING = "pending"      # 待处理
    INDEXING = "indexing"    # 索引中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败


# Alias for backward compatibility
EmbeddingStatus = IndexStatus


class Scope(str, enum.Enum):
    """数据范围"""
    GLOBAL = "global"          # 全局
    ENTERPRISE = "enterprise"  # 企业私有
    USER = "user"              # 用户私有


class KnowledgeDoc(Base):
    """知识库文档表 - 存储企业上传的参考资料"""
    __tablename__ = "knowledge_docs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True,
        comment="名称（与title相同，兼容旧字段）"
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True,
        comment="标题"
    )
    doc_type: Mapped[DocType] = mapped_column(
        SQLEnum(DocType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False, default=DocType.OTHER,
        comment="文档类型"
    )
    scope: Mapped[Scope] = mapped_column(
        SQLEnum(Scope, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False, default=Scope.USER,
        comment="数据范围"
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="所有者ID（企业或用户）"
    )
    
    # 内容
    content_source: Mapped[ContentSource] = mapped_column(
        SQLEnum(ContentSource, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False, default=ContentSource.FILE,
        comment="内容来源"
    )
    content: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="手动输入的内容"
    )
    file_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="文件路径"
    )
    file_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="文件类型（pdf/docx）"
    )
    
    # PageIndex 索引
    pageindex_tree: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="PageIndex 树状索引"
    )
    pageindex_status: Mapped[IndexStatus] = mapped_column(
        SQLEnum(IndexStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False, default=IndexStatus.PENDING,
        comment="PageIndex 索引状态"
    )
    pageindex_error: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="索引失败的错误信息"
    )

    # 向量索引状态
    vector_index_status: Mapped[str | None] = mapped_column(
        String(20), nullable=False, server_default="pending",
        comment="向量索引状态: pending/indexing/completed/failed"
    )
    vector_index_error: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="向量索引错误信息"
    )

    # LlamaIndex 后端标记
    index_backend: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="llamaindex",
        comment="索引后端: llamaindex"
    )
    index_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1",
        comment="索引版本号"
    )

    # 元数据
    tags: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=list,
        comment="标签列表"
    )
    keywords: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=list,
        comment="关键词列表"
    )
    category: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="分类"
    )
    
    # 统计
    usage_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="使用次数"
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="最后使用时间"
    )
    
    # 旧字段（保留以兼容）
    original_file_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="原始文件名（已废弃，使用 file_path）"
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="上传者ID"
    )
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 关系
    uploader: Mapped["User | None"] = relationship(
        "User", foreign_keys=[uploaded_by], backref="uploaded_knowledge_docs"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDoc {self.title}>"


class ProjectKnowledgeUsage(Base):
    """知识库使用记录表"""
    __tablename__ = "project_knowledge_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
        comment="项目ID"
    )
    knowledge_doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_docs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="知识库文档ID"
    )
    chapter_id: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="章节ID"
    )
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        comment="使用时间"
    )

    # 关系
    knowledge_doc: Mapped["KnowledgeDoc"] = relationship(
        "KnowledgeDoc", backref="usage_records"
    )

    def __repr__(self) -> str:
        return f"<ProjectKnowledgeUsage project={self.project_id} doc={self.knowledge_doc_id}>"


class KnowledgeDocChunk(Base):
    """知识库文档分块表 - 存储向量嵌入的分块"""
    __tablename__ = "knowledge_doc_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_docs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属文档ID"
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="分块序号"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="分块内容"
    )
    embedding: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="向量嵌入（pgvector 存储）"
    )
    chunk_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True,
        comment="元数据"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 关系
    knowledge_doc: Mapped["KnowledgeDoc"] = relationship(
        "KnowledgeDoc", backref="chunks"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocChunk doc={self.doc_id} idx={self.chunk_index}>"
