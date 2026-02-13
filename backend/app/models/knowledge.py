"""知识库文档 ORM 模型"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User


class DocType(str, enum.Enum):
    """文档类型"""
    QUALIFICATION = "qualification"  # 企业资质
    CASE = "case"                    # 成功案例
    TECHNICAL = "technical"          # 技术方案
    OTHER = "other"                  # 其他


class EmbeddingStatus(str, enum.Enum):
    """向量化状态（MVP 阶段暂不使用向量数据库）"""
    PENDING = "pending"      # 待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败


class KnowledgeDoc(Base):
    """知识库文档表 - 存储企业上传的参考资料"""
    __tablename__ = "knowledge_docs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="文档名称"
    )
    doc_type: Mapped[DocType] = mapped_column(
        SQLEnum(DocType), nullable=False, default=DocType.OTHER,
        comment="文档类型"
    )
    # 存储提取的文本分块，格式: [{"chunk_id": 1, "text": "...", "keywords": [...]}, ...]
    content_chunks: Mapped[list | None] = mapped_column(
        JSONB, nullable=True,
        comment="文本分块数据（JSONB）"
    )
    # 用于 TF-IDF 检索的词频统计
    tfidf_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="TF-IDF 相关数据（JSONB）"
    )
    embedding_status: Mapped[EmbeddingStatus] = mapped_column(
        SQLEnum(EmbeddingStatus), nullable=False, default=EmbeddingStatus.PENDING,
        comment="向量化状态"
    )
    original_file_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="原始文件名"
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="上传者ID"
    )
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
        return f"<KnowledgeDoc {self.name}>"
