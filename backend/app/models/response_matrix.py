"""响应矩阵 ORM 模型 — TenderClause + ResponseMatrixItem"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class ClauseType(str, enum.Enum):
    technical = "technical"
    commercial = "commercial"
    qualification = "qualification"
    disqualification = "disqualification"
    scoring = "scoring"
    format = "format"
    other = "other"


class ResponseStatus(str, enum.Enum):
    not_started = "not_started"
    covered = "covered"
    partial = "partial"
    missing = "missing"
    risk = "risk"
    not_applicable = "not_applicable"


class TenderClause(Base):
    """统一条款表 — 聚合评分标准、废标检查等各类招标要求"""
    __tablename__ = "tender_clauses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clause_type: Mapped[ClauseType] = mapped_column(
        Enum(ClauseType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_location: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    raw_requirement: Mapped[str] = mapped_column(Text, default="", nullable=False)
    score_value: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    is_fatal: Mapped[bool] = mapped_column(default=False, index=True, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # relationships
    project = relationship("Project", foreign_keys=[project_id])

    def __repr__(self) -> str:
        return f"<TenderClause {self.id} type={self.clause_type.value}>"


class ResponseMatrixItem(Base):
    """响应矩阵条目 — 条款→章节的覆盖映射"""
    __tablename__ = "response_matrix_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clause_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tender_clauses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_id: Mapped[str] = mapped_column(String(100), default="", index=True, nullable=False)
    chapter_title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    response_status: Mapped[ResponseStatus] = mapped_column(
        Enum(ResponseStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=ResponseStatus.not_started,
        index=True,
        nullable=False,
    )
    response_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    risk_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # relationships
    project = relationship("Project", foreign_keys=[project_id])
    clause = relationship("TenderClause", foreign_keys=[clause_id])

    def __repr__(self) -> str:
        return f"<ResponseMatrixItem clause={self.clause_id} status={self.response_status.value}>"
