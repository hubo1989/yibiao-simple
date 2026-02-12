"""版本快照相关 Pydantic schema"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..models.version import ChangeType


class VersionBase(BaseModel):
    """版本基础字段"""
    change_type: ChangeType = Field(..., description="变更类型")
    change_summary: str | None = Field(None, max_length=2000, description="变更摘要说明")


class VersionCreate(VersionBase):
    """创建版本快照请求"""
    project_id: uuid.UUID = Field(..., description="所属项目 ID")
    chapter_id: uuid.UUID | None = Field(None, description="关联章节 ID（全量快照时为空）")
    snapshot_data: dict[str, Any] = Field(..., description="章节内容快照")


class VersionResponse(VersionBase):
    """版本响应"""
    id: uuid.UUID
    project_id: uuid.UUID
    chapter_id: uuid.UUID | None
    version_number: int
    snapshot_data: dict[str, Any]
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionSummary(BaseModel):
    """版本摘要（列表用，不含大快照数据）"""
    id: uuid.UUID
    project_id: uuid.UUID
    chapter_id: uuid.UUID | None
    version_number: int
    change_type: ChangeType
    change_summary: str | None
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionList(BaseModel):
    """版本列表响应"""
    items: list[VersionSummary]
    total: int = Field(..., description="总数量")
    project_id: uuid.UUID


class VersionRollbackRequest(BaseModel):
    """版本回滚请求"""
    target_version_id: uuid.UUID = Field(..., description="目标版本 ID")
    create_snapshot: bool = Field(
        default=True,
        description="回滚前是否创建当前状态快照"
    )
