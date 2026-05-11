"""响应矩阵 Pydantic schemas"""
from datetime import datetime
from pydantic import BaseModel, Field


class TenderClauseResponse(BaseModel):
    id: str
    project_id: str
    clause_type: str
    title: str = ""
    content: str = ""
    source_page: int | None = None
    source_location: str = ""
    score_value: float | None = None
    is_fatal: bool = False
    model_config = {"from_attributes": True}


class ResponseMatrixItemResponse(BaseModel):
    id: str
    project_id: str
    clause_id: str
    chapter_id: str = ""
    chapter_title: str = ""
    response_status: str
    response_summary: str = ""
    evidence_summary: str = ""
    risk_note: str = ""
    confidence: str = "medium"
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


class ResponseMatrixSummary(BaseModel):
    total_clauses: int = 0
    covered: int = 0
    partial: int = 0
    missing: int = 0
    risk: int = 0
    fatal_missing: int = 0
    scoring_coverage_rate: float = 0
    overall_status: str = Field("not_ready", description="ready|not_ready|risk")


class BindClauseRequest(BaseModel):
    clause_id: str
    chapter_id: str = ""
    chapter_title: str = ""


class UpdateMatrixItemRequest(BaseModel):
    response_status: str | None = None
    response_summary: str | None = None
    evidence_summary: str | None = None
    risk_note: str | None = None
    confidence: str | None = None


class RebuildMatrixRequest(BaseModel):
    model_name: str | None = None
    provider_config_id: str | None = None


class ResponseMatrixPreflight(BaseModel):
    ready: bool = False
    summary: ResponseMatrixSummary = Field(default_factory=ResponseMatrixSummary)
    blockers: list[str] = Field(default_factory=list)
