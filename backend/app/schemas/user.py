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


class UserListResponse(BaseModel):
    """用户列表响应（分页）"""
    items: list[UserResponse]
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")


class AdminUserCreate(BaseModel):
    """管理员创建用户请求"""
    username: str = Field(..., min_length=2, max_length=64, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    role: UserRole = Field(default=UserRole.EDITOR, description="用户角色")
    is_active: bool = Field(default=True, description="是否启用")


class AdminUserUpdate(BaseModel):
    """管理员更新用户请求"""
    username: str | None = Field(None, min_length=2, max_length=64, description="用户名")
    email: EmailStr | None = Field(None, description="邮箱地址")
    role: UserRole | None = Field(None, description="用户角色")
    is_active: bool | None = Field(None, description="是否启用")


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")


class UsageStatsResponse(BaseModel):
    """使用统计响应"""
    total_projects: int = Field(..., description="总项目数")
    total_users: int = Field(..., description="总用户数")
    active_users: int = Field(..., description="活跃用户数")
    monthly_generations: int = Field(..., description="本月生成次数")
    estimated_tokens: int = Field(..., description="Token 消耗估算")
