"""素材库相关 schema"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from ..models.knowledge import Scope
from ..models.material import (
    BindingAnchorType,
    BindingDisplayMode,
    MaterialCategory,
    MaterialRequirementStatus,
    MaterialReviewStatus,
)


class MaterialAssetBase(BaseModel):
    scope: Scope = Field(default=Scope.USER)
    category: MaterialCategory = Field(default=MaterialCategory.OTHER)
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    ai_description: str | None = None
    ai_extracted_fields: dict = Field(default_factory=dict)
    valid_from: date | None = None
    valid_until: date | None = None
    review_status: MaterialReviewStatus = Field(default=MaterialReviewStatus.PENDING)


class MaterialAssetUpdate(BaseModel):
    category: MaterialCategory | None = None
    name: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    tags: list[str] | None = None
    keywords: list[str] | None = None
    ai_description: str | None = None
    ai_extracted_fields: dict | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    review_status: MaterialReviewStatus | None = None


class MaterialAssetResponse(MaterialAssetBase):
    id: uuid.UUID
    owner_id: uuid.UUID | None = None
    uploaded_by: uuid.UUID | None = None
    file_path: str
    preview_path: str | None = None
    thumbnail_path: str | None = None
    file_type: str
    file_ext: str
    file_size: int
    page_count: int | None = None
    is_expired: bool
    is_disabled: bool = False
    usage_count: int
    last_used_at: datetime | None = None
    # 溯源字段
    source_document_id: str | None = None
    source_page_from: int | None = None
    source_page_to: int | None = None
    source_excerpt: str | None = None
    extraction_method: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialRequirementResponse(BaseModel):
    id: str
    project_id: str
    source_document_id: str | None = None
    chapter_hint: str | None = None
    section_hint: str | None = None
    requirement_name: str
    requirement_text: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_mandatory: bool
    status: MaterialRequirementStatus
    extracted_by: str
    sort_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialRequirementUpdate(BaseModel):
    chapter_hint: str | None = None
    section_hint: str | None = None
    requirement_name: str | None = Field(None, min_length=1, max_length=500)
    requirement_text: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    is_mandatory: bool | None = None
    status: MaterialRequirementStatus | None = None
    sort_index: int | None = None


class MaterialRequirementAnalyzeResult(BaseModel):
    required_materials: list[MaterialRequirementUpdate] = Field(default_factory=list)


class MaterialRequirementMatchCandidate(BaseModel):
    asset_id: str
    score: float
    matched_reasons: list[str] = Field(default_factory=list)
    asset: MaterialAssetResponse | None = None


class MaterialMatchConfirmRequest(BaseModel):
    material_asset_id: uuid.UUID


class ChapterMaterialBindingCreate(BaseModel):
    material_requirement_id: uuid.UUID | None = None
    material_asset_id: uuid.UUID
    anchor_type: BindingAnchorType = Field(default=BindingAnchorType.SECTION_END)
    anchor_value: str | None = None
    display_mode: BindingDisplayMode = Field(default=BindingDisplayMode.IMAGE)
    caption: str | None = None
    sort_index: int = 0


class ChapterMaterialBindingUpdate(BaseModel):
    anchor_type: BindingAnchorType | None = None
    anchor_value: str | None = None
    display_mode: BindingDisplayMode | None = None
    caption: str | None = None
    sort_index: int | None = None


class ChapterMaterialBindingResponse(BaseModel):
    id: str
    project_id: str
    chapter_id: str
    material_requirement_id: str | None = None
    material_asset_id: str
    anchor_type: BindingAnchorType
    anchor_value: str | None = None
    display_mode: BindingDisplayMode
    caption: str | None = None
    sort_index: int
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    material_asset: MaterialAssetResponse | None = None

    model_config = {"from_attributes": True}


# ========== Ingestion Task Schemas ==========

class IngestionTaskStatus(str):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionTaskCreate(BaseModel):
    document_id: uuid.UUID


class IngestionTaskResponse(BaseModel):
    id: str
    document_id: str
    created_by: str | None = None
    status: str
    total_candidates: int
    confirmed_count: int
    rejected_count: int
    error_message: str | None = None
    processing_log: list[dict] = Field(default_factory=list)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialCandidateResponse(BaseModel):
    id: str
    task_id: str
    category: str
    name: str
    source_page_from: int | None = None
    source_page_to: int | None = None
    source_excerpt: str | None = None
    preview_path: str | None = None
    thumbnail_path: str | None = None
    file_type: str | None = None
    file_ext: str | None = None
    file_size: int | None = None
    extraction_method: str
    confidence_score: float | None = None
    ai_description: str | None = None
    ai_extracted_fields: dict | None = None
    tags: list[str] = Field(default_factory=list)
    review_status: str
    confirmed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionConfirmRequest(BaseModel):
    confirm_ids: list[uuid.UUID] = Field(default_factory=list)
    reject_ids: list[uuid.UUID] = Field(default_factory=list)
