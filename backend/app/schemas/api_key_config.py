"""API Key 配置相关 Pydantic schema"""
import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, computed_field, model_validator

DEFAULT_MODEL_NAME = "gpt-3.5-turbo"


class ApiKeyModelConfig(BaseModel):
    """单个模型用途配置"""
    model_id: str = Field(..., min_length=1, max_length=128, description="模型 ID")
    use_for_generation: bool = Field(default=False, description="是否用于生成")
    use_for_indexing: bool = Field(default=False, description="是否用于索引")

    @model_validator(mode="after")
    def strip_model_id(self) -> Self:
        self.model_id = self.model_id.strip()
        if not self.model_id:
            raise ValueError("模型 ID 不能为空")
        return self



def _resolve_model_configs(
    model_configs: list[ApiKeyModelConfig] | None,
    model_name: str | None,
) -> list[ApiKeyModelConfig]:
    normalized: list[ApiKeyModelConfig] = []
    seen_model_ids: set[str] = set()

    for item in model_configs or []:
        if item.model_id in seen_model_ids:
            raise ValueError(f"模型 ID 不能重复: {item.model_id}")
        seen_model_ids.add(item.model_id)
        normalized.append(item)

    if not normalized:
        fallback_model = (model_name or DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME
        normalized = [
            ApiKeyModelConfig(
                model_id=fallback_model,
                use_for_generation=True,
                use_for_indexing=True,
            )
        ]

    if sum(1 for item in normalized if item.use_for_generation) > 1:
        raise ValueError("同一配置最多只能指定一个生成模型")
    if sum(1 for item in normalized if item.use_for_indexing) > 1:
        raise ValueError("同一配置最多只能指定一个索引模型")

    return normalized



def _pick_generation_model_name(model_configs: list[ApiKeyModelConfig], model_name: str | None) -> str:
    for item in model_configs:
        if item.use_for_generation:
            return item.model_id
    if model_configs:
        return model_configs[0].model_id
    return (model_name or DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME



def _pick_index_model_name(model_configs: list[ApiKeyModelConfig], model_name: str | None) -> str:
    for item in model_configs:
        if item.use_for_indexing:
            return item.model_id
    return _pick_generation_model_name(model_configs, model_name)


class ApiKeyConfigCreate(BaseModel):
    """创建 API Key 配置请求"""
    provider: str = Field(..., min_length=1, max_length=64, description="提供商名称")
    api_key: str = Field(..., min_length=1, description="API Key")
    base_url: str | None = Field(None, max_length=512, description="API 基础 URL")
    model_name: str = Field(default=DEFAULT_MODEL_NAME, max_length=128, description="兼容旧版本的默认模型名称")
    model_configs: list[ApiKeyModelConfig] = Field(default_factory=list, description="模型列表与用途配置")
    is_default: bool = Field(default=False, description="是否为默认配置")

    @model_validator(mode="after")
    def normalize_models(self) -> Self:
        self.provider = self.provider.strip()
        if self.base_url is not None:
            self.base_url = self.base_url.strip() or None
        self.model_configs = _resolve_model_configs(self.model_configs, self.model_name)
        self.model_name = _pick_generation_model_name(self.model_configs, self.model_name)
        return self

    @computed_field(return_type=str)
    @property
    def generation_model_name(self) -> str:
        return _pick_generation_model_name(self.model_configs, self.model_name)

    @computed_field(return_type=str)
    @property
    def index_model_name(self) -> str:
        return _pick_index_model_name(self.model_configs, self.model_name)


class ApiKeyConfigUpdate(BaseModel):
    """更新 API Key 配置请求"""
    provider: str | None = Field(None, min_length=1, max_length=64)
    api_key: str | None = Field(None, min_length=1)
    base_url: str | None = Field(None, max_length=512)
    model_name: str | None = Field(None, max_length=128)
    model_configs: list[ApiKeyModelConfig] | None = Field(default=None)
    is_default: bool | None = None

    @model_validator(mode="after")
    def normalize_models(self) -> Self:
        if self.provider is not None:
            self.provider = self.provider.strip()
        if self.base_url is not None:
            self.base_url = self.base_url.strip()

        if self.model_configs is None and self.model_name is None:
            return self

        if self.model_configs == [] and self.model_name is None:
            raise ValueError("至少保留一个模型 ID")

        self.model_configs = _resolve_model_configs(self.model_configs, self.model_name)
        self.model_name = _pick_generation_model_name(self.model_configs, self.model_name)
        return self

    @computed_field(return_type=str | None)
    @property
    def generation_model_name(self) -> str | None:
        if self.model_configs is None and self.model_name is None:
            return None
        return _pick_generation_model_name(self.model_configs or [], self.model_name)

    @computed_field(return_type=str | None)
    @property
    def index_model_name(self) -> str | None:
        if self.model_configs is None and self.model_name is None:
            return None
        return _pick_index_model_name(self.model_configs or [], self.model_name)


class ApiKeyConfigResponse(BaseModel):
    """API Key 配置响应（Key 脱敏）"""
    id: uuid.UUID
    provider: str
    api_key_masked: str = Field(..., description="脱敏后的 API Key")
    base_url: str | None
    model_name: str
    model_configs: list[ApiKeyModelConfig]
    generation_model_name: str
    index_model_name: str
    is_default: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyConfigListResponse(BaseModel):
    """API Key 配置列表响应"""
    items: list[ApiKeyConfigResponse]
    total: int
