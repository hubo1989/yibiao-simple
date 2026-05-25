"""Bid Agent orchestrator schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BidAgentRunCreate(BaseModel):
    goal: str = Field("generate_draft", description="generate_draft|fix_risks")


class BidAgentRunResponse(BaseModel):
    id: str
    project_id: str
    created_by: str | None = None
    goal: str
    status: str
    progress: int = 0
    summary: str = ""
    error_message: str = ""
    result_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BidAgentStepResponse(BaseModel):
    id: str
    run_id: str
    step_key: str
    step_name: str
    status: str
    order_index: int = 0
    progress: int = 0
    summary: str = ""
    error_message: str = ""
    result_json: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class BidAgentQualityReport(BaseModel):
    project_id: str
    response_matrix_preflight: dict[str, Any] = Field(default_factory=dict)
    export_preflight: dict[str, Any] = Field(default_factory=dict)
    ready: bool = False
    blockers: list[str] = Field(default_factory=list)
