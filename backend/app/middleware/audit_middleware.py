"""操作日志审计中间件"""
import time
import uuid
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import async_session_factory
from ..models.operation_log import OperationLog, ActionType
from ..models.user import User
from ..auth.security import decode_token


# 敏感字段列表 - 这些字段不会被记录到日志中
SENSITIVE_FIELDS = {
    "password",
    "password_confirm",
    "hashed_password",
    "api_key",
    "api_key_encrypted",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "authorization",
}

# 端点到操作类型的映射
ENDPOINT_ACTION_MAP: dict[str, ActionType] = {
    # 认证相关
    "/api/auth/register": ActionType.REGISTER,
    "/api/auth/login": ActionType.LOGIN,
    "/api/auth/logout": ActionType.LOGOUT,
    # 项目相关
    "/api/projects": ActionType.PROJECT_CREATE,  # POST
    # 版本相关
    "/api/versions": ActionType.VERSION_CREATE,  # POST
    # AI 相关
    "/api/outline/generate": ActionType.AI_GENERATE,
    "/api/outline/generate-stream": ActionType.AI_GENERATE,
    "/api/content/generate": ActionType.AI_GENERATE,
    "/api/content/generate-stream": ActionType.AI_GENERATE,
    "/api/proofread": ActionType.AI_PROOFREAD,
    "/api/consistency-check": ActionType.CONSISTENCY_CHECK,
    # 导出相关
    "/api/export/docx": ActionType.EXPORT_DOCX,
    "/api/export/pdf": ActionType.EXPORT_PDF,
    # 配置相关
    "/api/admin/api-keys": ActionType.SETTINGS_CHANGE,  # POST/PUT/DELETE
}

# 需要额外记录详情的端点模式
DETAILED_LOG_PATTERNS = [
    "/api/projects",  # 项目创建/更新/删除
    "/api/versions",  # 版本操作
    "/api/outline/generate",  # AI 生成
    "/api/proofread",  # AI 校对
    "/api/consistency-check",  # 一致性检查
    "/api/export",  # 导出操作
    "/api/admin/api-keys",  # 配置变更
]


def sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    过滤字典中的敏感信息

    Args:
        data: 原始字典

    Returns:
        过滤后的字典，敏感字段值替换为 "***"
    """
    result = {}
    for key, value in data.items():
        lower_key = key.lower()
        # 检查是否是敏感字段
        if lower_key in SENSITIVE_FIELDS or any(
            sensitive in lower_key for sensitive in ["password", "secret", "token", "key"]
        ):
            result[key] = "***"
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def get_action_type(method: str, path: str) -> ActionType | None:
    """
    根据请求方法和路径确定操作类型

    Args:
        method: HTTP 方法
        path: 请求路径

    Returns:
        操作类型，如果不需要记录则返回 None
    """
    # GET 请求不记录
    if method == "GET":
        return None

    # 检查精确匹配
    if path in ENDPOINT_ACTION_MAP:
        return ENDPOINT_ACTION_MAP[path]

    # 检查精确路径（项目/章节 ID 是 UUID 格式）
    # /api/projects/{uuid} 形式
    import re
    uuid_pattern = r"/api/projects/[\da-f-]{36}"

    if re.match(uuid_pattern, path):
        if method == "PUT" or method == "PATCH":
            return ActionType.PROJECT_UPDATE
        elif method == "DELETE":
            return ActionType.PROJECT_DELETE

    # /api/chapters/{uuid} 形式
    chapter_uuid_pattern = r"/api/chapters/[\da-f-]{36}"
    if re.match(chapter_uuid_pattern, path):
        if method == "PUT" or method == "PATCH":
            return ActionType.CHAPTER_UPDATE
        elif method == "DELETE":
            return ActionType.CHAPTER_DELETE

    # 检查模式匹配
    for pattern, action_type in ENDPOINT_ACTION_MAP.items():
        if path.startswith(pattern):
            return action_type

    # 根据路径和方法推断操作类型
    if path.startswith("/api/projects"):
        if method == "POST" and path == "/api/projects":
            return ActionType.PROJECT_CREATE
        elif method in ("PUT", "PATCH"):
            return ActionType.PROJECT_UPDATE
        elif method == "DELETE":
            return ActionType.PROJECT_DELETE
    elif path.startswith("/api/chapters"):
        if method == "POST" and path == "/api/chapters":
            return ActionType.CHAPTER_CREATE
        elif method in ("PUT", "PATCH"):
            return ActionType.CHAPTER_UPDATE
        elif method == "DELETE":
            return ActionType.CHAPTER_DELETE
    elif path.startswith("/api/versions") and method == "POST":
        return ActionType.VERSION_CREATE
    elif path.startswith("/api/export"):
        if "docx" in path:
            return ActionType.EXPORT_DOCX
        elif "pdf" in path:
            return ActionType.EXPORT_PDF
    elif path.startswith("/api/admin/api-keys"):
        return ActionType.SETTINGS_CHANGE

    return None


def should_log_detail(path: str) -> bool:
    """判断是否需要记录详细日志"""
    return any(pattern in path for pattern in DETAILED_LOG_PATTERNS)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    审计日志中间件

    自动记录所有非 GET 请求到 operation_logs 表，包括：
    - 用户信息（如果已认证）
    - 端点和请求方法
    - 请求耗时
    - 客户端 IP 地址
    - 操作详情（过滤敏感信息）
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 记录开始时间
        start_time = time.time()

        # 执行请求
        response = await call_next(request)

        # 计算耗时
        duration_ms = int((time.time() - start_time) * 1000)

        # 只记录非 GET 请求
        if request.method != "GET":
            await self._log_request(request, response, duration_ms)

        return response

    async def _log_request(
        self, request: Request, response: Response, duration_ms: int
    ) -> None:
        """
        记录请求到数据库

        Args:
            request: FastAPI 请求对象
            response: 响应对象
            duration_ms: 请求耗时（毫秒）
        """
        try:
            # 获取操作类型
            action_type = get_action_type(request.method, request.url.path)

            # 如果无法确定操作类型，跳过日志记录
            if action_type is None:
                return

            # 获取用户信息
            user_id = await self._get_user_id(request)

            # 获取客户端 IP
            ip_address = self._get_client_ip(request)

            # 获取项目 ID（如果存在）
            project_id = await self._get_project_id(request)

            # 构建操作详情
            detail = {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }

            # 对于关键业务操作，记录更多信息
            if should_log_detail(request.url.path):
                detail["user_agent"] = request.headers.get("user-agent", "")
                # 尝试获取请求体（注意：只能读取一次）
                try:
                    body = await self._get_request_body(request)
                    if body:
                        detail["request_body"] = sanitize_dict(body)
                except Exception:
                    pass

            # 写入数据库
            async with async_session_factory() as db:
                log_entry = OperationLog(
                    user_id=user_id,
                    project_id=project_id,
                    action=action_type,
                    detail=detail,
                    ip_address=ip_address,
                )
                db.add(log_entry)
                await db.commit()

        except Exception as e:
            # 日志记录失败不应影响请求响应
            # 在生产环境中应该使用 logging 模块记录错误
            print(f"Audit log error: {e}")

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

    async def _get_project_id(self, request: Request) -> uuid.UUID | None:
        """从请求路径或体中获取项目 ID"""
        try:
            # 从路径参数获取
            path_parts = request.url.path.split("/")
            for i, part in enumerate(path_parts):
                if part == "projects" and i + 1 < len(path_parts):
                    try:
                        return uuid.UUID(path_parts[i + 1])
                    except ValueError:
                        continue

            # 从请求体获取
            body = await self._get_request_body(request)
            if body and "project_id" in body:
                return uuid.UUID(body["project_id"])
        except Exception:
            pass
        return None

    async def _get_request_body(self, request: Request) -> dict[str, Any] | None:
        """
        获取请求体

        注意：这个方法有局限性，因为请求体通常只能读取一次
        在实际使用中，可能需要在请求处理前缓存请求体
        """
        try:
            # 尝试从请求状态中获取已缓存的请求体
            cached_body = getattr(request.state, "cached_body", None)
            if cached_body:
                import json
                return json.loads(cached_body)

            # 直接读取（可能失败，因为已被读取）
            body_bytes = await request.body()
            if body_bytes:
                import json
                return json.loads(body_bytes)
        except Exception:
            pass
        return None
