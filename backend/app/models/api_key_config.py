"""API Key 配置 ORM 模型"""
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import String, Boolean, DateTime, func, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base

DEFAULT_MODEL_NAME = "gpt-3.5-turbo"



def _normalize_model_configs(
    model_configs: list[dict[str, Any]] | None,
    fallback_model_name: str | None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_model_ids: set[str] = set()

    for item in model_configs or []:
        model_id = str(item.get("model_id", "")).strip()
        if not model_id or model_id in seen_model_ids:
            continue
        seen_model_ids.add(model_id)
        normalized.append(
            {
                "model_id": model_id,
                "use_for_generation": bool(item.get("use_for_generation", False)),
                "use_for_indexing": bool(item.get("use_for_indexing", False)),
            }
        )

    if normalized:
        return normalized

    legacy_model_name = (fallback_model_name or DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME
    return [
        {
            "model_id": legacy_model_name,
            "use_for_generation": True,
            "use_for_indexing": True,
        }
    ]


class ApiKeyConfig(Base):
    """API Key 配置表"""
    __tablename__ = "api_key_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="提供商名称，如 openai, anthropic"
    )
    api_key_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False, comment="加密后的 API Key"
    )
    base_url: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="API 基础 URL"
    )
    model_name: Mapped[str] = mapped_column(
        String(128), nullable=False, default=DEFAULT_MODEL_NAME, comment="默认模型名称"
    )
    model_configs_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="模型配置 JSON，支持分别设置生成模型与索引模型",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否为默认配置"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建者 ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def get_model_configs(self) -> list[dict[str, Any]]:
        """获取规范化后的模型配置列表。"""
        if self.model_configs_json:
            try:
                raw_configs = json.loads(self.model_configs_json)
                if isinstance(raw_configs, list):
                    return _normalize_model_configs(raw_configs, self.model_name)
            except json.JSONDecodeError:
                pass
        return _normalize_model_configs(None, self.model_name)

    def set_model_configs(self, model_configs: list[dict[str, Any]] | None) -> None:
        """设置模型配置，并同步兼容字段。"""
        normalized = _normalize_model_configs(model_configs, self.model_name)
        self.model_configs_json = json.dumps(normalized, ensure_ascii=False)
        self.model_name = self.get_generation_model_name_from_configs(normalized)

    @staticmethod
    def get_generation_model_name_from_configs(model_configs: list[dict[str, Any]]) -> str:
        for item in model_configs:
            if item.get("use_for_generation"):
                return str(item.get("model_id") or DEFAULT_MODEL_NAME)
        if model_configs:
            return str(model_configs[0].get("model_id") or DEFAULT_MODEL_NAME)
        return DEFAULT_MODEL_NAME

    @staticmethod
    def get_index_model_name_from_configs(model_configs: list[dict[str, Any]]) -> str:
        for item in model_configs:
            if item.get("use_for_indexing"):
                return str(item.get("model_id") or DEFAULT_MODEL_NAME)
        return ApiKeyConfig.get_generation_model_name_from_configs(model_configs)

    def get_generation_model_name(self) -> str:
        return self.get_generation_model_name_from_configs(self.get_model_configs())

    def get_index_model_name(self) -> str:
        return self.get_index_model_name_from_configs(self.get_model_configs())

    def __repr__(self) -> str:
        return f"<ApiKeyConfig {self.provider}>"
