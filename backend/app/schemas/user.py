"""用户相关 Pydantic schema"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr

from ..models.user import UserRole


class UserBase(BaseModel):
    """用户基础字段"""
    username: str = Field(..., min_length=2, max_length=64, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    role: UserRole = Field(default=UserRole.EDITOR, description="用户角色")


class UserCreate(UserBase):
    """创建用户请求"""
    password: str = Field(..., min_length=8, max_length=128, description="密码")


class UserUpdate(BaseModel):
    """更新用户请求（所有字段可选）"""
    username: str | None = Field(None, min_length=2, max_length=64)
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    """用户响应"""
    id: uuid.UUID
    username: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserInDB(UserResponse):
    """数据库中的用户（含密码哈希，仅内部使用）"""
    hashed_password: str
