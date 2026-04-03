"""认证路由：注册、登录、获取当前用户"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.user import User, UserRole
from ..schemas.auth import (
    UserRegister,
    UserLogin,
    Token,
    TokenResponseWithCsrf,
    UserMe,
)
from ..auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    set_refresh_token_cookie,
    get_refresh_token_from_cookie,
)
from ..auth.dependencies import get_current_user, get_current_active_user
from ..auth.csrf import generate_csrf_token, validate_csrf_token

# 导入速率限制器（如果可用）
try:
    from ..main import limiter
except (ImportError, AttributeError):
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    limiter = DummyLimiter()

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.get("/csrf-token")
async def get_csrf_token(
    response: Response,
) -> dict:
    """获取 CSRF token（用于初始登录前的预请求）"""
    csrf_token = generate_csrf_token()

    # 设置 CSRF cookie
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        path="/",
        samesite="lax",
        secure=False,  # 生产环境应设为 True
    )

    return {"csrf_token": csrf_token}


@router.post("/register", response_model=TokenResponseWithCsrf, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    user_data: UserRegister,
    response: Response,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponseWithCsrf:
    """用户注册"""
    # 检查用户名或邮箱是否已存在
    result = await db.execute(
        select(User).where(
            or_(User.username == user_data.username, User.email == user_data.email)
        )
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.username == user_data.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已被注册",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册",
            )

    # 创建新用户
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        role=UserRole.EDITOR,
        is_active=True,
    )

    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    # 生成令牌
    token_subject = str(new_user.id)
    access_token = create_access_token(
        subject=token_subject,
        additional_claims={"role": new_user.role.value},
    )
    refresh_token = create_refresh_token(
        subject=token_subject,
        additional_claims={"role": new_user.role.value},
    )

    # 设置 refresh token 为 httpOnly cookie
    cookie_config = set_refresh_token_cookie(access_token, refresh_token, request)
    response.set_cookie(**cookie_config)

    # 生成 CSRF token
    csrf_token = generate_csrf_token()

    # 设置 CSRF cookie
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        path="/",
        samesite="lax",
        secure=False,
    )

    return TokenResponseWithCsrf(
        access_token=access_token,
        csrf_token=csrf_token,
        token_type="bearer",
    )


@router.post("/login", response_model=TokenResponseWithCsrf)
@limiter.limit("10/minute")
async def login(
    credentials: UserLogin,
    response: Response,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponseWithCsrf:
    """用户登录"""
    # 支持用户名或邮箱登录
    result = await db.execute(
        select(User).where(
            or_(
                User.username == credentials.username,
                User.email == credentials.username,
            )
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账户已被禁用",
        )

    # 生成令牌
    token_subject = str(user.id)
    access_token = create_access_token(
        subject=token_subject,
        additional_claims={"role": user.role.value},
    )
    refresh_token = create_refresh_token(
        subject=token_subject,
        additional_claims={"role": user.role.value},
    )

    # 设置 refresh token 为 httpOnly cookie
    cookie_config = set_refresh_token_cookie(access_token, refresh_token, request)
    response.set_cookie(**cookie_config)

    # 生成 CSRF token
    csrf_token = generate_csrf_token()

    # 设置 CSRF cookie
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        path="/",
        samesite="lax",
        secure=False,
    )

    return TokenResponseWithCsrf(
        access_token=access_token,
        csrf_token=csrf_token,
        token_type="bearer",
    )


@router.get("/me", response_model=UserMe)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserMe:
    """获取当前用户信息"""
    return UserMe.model_validate(current_user)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    response: Response,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """使用刷新令牌获取新的访问令牌（从 httpOnly cookie 读取）"""
    # 从 cookie 获取 refresh token
    refresh_token = get_refresh_token_from_cookie(request)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少刷新令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(refresh_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查是否是刷新令牌
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌类型错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌载荷",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 验证用户是否存在且活跃
    result = await db.execute(select(User).where(User.id == user_id_str))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 生成新令牌
    token_subject = str(user.id)
    access_token = create_access_token(
        subject=token_subject,
        additional_claims={"role": user.role.value},
    )
    new_refresh_token = create_refresh_token(
        subject=token_subject,
        additional_claims={"role": user.role.value},
    )

    # 设置新的 refresh token cookie
    cookie_config = set_refresh_token_cookie(access_token, new_refresh_token, request)
    response.set_cookie(**cookie_config)

    # 生成新的 CSRF token
    csrf_token = generate_csrf_token()

    # 更新 CSRF cookie
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        path="/",
        samesite="lax",
        secure=False,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
    )


@router.post("/logout")
async def logout(response: Response) -> dict:
    """登出用户（清除 refresh token cookie）"""
    response.delete_cookie(
        key="refresh_token",
        path="/",
        httponly=True,
        samesite="lax",
    )
    return {"message": "登出成功"}
