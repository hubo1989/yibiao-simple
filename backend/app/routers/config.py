"""配置相关API路由"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.schemas import ModelListResponse, ProviderModelOption
from ..models.user import User
from ..models.api_key_config import ApiKeyConfig
from ..services.openai_service import OpenAIService
from ..db.database import get_db
from ..auth.dependencies import require_editor
from ..config import settings

router = APIRouter(prefix="/api/config", tags=["配置管理"])


def build_env_provider_option(is_default: bool = False) -> ProviderModelOption | None:
    """从环境变量构建自托管 provider 选项。"""
    if not (settings.llm_base_url or settings.llm_api_key or settings.llm_model):
        return None

    return ProviderModelOption(
        config_id="env",
        provider=settings.llm_provider or "env",
        models=settings.generation_models,
        default_model=settings.generation_model,
        is_default=is_default,
        source="environment",
        index_model=settings.embedding_model,
        embedding_base_url=settings.effective_embedding_base_url,
        embedding_provider=settings.embedding_provider,
    )


@router.post("/models", response_model=ModelListResponse)
async def get_available_models(
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取可用的 provider 与模型列表。"""
    try:
        result = await db.execute(
            select(ApiKeyConfig).order_by(ApiKeyConfig.is_default.desc(), ApiKeyConfig.created_at.desc())
        )
        configs = result.scalars().all()

        env_provider = build_env_provider_option(is_default=True)

        if not configs and env_provider is None:
            return ModelListResponse(
                models=[],
                providers=[],
                success=False,
                message="未配置 API Key。请通过环境变量 LLM_BASE_URL/LLM_API_KEY/LLM_MODEL 配置，或由管理员在后台添加配置。"
            )

        provider_items: list[ProviderModelOption] = []
        default_provider_config_id: str | None = None

        if env_provider is not None:
            provider_items.append(env_provider)
            default_provider_config_id = env_provider.config_id

        for config in configs:
            configured_models = [item.get("model_id", "") for item in config.get_model_configs()]
            configured_models = [model for model in configured_models if model]

            openai_service = OpenAIService(db=db)
            models = configured_models

            if openai_service.use_api_key_config(config):
                try:
                    models = await openai_service.get_available_models()
                except Exception:
                    models = configured_models

            deduped_models = list(dict.fromkeys([*models, *configured_models]))
            default_model = config.get_generation_model_name()

            provider_items.append(
                ProviderModelOption(
                    config_id=str(config.id),
                    provider=config.provider,
                    models=deduped_models or [default_model],
                    default_model=default_model,
                    is_default=config.is_default,
                    source="database",
                    index_model=config.get_index_model_name(),
                )
            )

            if config.is_default and default_provider_config_id is None:
                default_provider_config_id = str(config.id)

        active_provider = next(
            (item for item in provider_items if item.config_id == default_provider_config_id),
            provider_items[0],
        )

        return ModelListResponse(
            models=active_provider.models,
            providers=provider_items,
            default_provider_config_id=active_provider.config_id,
            success=True,
            message=f"获取到 {len(provider_items)} 个 Provider"
        )

    except Exception as e:
        return ModelListResponse(
            models=[],
            providers=[],
            success=False,
            message=f"获取模型列表失败: {str(e)}"
        )
