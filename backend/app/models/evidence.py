"""证据引用 ORM 模型"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class EvidenceSourceType(str, enum.Enum):
    tender_document = "tender_document"
    knowledge_doc = "knowledge_doc"
    material_asset = "material_asset"
    manual_input = "manual_input"
    generated_content = "generated_content"


class EvidenceRef(Base):
    """证据引用表 — 追溯每段生成内容到具体来源"""
    __tablename__ = "evidence_refs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_type: Mapped[EvidenceSourceType] = mapped_column(
        Enum(EvidenceSourceType, values_callable=lambda obj: [e.value for e in obj]), index=True
    )
    source_id: Mapped[str] = mapped_column(String(255), default="", index=True)
    source_title: Mapped[str] = mapped_column(String(500), default="")
    source_location: Mapped[str] = mapped_column(String(255), default="")
    quote: Mapped[str] = mapped_column(Text, default="")
    relation: Mapped[str] = mapped_column(Text, default="", comment="与生成内容的关系说明")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # relationships
    project = relationship("Project", foreign_keys=[project_id])
    chapter = relationship("Chapter", foreign_keys=[chapter_id])
