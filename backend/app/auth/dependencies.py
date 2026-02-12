"""认证依赖注入"""
import uuid
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.user import User, UserRole
from .security import decode_token

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """从 Authorization header 解析 token 并返回当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise credentials_exception

    # 检查是否是刷新令牌（刷新令牌不能用于访问）
    if payload.get("type") == "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌不能用于访问",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """确保当前用户处于活跃状态"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账户已被禁用",
        )
    return current_user


def require_role(*required_roles: UserRole) -> Callable:
    """
    角色权限检查依赖工厂

    Args:
        *required_roles: 允许访问的角色列表

    Returns:
        依赖函数，用于验证用户是否具有所需角色

    Usage:
        @router.get("/admin-only")
        async def admin_route(user: User = Depends(require_role(UserRole.ADMIN))):
            return {"message": "Admin access granted"}

        @router.get("/editor-or-admin")
        async def editor_route(user: User = Depends(require_role(UserRole.EDITOR, UserRole.ADMIN))):
            return {"message": "Editor access granted"}
    """
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        # 管理员拥有所有权限
        if current_user.role == UserRole.ADMIN:
            return current_user

        if current_user.role not in required_roles:
            roles_str = "、".join(r.value for r in required_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要以下角色之一：{roles_str}",
            )
        return current_user

    return role_checker


# 预定义的常用角色依赖
require_admin = require_role(UserRole.ADMIN)
require_editor = require_role(UserRole.EDITOR, UserRole.ADMIN)
require_reviewer = require_role(UserRole.REVIEWER, UserRole.EDITOR, UserRole.ADMIN)
