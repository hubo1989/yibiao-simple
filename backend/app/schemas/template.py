"""模板相关 Pydantic schema"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TemplateBase(BaseModel):
    """模板基础字段"""
    name: str = Field(..., min_length=1, max_length=255, description="模板名称")
    description: str | None = Field(None, description="模板描述")


class TemplateCreate(TemplateBase):
    """创建模板请求"""
    source_project_id: uuid.UUID | None = Field(None, description="来源项目 ID，若提供则自动复制目录结构")


class TemplateUpdate(BaseModel):
    """更新模板请求（所有字段可选）"""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    outline_data: dict | None = None


class TemplateResponse(TemplateBase):
    """模板响应"""
    id: uuid.UUID
    outline_data: dict | None
    source_project_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateSummary(BaseModel):
    """模板摘要（列表用，不含大纲数据）"""
    id: uuid.UUID
    name: str
    description: str | None
    source_project_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectFromTemplateCreate(BaseModel):
    """基于模板创建项目请求"""
    name: str = Field(..., min_length=1, max_length=255, description="新项目名称")
    description: str | None = Field(None, description="项目描述")
