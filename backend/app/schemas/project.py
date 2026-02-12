"""项目相关 Pydantic schema"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..models.project import ProjectStatus, ProjectMemberRole
from ..models.chapter import ChapterStatus
from ..models.consistency_result import ConsistencySeverity, ConsistencyCategory


class ProjectProgress(BaseModel):
    """项目进度统计"""
    total_chapters: int = Field(..., description="章节总数")
    pending: int = Field(default=0, description="待生成章节数")
    generated: int = Field(default=0, description="已生成章节数")
    reviewing: int = Field(default=0, description="审核中章节数")
    finalized: int = Field(default=0, description="已定稿章节数")
    completion_percentage: float = Field(default=0.0, description="完成百分比")

    model_config = {"from_attributes": True}


class ProjectBase(BaseModel):
    """项目基础字段"""
    name: str = Field(..., min_length=1, max_length=255, description="项目名称")
    description: str | None = Field(None, description="项目描述")


class ProjectCreate(ProjectBase):
    """创建项目请求"""
    pass


class ProjectUpdate(BaseModel):
    """更新项目请求（所有字段可选）"""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus | None = None
    file_content: str | None = None
    project_overview: str | None = None
    tech_requirements: str | None = None


class ProjectMemberAdd(BaseModel):
    """添加项目成员请求"""
    user_id: uuid.UUID = Field(..., description="用户 ID")
    role: ProjectMemberRole = Field(default=ProjectMemberRole.EDITOR, description="成员角色")


class ProjectMemberResponse(BaseModel):
    """项目成员响应"""
    user_id: uuid.UUID
    project_id: uuid.UUID
    role: ProjectMemberRole
    joined_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(ProjectBase):
    """项目响应"""
    id: uuid.UUID
    creator_id: uuid.UUID | None
    status: ProjectStatus
    file_content: str | None
    project_overview: str | None
    tech_requirements: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectSummary(BaseModel):
    """项目摘要（列表用，不含大文本字段）"""
    id: uuid.UUID
    name: str
    description: str | None
    creator_id: uuid.UUID | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# === 跨章节一致性检查相关 Schemas ===

class ChapterSummaryForConsistency(BaseModel):
    """用于一致性检查的章节摘要"""
    chapter_number: str = Field(..., description="章节编号，如 1.2.3")
    title: str = Field(..., description="章节标题")
    summary: str = Field(..., description="章节内容摘要（包含关键承诺、数据、时间线等）")


class ContradictionItem(BaseModel):
    """单个矛盾项"""
    severity: ConsistencySeverity = Field(..., description="严重程度")
    category: ConsistencyCategory = Field(..., description="矛盾类别")
    description: str = Field(..., description="矛盾描述")
    chapter_a: str = Field(..., description="涉及章节A的编号和标题")
    chapter_b: str = Field(..., description="涉及章节B的编号和标题")
    detail_a: str = Field(..., description="章节A中的相关内容")
    detail_b: str = Field(..., description="章节B中的相关内容")
    suggestion: str = Field(..., description="统一的建议")


class ConsistencyCheckRequest(BaseModel):
    """一致性检查请求"""
    chapter_summaries: list[ChapterSummaryForConsistency] = Field(
        ...,
        min_length=2,
        description="章节摘要列表（至少2个章节）"
    )


class ConsistencyCheckResponse(BaseModel):
    """一致性检查响应"""
    contradictions: list[ContradictionItem] = Field(
        default_factory=list,
        description="检测到的矛盾列表"
    )
    summary: str = Field(..., description="整体一致性评估摘要")
    overall_consistency: Literal["consistent", "minor_issues", "major_issues"] = Field(
        ...,
        description="整体一致性评估"
    )
    contradiction_count: int = Field(default=0, description="矛盾总数")
    critical_count: int = Field(default=0, description="严重矛盾数量")
    created_at: datetime = Field(..., description="检查时间")

    model_config = {"from_attributes": True}
