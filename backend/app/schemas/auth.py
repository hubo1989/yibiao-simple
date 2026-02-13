"""认证相关 Pydantic schemas"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from ..models.user import UserRole


class UserRegister(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=2, max_length=64, description="用户名")
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, max_length=128, description="密码")


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class Token(BaseModel):
    """令牌响应"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class TokenPayload(BaseModel):
    """令牌载荷"""
    sub: str = Field(..., description="用户ID")
    role: UserRole | None = Field(None, description="用户角色")
    exp: int | None = Field(None, description="过期时间戳")
    type: str | None = Field(None, description="令牌类型")


class UserMe(BaseModel):
    """当前用户信息响应"""
    id: uuid.UUID
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str = Field(..., description="刷新令牌")
