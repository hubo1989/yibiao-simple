"""安全工具：密码哈希和 JWT 生成/验证"""
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import jwt, JWTError
from fastapi import Request

from ..config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否匹配"""
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def create_access_token(
    subject: str | dict,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """创建访问令牌"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode: dict[str, Any] = {"exp": expire}
    if isinstance(subject, str):
        to_encode["sub"] = subject
    else:
        to_encode.update(subject)

    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def create_refresh_token(
    subject: str | dict,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """创建刷新令牌"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )

    to_encode: dict[str, Any] = {"exp": expire, "type": "refresh"}
    if isinstance(subject, str):
        to_encode["sub"] = subject
    else:
        to_encode.update(subject)

    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """解码并验证 JWT 令牌"""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        return None


def get_refresh_token_from_cookie(request: Request) -> str | None:
    """从 httpOnly cookie 获取 refresh token"""
    return request.cookies.get("refresh_token")


def set_refresh_token_cookie(
    access_token: str,
    refresh_token: str,
    request: Request,
) -> dict:
    """设置 refresh token 为 httpOnly cookie"""
    from datetime import datetime, timedelta, timezone

    # 计算 cookie 过期时间
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )

    return {
        "key": "refresh_token",
        "value": refresh_token,
        "httponly": True,
        "expires": expire,
        "path": "/",
        "samesite": "lax",
        "secure": False,  # 生产环境应设为 True（需要 HTTPS）
    }
