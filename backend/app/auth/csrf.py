"""CSRF 保护配置（内置实现）"""
from secrets import token_hex
from typing import Callable
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    简单的 CSRF 保护中间件

    工作原理：
    1. 在响应中设置 csrf_token cookie（非 httpOnly，前端可读）
    2. 对于状态变更请求（POST/PUT/DELETE/PATCH），验证请求头中的 X-CSRF-Token
    """

    # 不需要 CSRF 验证的路径
    EXEMPT_PATHS = {
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/csrf-token",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    async def dispatch(self, request: Request, call_next: Callable):
        # 处理请求
        response = await call_next(request)

        # 对于 exempt 路径，生成并设置 CSRF token
        if request.url.path in self.EXEMPT_PATHS or request.url.path.startswith("/static"):
            csrf_token = token_hex(32)
            response.set_cookie(
                key="csrf_token",
                value=csrf_token,
                httponly=False,  # 前端需要读取
                path="/",
                samesite="lax",
                secure=False,  # 生产环境应设为 True
            )

        return response


async def validate_csrf_token(request: Request) -> None:
    """
    验证 CSRF token（依赖注入）

    对于状态变更请求（POST/PUT/DELETE/PATCH），验证 X-CSRF-Token header
    """
    # 只验证状态变更方法
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    # 排除 exempt 路径
    if request.url.path in CSRFMiddleware.EXEMPT_PATHS:
        return

    # 获取 cookie 中的 CSRF token
    csrf_token_cookie = request.cookies.get("csrf_token")
    if not csrf_token_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token 缺失",
        )

    # 获取 header 中的 CSRF token
    csrf_token_header = request.headers.get("X-CSRF-Token")
    if not csrf_token_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token header 缺失",
        )

    # 验证 token 是否匹配
    if csrf_token_cookie != csrf_token_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token 验证失败",
        )


def generate_csrf_token() -> str:
    """生成新的 CSRF token"""
    return token_hex(32)
