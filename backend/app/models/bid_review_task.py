"""标书审查任务 ORM 模型"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class ReviewTaskStatus(str, PyEnum):
    """审查任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BidReviewTask(Base):
    """标书审查任务表"""
    __tablename__ = "bid_review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    status: Mapped[ReviewTaskStatus] = mapped_column(
        Enum(ReviewTaskStatus, name="review_task_status", native_enum=False, length=20),
        nullable=False, default=ReviewTaskStatus.PENDING
    )

    # 投标文件信息
    bid_file_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="投标文件磁盘路径"
    )
    bid_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="投标文件原始文件名"
    )
    bid_content: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="投标文件提取文本"
    )
    paragraph_index: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="文档段落索引"
    )

    # 审查配置
    dimensions: Mapped[list] = mapped_column(
        JSONB, nullable=False, comment="审查维度列表"
    )
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="full", comment="审查范围"
    )
    model_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="使用的模型名称"
    )
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_key_configs.id", ondelete="SET NULL"),
        nullable=True
    )

    # 审查结果
    responsiveness_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="响应性审查结果"
    )
    compliance_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="合规性审查结果"
    )
    consistency_result: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="一致性审查结果"
    )
    summary: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="审查汇总"
    )

    # 错误信息
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="失败时的错误信息"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="审查完成时间"
    )

    # 关系
    project = relationship("Project", foreign_keys=[project_id], backref="review_tasks")
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<BidReviewTask {self.id}>"
