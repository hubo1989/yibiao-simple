"""模板 ORM 模型"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User
    from .project import Project


class Template(Base):
    """模板表 - 保存标书模板用于复用"""
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="模板名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="模板描述"
    )
    outline_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="目录结构数据 (JSONB)"
    )
    source_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="来源项目ID"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="创建者ID"
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
    source_project: Mapped["Project | None"] = relationship(
        "Project", foreign_keys=[source_project_id], backref="templates"
    )
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], backref="created_templates"
    )

    def __repr__(self) -> str:
        return f"<Template {self.name}>"
