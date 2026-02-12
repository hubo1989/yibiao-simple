"""校对结果 ORM 模型"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class IssueSeverity(str, PyEnum):
    """问题严重程度"""
    CRITICAL = "critical"  # 严重问题
    WARNING = "warning"    # 一般问题
    INFO = "info"          # 轻微问题


class IssueCategory(str, PyEnum):
    """问题类别"""
    COMPLIANCE = "compliance"    # 合规性
    LANGUAGE = "language"        # 语言质量
    CONSISTENCY = "consistency"  # 一致性
    REDUNDANCY = "redundancy"    # 冗余


class ProofreadResult(Base):
    """校对结果表 - 存储 AI 校对的结果"""
    __tablename__ = "proofread_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    issues: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="问题列表（JSON 格式）"
    )
    summary: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="问题摘要"
    )
    issue_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="问题总数"
    )
    critical_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="严重问题数量"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 关系
    chapter: Mapped["Chapter"] = relationship(
        "Chapter", foreign_keys=[chapter_id], backref="proofread_results"
    )
    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], backref="proofread_results"
    )

    def __repr__(self) -> str:
        return f"<ProofreadResult {self.id} chapter={self.chapter_id}>"
