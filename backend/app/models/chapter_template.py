"""章节模板 ORM 模型 - 标书知识库（章节复用库）"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User
    from .project import Project
    from .chapter import Chapter


class ChapterTemplate(Base):
    """章节模板表 - 标书知识库，存储可复用的章节内容模板"""
    __tablename__ = "chapter_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="模板名称，如「安全方案-中标版」"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="模板描述"
    )
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="分类：技术方案/项目经验/团队配置/质量保障/安全方案/其他"
    )
    tags: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=list,
        comment="标签列表"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="章节内容（Markdown）"
    )
    source_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        comment="来源项目 ID"
    )
    source_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
        comment="来源章节 ID"
    )
    source_project_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="来源项目名（冗余存储，避免级联查询）"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="创建者 ID"
    )
    usage_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="被套用次数"
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
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], backref="chapter_templates"
    )
    source_project: Mapped["Project | None"] = relationship(
        "Project", foreign_keys=[source_project_id], backref="chapter_templates"
    )
    source_chapter: Mapped["Chapter | None"] = relationship(
        "Chapter", foreign_keys=[source_chapter_id], backref="chapter_templates"
    )

    def __repr__(self) -> str:
        return f"<ChapterTemplate {self.name}>"
