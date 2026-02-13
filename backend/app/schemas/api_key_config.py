"""API Key 配置相关 Pydantic schema"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyConfigCreate(BaseModel):
    """创建 API Key 配置请求"""
    provider: str = Field(..., min_length=1, max_length=64, description="提供商名称")
    api_key: str = Field(..., min_length=1, description="API Key")
    base_url: str | None = Field(None, max_length=512, description="API 基础 URL")
    model_name: str = Field(default="gpt-3.5-turbo", max_length=128, description="默认模型名称")
    is_default: bool = Field(default=False, description="是否为默认配置")


class ApiKeyConfigUpdate(BaseModel):
    """更新 API Key 配置请求"""
    provider: str | None = Field(None, min_length=1, max_length=64)
    api_key: str | None = Field(None, min_length=1)
    base_url: str | None = Field(None, max_length=512)
    model_name: str | None = Field(None, max_length=128)
    is_default: bool | None = None


class ApiKeyConfigResponse(BaseModel):
    """API Key 配置响应（Key 脱敏）"""
    id: uuid.UUID
    provider: str
    api_key_masked: str = Field(..., description="脱敏后的 API Key")
    base_url: str | None
    model_name: str
    is_default: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyConfigListResponse(BaseModel):
    """API Key 配置列表响应"""
    items: list[ApiKeyConfigResponse]
    total: int
