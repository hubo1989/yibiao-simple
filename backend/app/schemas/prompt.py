"""提示词相关的 Pydantic Schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class PromptCategory:
    """提示词类别常量"""
    ANALYSIS = "analysis"
    GENERATION = "generation"
    CHECK = "check"


class PromptResponse(BaseModel):
    """提示词响应模型"""
    scene_key: str = Field(..., description="场景标识")
    scene_name: str = Field(..., description="场景名称")
    category: str = Field(..., description="类别：analysis/generation/check")
    prompt: str = Field(..., description="完整提示词")
    available_vars: Optional[dict] = Field(None, description="可用变量列表")
    version: int = Field(..., description="当前版本号")
    is_customized: bool = Field(False, description="是否已自定义（区别于内置默认）")
    updated_at: Optional[datetime] = Field(None, description="最后更新时间")

    model_config = {"from_attributes": True}


class PromptUpdate(BaseModel):
    """提示词更新模型"""
    prompt: str = Field(..., min_length=10, description="完整提示词")


class PromptVersionResponse(BaseModel):
    """提示词版本响应模型"""
    id: uuid.UUID = Field(..., description="版本ID")
    version: int = Field(..., description="版本号")
    prompt: str = Field(..., description="提示词")
    created_by: Optional[uuid.UUID] = Field(None, description="创建者ID")
    created_by_name: Optional[str] = Field(None, description="创建者名称")
    created_at: datetime = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class PromptVersionListResponse(BaseModel):
    """提示词版本列表响应"""
    items: list[PromptVersionResponse]
    total: int


class PromptListResponse(BaseModel):
    """提示词列表响应"""
    items: list[PromptResponse]
    total: int


class ProjectPromptConfig(BaseModel):
    """项目提示词配置"""
    scene_key: str = Field(..., description="场景标识")
    scene_name: str = Field(..., description="场景名称")
    category: str = Field(..., description="类别")
    # 最终使用的提示词（已解析三层回退）
    prompt: str = Field(..., description="最终使用的提示词")
    available_vars: Optional[dict] = Field(None, description="可用变量列表")
    # 继承状态
    source: str = Field(..., description="提示词来源：builtin/global/project")
    has_project_override: bool = Field(False, description="项目是否有自定义覆盖")
    has_global_override: bool = Field(False, description="全局是否有自定义覆盖")


class ProjectPromptConfigListResponse(BaseModel):
    """项目提示词配置列表响应"""
    items: list[ProjectPromptConfig]
    total: int


class ProjectPromptOverride(BaseModel):
    """项目提示词覆盖设置"""
    prompt: str = Field(..., min_length=10, description="提示词")


class PromptRollbackRequest(BaseModel):
    """提示词回滚请求"""
    version: int = Field(..., ge=1, description="目标版本号")
