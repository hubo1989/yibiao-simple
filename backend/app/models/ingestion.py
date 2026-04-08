"""历史标书解析任务相关 ORM 模型"""
import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .knowledge import KnowledgeDoc
    from .user import User


class IngestionTaskStatus(str, enum.Enum):
    """解析任务状态"""
    PENDING = "pending"          # 待处理
    PROCESSING = "processing"    # 处理中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败


class IngestionTask(Base):
    """历史标书解析任务"""
    __tablename__ = "ingestion_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_docs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[IngestionTaskStatus] = mapped_column(
        SQLEnum(IngestionTaskStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=IngestionTaskStatus.PENDING,
        index=True,
    )
    total_candidates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_log: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    document: Mapped["KnowledgeDoc"] = relationship("KnowledgeDoc", backref="ingestion_tasks")
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by], backref="created_ingestion_tasks")


class MaterialCandidate(Base):
    """解析候选素材"""
    __tablename__ = "material_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_page_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_page_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    temp_file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    preview_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_ext: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(20), nullable=False, default="rule")  # rule | llm | hybrid
    confidence_score: Mapped[float | None] = mapped_column(nullable=True)  # 0-1
    ai_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_extracted_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)  # pending | confirmed | rejected
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    task: Mapped["IngestionTask"] = relationship("IngestionTask", backref="candidates")
