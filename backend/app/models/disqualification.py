"""废标检查 ORM 模型"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User
    from .project import Project


class DisqualificationCheck(Base):
    """废标检查项表 - 存储从招标文件中提取的否决性条款及检查状态"""
    __tablename__ = "disqualification_checks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目ID"
    )
    item_id: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="条目编号，如 DQ001"
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="分类，如 资质要求/文件要求/格式要求/时限要求/其他"
    )
    requirement: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="具体要求描述"
    )
    check_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="检查类型：certificate/document/format/deadline/other"
    )
    severity: Mapped[str] = mapped_column(
        String(10), nullable=False, default="fatal",
        comment="严重程度：fatal（直接废标）/warning（潜在风险）"
    )
    source_text: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="招标文件来源原文"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unchecked",
        comment="检查状态：unchecked/passed/failed/not_applicable"
    )
    checked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="检查操作者ID"
    )
    checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="检查时间"
    )
    note: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="用户备注"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], backref="disqualification_checks"
    )
    checker: Mapped["User | None"] = relationship(
        "User", foreign_keys=[checked_by], backref="disqualification_checks"
    )

    def __repr__(self) -> str:
        return f"<DisqualificationCheck {self.item_id} project={self.project_id} status={self.status}>"
