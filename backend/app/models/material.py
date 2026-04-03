"""素材库相关 ORM 模型"""
import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base
from .knowledge import Scope

if TYPE_CHECKING:
    from .chapter import Chapter
    from .project import Project
    from .user import User


class MaterialCategory(str, enum.Enum):
    BUSINESS_LICENSE = "business_license"
    LEGAL_PERSON_ID = "legal_person_id"
    QUALIFICATION_CERT = "qualification_cert"
    AWARD_CERT = "award_cert"
    ISO_CERT = "iso_cert"
    CONTRACT_SAMPLE = "contract_sample"
    PROJECT_CASE = "project_case"
    TEAM_PHOTO = "team_photo"
    EQUIPMENT_PHOTO = "equipment_photo"
    FINANCIAL_REPORT = "financial_report"
    BANK_CREDIT = "bank_credit"
    SOCIAL_SECURITY = "social_security"
    OTHER = "other"


class MaterialReviewStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class MaterialRequirementStatus(str, enum.Enum):
    PENDING = "pending"
    MATCHED = "matched"
    MISSING = "missing"
    IGNORED = "ignored"
    CONFIRMED = "confirmed"


class MaterialExtractedBy(str, enum.Enum):
    AI = "ai"
    USER = "user"


class BindingAnchorType(str, enum.Enum):
    SECTION_END = "section_end"
    PARAGRAPH_AFTER = "paragraph_after"
    PARAGRAPH_BEFORE = "paragraph_before"
    APPENDIX_BLOCK = "appendix_block"


class BindingDisplayMode(str, enum.Enum):
    IMAGE = "image"
    ATTACHMENT_NOTE = "attachment_note"


class MaterialAsset(Base):
    __tablename__ = "material_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=Scope.USER.value,
        index=True,
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category: Mapped[MaterialCategory] = mapped_column(
        SQLEnum(MaterialCategory, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=MaterialCategory.OTHER,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    preview_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_ext: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    ai_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_extracted_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_expired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    review_status: Mapped[MaterialReviewStatus] = mapped_column(
        SQLEnum(MaterialReviewStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=MaterialReviewStatus.PENDING,
    )
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 溯源字段：从历史标书解析而来
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_docs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_page_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_page_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # rule | llm | hybrid
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    uploader: Mapped["User | None"] = relationship("User", foreign_keys=[uploaded_by], backref="uploaded_material_assets")


class MaterialRequirement(Base):
    __tablename__ = "material_requirements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    chapter_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requirement_name: Mapped[str] = mapped_column(String(500), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[MaterialRequirementStatus] = mapped_column(
        SQLEnum(MaterialRequirementStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=MaterialRequirementStatus.PENDING,
        index=True,
    )
    extracted_by: Mapped[MaterialExtractedBy] = mapped_column(
        SQLEnum(MaterialExtractedBy, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=MaterialExtractedBy.AI,
    )
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped["Project"] = relationship("Project", backref="material_requirements")


class ChapterMaterialBinding(Base):
    __tablename__ = "chapter_material_bindings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("material_requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    material_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    anchor_type: Mapped[BindingAnchorType] = mapped_column(
        SQLEnum(BindingAnchorType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=BindingAnchorType.SECTION_END,
    )
    anchor_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_mode: Mapped[BindingDisplayMode] = mapped_column(
        SQLEnum(BindingDisplayMode, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=BindingDisplayMode.IMAGE,
    )
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped["Project"] = relationship("Project", backref="chapter_material_bindings")
    chapter: Mapped["Chapter"] = relationship("Chapter", backref="material_bindings")
    material_asset: Mapped["MaterialAsset"] = relationship("MaterialAsset", backref="chapter_bindings")
    material_requirement: Mapped["MaterialRequirement | None"] = relationship(
        "MaterialRequirement", backref="chapter_bindings"
    )


# Import dependent ORM modules so relationship string resolution works during mapper configuration.
from . import chapter as _chapter  # noqa: E402,F401
from . import project as _project  # noqa: E402,F401
from . import user as _user  # noqa: E402,F401
