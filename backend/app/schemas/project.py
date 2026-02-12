"""项目相关 Pydantic schema"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from ..models.project import ProjectStatus, ProjectMemberRole


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
