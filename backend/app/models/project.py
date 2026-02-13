"""项目 ORM 模型"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Text, DateTime, ForeignKey, Table, Column, func, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class ProjectStatus(str, PyEnum):
    """项目状态枚举"""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEWING = "reviewing"
    COMPLETED = "completed"


class ProjectMemberRole(str, PyEnum):
    """项目成员角色枚举"""
    OWNER = "owner"
    EDITOR = "editor"
    REVIEWER = "reviewer"


# 项目成员关联表
project_members = Table(
    "project_members",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("project_id", UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("role", Enum(ProjectMemberRole, name="project_member_role", native_enum=False, length=20), nullable=False, default=ProjectMemberRole.EDITOR),
    Column("joined_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


class Project(Base):
    """项目表"""
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", native_enum=False, length=20),
        nullable=False,
        default=ProjectStatus.DRAFT,
    )
    file_content: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    project_overview: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    tech_requirements: Mapped[str | None] = mapped_column(
        Text, nullable=True
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
    creator = relationship("User", foreign_keys=[creator_id], backref="created_projects")
    members = relationship("User", secondary=project_members, backref="projects")

    def __repr__(self) -> str:
        return f"<Project {self.name}>"
