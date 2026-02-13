"""章节 ORM 模型"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User
    from .project import Project


class ChapterStatus(str, PyEnum):
    """章节状态枚举"""
    PENDING = "pending"       # 待生成
    GENERATED = "generated"   # 已生成
    REVIEWING = "reviewing"   # 审核中
    FINALIZED = "finalized"   # 已定稿


class Chapter(Base):
    """章节表 - 存储标书目录结构和内容"""
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    chapter_number: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="章节编号，如 1.2.3"
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="章节标题"
    )
    content: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="章节内容"
    )
    status: Mapped[ChapterStatus] = mapped_column(
        Enum(ChapterStatus, name="chapter_status", native_enum=False, length=20),
        nullable=False,
        default=ChapterStatus.PENDING,
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="同级章节排序索引"
    )
    locked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="锁定用户ID（编辑锁定机制）"
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="锁定时间"
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
    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], backref="chapters"
    )
    parent: Mapped["Chapter | None"] = relationship(
        "Chapter", remote_side=[id], backref="children"
    )
    locked_by_user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[locked_by], backref="locked_chapters"
    )

    def __repr__(self) -> str:
        return f"<Chapter {self.chapter_number} {self.title}>"
