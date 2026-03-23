from __future__ import annotations

"""请求日志 ORM 模型"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User


class RequestLog(Base):
    """请求日志表 - 记录所有API请求和响应"""
    __tablename__ = "request_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="操作用户 ID（未认证时为空）"
    )
    method: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="HTTP 方法 (GET, POST, PUT, DELETE 等)"
    )
    path: Mapped[str] = mapped_column(
        String(500), nullable=False,
        index=True,
        comment="请求路径"
    )
    query_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="查询参数"
    )
    request_headers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="请求头（过滤敏感信息）"
    )
    request_body: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True,
        comment="请求体（过滤敏感信息）"
    )
    status_code: Mapped[int] = mapped_column(
        Integer, nullable=False,
        index=True,
        comment="HTTP 状态码"
    )
    response_body: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True,
        comment="响应体"
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="请求耗时（毫秒）"
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True,
        comment="客户端 IP 地址"
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="用户代理"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="错误信息（如果请求失败）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        index=True,
        comment="创建时间"
    )

    # 关系
    user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id], backref="request_logs"
    )

    def __repr__(self) -> str:
        return f"<RequestLog {self.method} {self.path} - {self.status_code}>"
