"""评论批注 ORM 模型"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User
    from .chapter import Chapter


class Comment(Base):
    """评论批注表 - 存储章节内容的批注"""
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属章节ID"
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="批注创建者ID"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="批注内容"
    )
    position_start: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="批注起始位置（字符偏移量）"
    )
    position_end: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="批注结束位置（字符偏移量）"
    )
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="是否已解决"
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="解决者ID"
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="解决时间"
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
    chapter: Mapped["Chapter"] = relationship(
        "Chapter", foreign_keys=[chapter_id], backref="comments"
    )
    user: Mapped["User"] = relationship(
        "User", foreign_keys=[user_id], backref="comments"
    )
    resolver: Mapped["User | None"] = relationship(
        "User", foreign_keys=[resolved_by], backref="resolved_comments"
    )

    def __repr__(self) -> str:
        return f"<Comment {self.id} by {self.user_id}>"
