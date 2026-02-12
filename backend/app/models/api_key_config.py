"""API Key 配置 ORM 模型"""
import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, func, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class ApiKeyConfig(Base):
    """API Key 配置表"""
    __tablename__ = "api_key_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="提供商名称，如 openai, anthropic"
    )
    api_key_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False, comment="加密后的 API Key"
    )
    base_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="API 基础 URL"
    )
    model_name: Mapped[str] = mapped_column(
        String(128), nullable=False, default="gpt-3.5-turbo", comment="默认模型名称"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否为默认配置"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建者 ID"
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

    def __repr__(self) -> str:
        return f"<ApiKeyConfig {self.provider}>"
