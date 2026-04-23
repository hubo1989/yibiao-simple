"""评分标准 ORM 模型"""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Float, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class ScoringCriteria(Base):
    """评分标准表 - 存储从招标文件中提取的评分项"""
    __tablename__ = "scoring_criteria"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="评分项编号，如 SC001"
    )
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="评分类别，如 技术方案 / 商务 / 其他"
    )
    item: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="评分项名称"
    )
    max_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="该项满分"
    )
    scoring_rule: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="评分细则"
    )
    keywords: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, default=list, comment="关键词列表"
    )
    source_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="评分标准在招标文件中的来源描述"
    )
    bound_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
        comment="绑定的章节ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 关系
    project = relationship("Project", foreign_keys=[project_id], backref="scoring_criteria")
    bound_chapter = relationship("Chapter", foreign_keys=[bound_chapter_id])

    def __repr__(self) -> str:
        return f"<ScoringCriteria {self.item_id} {self.item}>"
