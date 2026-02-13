"""管理员 API 路由"""
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy import select, func, or_, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..db.database import get_db
from ..models.user import User, UserRole
from ..models.project import Project
from ..models.api_key_config import ApiKeyConfig
from ..models.operation_log import OperationLog, ActionType
from ..schemas.api_key_config import (
    ApiKeyConfigCreate,
    ApiKeyConfigUpdate,
    ApiKeyConfigResponse,
    ApiKeyConfigListResponse,
)
from ..schemas.operation_log import (
    OperationLogList,
    OperationLogSummary,
    OperationLogDetail,
    AuditLogQuery,
)
from ..schemas.user import (
    UserResponse,
    UserListResponse,
    AdminUserCreate,
    AdminUserUpdate,
    ResetPasswordRequest,
    UsageStatsResponse,
)
from ..auth.dependencies import require_admin
from ..auth.security import get_password_hash
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


@router.get("/logs", response_model=OperationLogList)
async def list_operation_logs(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: uuid.UUID | None = Query(None, description="按用户 ID 筛选"),
    username: str | None = Query(None, description="按用户名筛选（模糊匹配）"),
    project_id: uuid.UUID | None = Query(None, description="按项目 ID 筛选"),
    action: ActionType | None = Query(None, description="按操作类型筛选"),
    start_time: datetime | None = Query(None, description="开始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    ip_address: str | None = Query(None, description="按 IP 地址筛选"),
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """
    查询操作日志（仅管理员）

    支持按用户、项目、操作类型、时间范围、IP 地址筛选
    支持分页查询
    """
    # 构建基础查询
    base_query = select(OperationLog)

    # 应用筛选条件
    conditions = []

    if user_id:
        conditions.append(OperationLog.user_id == user_id)

    if username:
        # 通过用户名筛选，需要 join users 表
        base_query = base_query.join(User, OperationLog.user_id == User.id, isouter=True)
        conditions.append(User.username.ilike(f"%{username}%"))

    if project_id:
        conditions.append(OperationLog.project_id == project_id)

    if action:
        conditions.append(OperationLog.action == action)

    if start_time:
        conditions.append(OperationLog.created_at >= start_time)

    if end_time:
        conditions.append(OperationLog.created_at <= end_time)

    if ip_address:
        conditions.append(OperationLog.ip_address.ilike(f"%{ip_address}%"))

    # 组合所有条件
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # 查询总数
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    query = base_query.order_by(OperationLog.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    logs = result.scalars().all()

    # 转换为响应模型
    items = [OperationLogSummary.from_orm_with_detail(log) for log in logs]

    return OperationLogList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/logs/{log_id}", response_model=OperationLogDetail)
async def get_operation_log_detail(
    log_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    获取操作日志详情（仅管理员）

    返回完整的日志信息，包括用户名和项目名称
    """
    # 查询日志，同时加载关联的用户和项目
    query = (
        select(OperationLog)
        .options(
            joinedload(OperationLog.user),
            joinedload(OperationLog.project),
        )
        .where(OperationLog.id == log_id)
    )

    result = await db.execute(query)
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="操作日志不存在",
        )

    # 构建详细响应
    return OperationLogDetail(
        id=log.id,
        user_id=log.user_id,
        project_id=log.project_id,
        action=log.action,
        detail=log.detail,
        ip_address=log.ip_address,
        created_at=log.created_at,
        username=log.user.username if log.user else None,
        project_name=log.project.name if log.project else None,
    )


@router.get("/logs/stats/actions", response_model=dict)
async def get_action_stats(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_time: datetime | None = Query(None, description="开始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
):
    """
    获取操作类型统计（仅管理员）

    返回各操作类型的数量统计
    """
    # 构建查询
    query = select(
        OperationLog.action,
        func.count(OperationLog.id).label("count"),
    ).group_by(OperationLog.action)

    # 应用时间筛选
    conditions = []
    if start_time:
        conditions.append(OperationLog.created_at >= start_time)
    if end_time:
        conditions.append(OperationLog.created_at <= end_time)

    if conditions:
        query = query.where(and_(*conditions))

    result = await db.execute(query)
    rows = result.all()

    # 构建响应
    stats = {row.action.value: row.count for row in rows}

    return {
        "total": sum(stats.values()),
        "by_action": stats,
    }


# ==================== 用户管理接口 ====================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    username: str | None = Query(None, description="按用户名筛选（模糊匹配）"),
    email: str | None = Query(None, description="按邮箱筛选（模糊匹配）"),
    role: UserRole | None = Query(None, description="按角色筛选"),
    is_active: bool | None = Query(None, description="按启用状态筛选"),
    page: int = Query(1, ge=1, description="页码（从 1 开始）"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """
    获取用户列表（仅管理员）

    支持按用户名、邮箱、角色、启用状态筛选
    支持分页查询
    """
    # 构建基础查询
    base_query = select(User)

    # 应用筛选条件
    conditions = []

    if username:
        conditions.append(User.username.ilike(f"%{username}%"))

    if email:
        conditions.append(User.email.ilike(f"%{email}%"))

    if role:
        conditions.append(User.role == role)

    if is_active is not None:
        conditions.append(User.is_active == is_active)

    if conditions:
        base_query = base_query.where(and_(*conditions))

    # 查询总数
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    query = base_query.order_by(User.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: AdminUserCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    创建用户（仅管理员）

    管理员可以创建新用户并指定角色和初始密码
    """
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已存在",
        )

    # 创建用户
    new_user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role=data.role,
        is_active=data.is_active,
    )

    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    更新用户信息（仅管理员）

    管理员可以修改用户的用户名、邮箱、角色和启用状态
    """
    # 查找用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 防止管理员禁用自己
    if user.id == current_user.id and data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用自己的账户",
        )

    # 检查用户名是否与其他用户冲突
    if data.username and data.username != user.username:
        result = await db.execute(select(User).where(User.username == data.username))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在",
            )
        user.username = data.username

    # 检查邮箱是否与其他用户冲突
    if data.email and data.email != user.email:
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已存在",
            )
        user.email = data.email

    # 更新角色
    if data.role:
        user.role = data.role

    # 更新启用状态
    if data.is_active is not None:
        user.is_active = data.is_active

    await db.flush()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/reset-password", response_model=UserResponse)
async def reset_user_password(
    user_id: uuid.UUID,
    data: ResetPasswordRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    重置用户密码（仅管理员）

    管理员可以为用户设置新密码
    """
    # 查找用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 更新密码
    user.hashed_password = get_password_hash(data.new_password)

    await db.flush()
    await db.refresh(user)

    return UserResponse.model_validate(user)


# ==================== 使用统计接口 ====================

@router.get("/stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    获取使用统计（仅管理员）

    返回总项目数、总用户数、活跃用户数、本月生成次数和 Token 消耗估算
    """
    # 总项目数
    projects_result = await db.execute(select(func.count(Project.id)))
    total_projects = projects_result.scalar() or 0

    # 总用户数
    users_result = await db.execute(select(func.count(User.id)))
    total_users = users_result.scalar() or 0

    # 活跃用户数（is_active = True）
    active_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    active_users = active_users_result.scalar() or 0

    # 计算本月开始时间
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 本月生成次数（统计所有内容生成相关的操作）
    generation_actions = [
        ActionType.AI_GENERATE,
        ActionType.AI_PROOFREAD,
        ActionType.CONSISTENCY_CHECK,
    ]

    monthly_generations_result = await db.execute(
        select(func.count(OperationLog.id)).where(
            and_(
                OperationLog.created_at >= month_start,
                OperationLog.action.in_(generation_actions),
            )
        )
    )
    monthly_generations = monthly_generations_result.scalar() or 0

    # Token 消耗估算（基于生成次数 × 估算平均值 2000 tokens）
    # 这是一个简化估算，实际应该记录每次 API 调用的 token 使用量
    estimated_tokens = monthly_generations * 2000

    return UsageStatsResponse(
        total_projects=total_projects,
        total_users=total_users,
        active_users=active_users,
        monthly_generations=monthly_generations,
        estimated_tokens=estimated_tokens,
    )
