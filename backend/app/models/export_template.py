"""导出格式模板 ORM 模型"""
import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class ExportTemplate(Base):
    """导出格式模板表"""
    __tablename__ = "export_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    format_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        comment="格式配置 JSON：font/spacing/margin/page/cover/toc"
    )
    source_file_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="AI 提取来源文件路径（可选）"
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
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<ExportTemplate {self.name} builtin={self.is_builtin}>"
