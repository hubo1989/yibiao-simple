"""请求日志中间件"""
import logging
import re
import time
import uuid
import json
from typing import Any, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

from ..db.database import async_session_factory
from ..models.request_log import RequestLog
from ..auth.security import decode_token

# 配置请求日志专用 logger
request_logger = logging.getLogger("app.request")


# 敏感字段列表 - 这些字段不会被记录到日志中
SENSITIVE_FIELDS = {
    "password",
    "password_confirm",
    "hashed_password",
    "new_password",
    "old_password",
    "api_key",
    "api_key_encrypted",
    "api_key_secret",
    "token",
    "access_token",
    "refresh_token",
    "bearer_token",
    "jwt_token",
    "secret",
    "secret_key",
    "client_secret",
    "authorization",
    "auth_token",
    "session_token",
    "csrf_token",
    "otp",
    "totp_secret",
    "private_key",
    "private_key_pem",
    "credit_card",
    "card_number",
    "cvv",
    "cvc",
    "ssn",
    "social_security",
    "pin",
    "passphrase",
}

# 敏感字段模式
SENSITIVE_PATTERNS = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"\w+key\w*$", re.IGNORECASE),
    re.compile(r"auth", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
]

# 敏感请求头列表
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
}

# 不需要记录的路径模式
SKIP_PATTERNS = [
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/static/",
]


def _is_sensitive_field(field_name: str) -> bool:
    """检查字段名是否为敏感字段"""
    if not field_name:
        return False

    lower_name = field_name.lower()

    # 检查精确匹配
    if lower_name in SENSITIVE_FIELDS:
        return True

    # 检查模式匹配
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(field_name):
            return True

    return False


def sanitize_dict(data: dict[str, Any], sensitive_fields: set[str] | None = None, max_depth: int = 10, current_depth: int = 0) -> dict[str, Any]:
    """
    过滤字典中的敏感信息

    Args:
        data: 原始字典
        sensitive_fields: 敏感字段集合（兼容旧接口，优先使用内置模式）
        max_depth: 最大递归深度
        current_depth: 当前递归深度

    Returns:
        过滤后的字典，敏感字段值替换为 "***"
    """
    if not isinstance(data, dict):
        return data

    if current_depth >= max_depth:
        return {"_truncated": "max depth reached"}

    result = {}
    for key, value in data.items():
        # 使用传入的 sensitive_fields（兼容旧接口）或内置检测
        is_sensitive = False
        if sensitive_fields and key.lower() in sensitive_fields:
            is_sensitive = True
        elif _is_sensitive_field(key):
            is_sensitive = True

        if is_sensitive:
            result[key] = "***"
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, sensitive_fields, max_depth, current_depth + 1)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item, sensitive_fields, max_depth, current_depth + 1) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def should_skip_path(path: str) -> bool:
    """判断是否应该跳过该路径的日志记录"""
    return any(pattern in path for pattern in SKIP_PATTERNS)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件

    记录所有 API 请求和响应到 request_logs 表，包括：
    - 请求方法、路径、查询参数、请求头、请求体
    - 响应状态码、响应体
    - 请求耗时
    - 用户信息（如果已认证）
    - 客户端 IP 地址
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 检查是否跳过该路径
        if should_skip_path(request.url.path):
            return await call_next(request)
        
        # 缓存请求体（因为请求体只能读取一次）
        request_body = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    request_body = json.loads(body_bytes)
                    # 将请求体缓存到 request.state 中
                    request.state.cached_body = body_bytes
            except Exception:
                pass

        # 记录开始时间
        start_time = time.time()

        # 执行请求
        try:
            response = await call_next(request)
            
            # 计算耗时
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 获取响应体
            response_body = None
            if not isinstance(response, StreamingResponse):
                try:
                    # 尝试读取响应体
                    response_body_bytes = b""
                    async for chunk in response.body_iterator:
                        response_body_bytes += chunk
                    
                    # 重新创建响应，因为 body_iterator 已经被消费
                    response = Response(
                        content=response_body_bytes,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                        background=response.background,
                    )
                    
                    # 尝试解析 JSON 响应
                    if response_body_bytes:
                        try:
                            response_body = json.loads(response_body_bytes)
                        except Exception:
                            # 如果不是 JSON，存储为字符串（截取前1000字符）
                            response_body = {"raw": response_body_bytes[:1000].decode('utf-8', errors='ignore')}
                except Exception:
                    pass
            
            # 记录请求日志
            await self._log_request(request, response, duration_ms, request_body, response_body)
            
            return response
            
        except Exception as e:
            # 计算耗时
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 记录错误请求
            error_response = Response(content=str(e), status_code=500)
            await self._log_request(
                request, error_response, duration_ms, request_body, 
                {"error": str(e)}, error_message=str(e)
            )
            
            raise

    async def _log_request(
        self,
        request: Request,
        response: Response,
        duration_ms: int,
        request_body: dict[str, Any] | None,
        response_body: dict[str, Any] | None,
        error_message: str | None = None,
    ) -> None:
        """
        记录请求到数据库

        Args:
            request: FastAPI 请求对象
            response: 响应对象
            duration_ms: 请求耗时（毫秒）
            request_body: 请求体
            response_body: 响应体
            error_message: 错误信息
        """
        try:
            # 获取用户信息
            user_id = await self._get_user_id(request)

            # 获取客户端 IP
            ip_address = self._get_client_ip(request)

            # 获取并过滤请求头
            request_headers = dict(request.headers)
            request_headers = sanitize_dict(request_headers, SENSITIVE_HEADERS)

            # 过滤请求体中的敏感信息
            if request_body:
                request_body = sanitize_dict(request_body, SENSITIVE_FIELDS)

            # 过滤响应体中的敏感信息
            if response_body:
                response_body = sanitize_dict(response_body, SENSITIVE_FIELDS)

            # 获取查询参数
            query_params = dict(request.query_params)

            # 写入数据库
            async with async_session_factory() as db:
                log_entry = RequestLog(
                    user_id=user_id,
                    method=request.method,
                    path=request.url.path,
                    query_params=query_params,
                    request_headers=request_headers,
                    request_body=request_body,
                    status_code=response.status_code,
                    response_body=response_body,
                    duration_ms=duration_ms,
                    ip_address=ip_address,
                    user_agent=request.headers.get("user-agent", ""),
                    error_message=error_message,
                )
                db.add(log_entry)
                await db.commit()

        except Exception as e:
            # 日志记录失败不应影响请求响应
            request_logger.error(f"Request logging error: {e}", exc_info=True)

    async def _get_user_id(self, request: Request) -> uuid.UUID | None:
        """从请求中获取用户 ID"""
        try:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                payload = decode_token(token)
                if payload:
                    user_id_str = payload.get("sub")
                    if user_id_str:
                        return uuid.UUID(user_id_str)
        except Exception:
            pass
        return None

    def _get_client_ip(self, request: Request) -> str | None:
        """获取客户端真实 IP 地址"""
        # 检查代理头
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # 取第一个 IP（最原始的客户端）
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # 直接连接的客户端
        if request.client:
            return request.client.host

        return None
