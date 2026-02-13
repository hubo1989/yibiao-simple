"""配置相关API路由"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.schemas import ModelListResponse
from ..models.user import User
from ..models.api_key_config import ApiKeyConfig
from ..services.openai_service import OpenAIService
from ..utils.encryption import encryption_service
from ..db.database import get_db
from ..auth.dependencies import require_admin

router = APIRouter(prefix="/api/config", tags=["配置管理"])


@router.post("/models", response_model=ModelListResponse)
async def get_available_models(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取可用的模型列表（仅管理员，使用数据库中的默认配置）"""
    try:
        # 从数据库获取默认配置
        result = await db.execute(
            select(ApiKeyConfig).where(ApiKeyConfig.is_default == True).limit(1)
        )
        config = result.scalar_one_or_none()

        if not config:
            return ModelListResponse(
                models=[],
                success=False,
                message="未配置默认 API Key，请管理员先添加配置"
            )

        # 解密 API Key
        api_key = encryption_service.decrypt(config.api_key_encrypted)
        if not api_key:
            return ModelListResponse(
                models=[],
                success=False,
                message="API Key 解密失败"
            )

        # 创建 OpenAI 服务实例
        openai_service = OpenAIService(db=db)
        # 手动设置配置
        openai_service.api_key = api_key
        openai_service.base_url = config.base_url or ''
        openai_service.model_name = config.model_name

        # 获取模型列表
        models = await openai_service.get_available_models()

        return ModelListResponse(
            models=models,
            success=True,
            message=f"获取到 {len(models)} 个模型"
        )

    except Exception as e:
        return ModelListResponse(
            models=[],
            success=False,
            message=f"获取模型列表失败: {str(e)}"
        )
