"""版本快照 ORM 模型"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    func,
    Enum,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User
    from .project import Project
    from .chapter import Chapter


class ChangeType(str, PyEnum):
    """变更类型枚举"""

    AI_GENERATE = "ai_generate"  # AI 生成
    MANUAL_EDIT = "manual_edit"  # 手动编辑
    PROOFREAD = "proofread"  # 校对
    ROLLBACK = "rollback"  # 回滚


class ProjectVersion(Base):
    """版本快照表 - 跟踪内容变更历史"""

    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_project_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联章节 ID（全量快照时为空）",
    )
    version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="项目内递增版本号"
    )
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="章节内容快照（JSON 格式）"
    )
    change_type: Mapped[ChangeType] = mapped_column(
        Enum(ChangeType, name="change_type", native_enum=False, length=20),
        nullable=False,
        comment="变更类型",
    )
    change_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="变更摘要说明"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="创建此版本的用户",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], backref="versions"
    )
    chapter: Mapped["Chapter | None"] = relationship(
        "Chapter", foreign_keys=[chapter_id], backref="versions"
    )
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], backref="created_versions"
    )

    def __repr__(self) -> str:
        return f"<ProjectVersion {self.project_id} v{self.version_number}>"
