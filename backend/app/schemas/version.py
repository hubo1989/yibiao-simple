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


class VersionDiffInfo(BaseModel):
    """版本差异中的版本信息"""
    id: str
    version_number: int
    created_at: str
    change_type: str


class ChapterChange(BaseModel):
    """章节变更记录"""
    type: str = Field(..., description="变更类型: added, deleted, modified")
    chapter_id: str = Field(..., description="章节 ID")
    chapter_number: str | None = Field(None, description="章节编号")
    title: str | None = Field(None, description="章节标题")
    old_content: str | None = Field(None, description="旧内容")
    new_content: str | None = Field(None, description="新内容")
    old_title: str | None = Field(None, description="旧标题")
    new_title: str | None = Field(None, description="新标题")
    content_changed: bool | None = Field(None, description="内容是否变化")
    title_changed: bool | None = Field(None, description="标题是否变化")


class VersionDiffSummary(BaseModel):
    """版本差异摘要"""
    total_changes: int = Field(..., description="总变更数")
    added: int = Field(..., description="新增章节数")
    deleted: int = Field(..., description="删除章节数")
    modified: int = Field(..., description="修改章节数")
    changes: list[ChapterChange] = Field(default_factory=list, description="变更列表")


class VersionDiffResponse(BaseModel):
    """版本差异对比响应"""
    v1: VersionDiffInfo = Field(..., description="版本1信息")
    v2: VersionDiffInfo = Field(..., description="版本2信息")
    diff: VersionDiffSummary | dict[str, Any] = Field(..., description="差异结果")


class RestoredChapter(BaseModel):
    """恢复的章节信息"""
    id: str
    chapter_number: str
    action: str = Field(..., description="操作类型: updated")


class VersionRollbackResponse(BaseModel):
    """版本回滚响应"""
    success: bool = Field(..., description="是否成功")
    target_version_number: int | None = Field(None, description="目标版本号")
    new_version_id: str | None = Field(None, description="新创建的版本 ID")
    new_version_number: int | None = Field(None, description="新版本号")
    pre_snapshot_id: str | None = Field(None, description="回滚前快照 ID")
    restored_chapters: list[RestoredChapter] = Field(
        default_factory=list,
        description="恢复的章节列表"
    )
    error: str | None = Field(None, description="错误信息")
