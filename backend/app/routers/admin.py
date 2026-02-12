"""管理员 API 路由"""
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.user import User
from ..models.api_key_config import ApiKeyConfig
from ..schemas.api_key_config import (
    ApiKeyConfigCreate,
    ApiKeyConfigUpdate,
    ApiKeyConfigResponse,
    ApiKeyConfigListResponse,
)
from ..auth.dependencies import require_admin
from ..utils.encryption import encryption_service

router = APIRouter(prefix="/api/admin", tags=["管理员"])


def mask_api_key(api_key: str) -> str:
    """脱敏 API Key：仅保留前4位和后4位"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return api_key[:4] + "****" + api_key[-4:]


def config_to_response(config: ApiKeyConfig) -> ApiKeyConfigResponse:
    """将 ORM 模型转换为响应模型（Key 脱敏）"""
    # 解密 API Key 后再脱敏
    decrypted_key = encryption_service.decrypt(config.api_key_encrypted)
    masked_key = mask_api_key(decrypted_key)

    return ApiKeyConfigResponse(
        id=config.id,
        provider=config.provider,
        api_key_masked=masked_key,
        base_url=config.base_url,
        model_name=config.model_name,
        is_default=config.is_default,
        created_by=config.created_by,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/api-keys", response_model=ApiKeyConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key_config(
    data: ApiKeyConfigCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """创建新的 API Key 配置（仅管理员）"""
    # 加密 API Key
    encrypted_key = encryption_service.encrypt(data.api_key)

    # 如果设为默认，先取消其他默认配置
    if data.is_default:
        result = await db.execute(
            select(ApiKeyConfig).where(ApiKeyConfig.is_default == True)
        )
        existing_defaults = result.scalars().all()
        for config in existing_defaults:
            config.is_default = False

    # 创建新配置
    new_config = ApiKeyConfig(
        provider=data.provider,
        api_key_encrypted=encrypted_key,
        base_url=data.base_url,
        model_name=data.model_name,
        is_default=data.is_default,
        created_by=current_user.id,
    )

    db.add(new_config)
    await db.flush()
    await db.refresh(new_config)

    return config_to_response(new_config)


@router.get("/api-keys", response_model=ApiKeyConfigListResponse)
async def list_api_key_configs(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
):
    """获取 API Key 配置列表（仅管理员，Key 脱敏）"""
    # 查询总数
    count_result = await db.execute(select(func.count(ApiKeyConfig.id)))
    total = count_result.scalar() or 0

    # 查询列表
    result = await db.execute(
        select(ApiKeyConfig).order_by(ApiKeyConfig.created_at.desc()).offset(skip).limit(limit)
    )
    configs = result.scalars().all()

    return ApiKeyConfigListResponse(
        items=[config_to_response(config) for config in configs],
        total=total,
    )


@router.delete("/api-keys/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key_config(
    config_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """删除 API Key 配置（仅管理员）"""
    result = await db.execute(
        select(ApiKeyConfig).where(ApiKeyConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key 配置不存在",
        )

    await db.delete(config)


@router.put("/api-keys/{config_id}/default", response_model=ApiKeyConfigResponse)
async def set_default_api_key_config(
    config_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """设置默认 API Key 配置（仅管理员）"""
    # 查找目标配置
    result = await db.execute(
        select(ApiKeyConfig).where(ApiKeyConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key 配置不存在",
        )

    # 取消其他默认配置
    result = await db.execute(
        select(ApiKeyConfig).where(ApiKeyConfig.is_default == True)
    )
    existing_defaults = result.scalars().all()
    for default_config in existing_defaults:
        default_config.is_default = False

    # 设置新的默认配置
    config.is_default = True
    await db.flush()
    await db.refresh(config)

    return config_to_response(config)
