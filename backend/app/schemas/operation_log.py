"""操作日志相关 Pydantic schema"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..models.operation_log import ActionType


class OperationLogBase(BaseModel):
    """操作日志基础字段"""
    action: ActionType = Field(..., description="操作类型")
    detail: dict[str, Any] = Field(default_factory=dict, description="操作详情")
    ip_address: str | None = Field(None, max_length=45, description="客户端 IP 地址")


class OperationLogCreate(OperationLogBase):
    """创建操作日志请求"""
    user_id: uuid.UUID | None = Field(None, description="操作用户 ID")
    project_id: uuid.UUID | None = Field(None, description="关联项目 ID")


class OperationLogResponse(OperationLogBase):
    """操作日志响应"""
    id: uuid.UUID
    user_id: uuid.UUID | None
    project_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OperationLogSummary(BaseModel):
    """操作日志摘要（列表用）"""
    id: uuid.UUID
    user_id: uuid.UUID | None
    project_id: uuid.UUID | None
    action: ActionType
    ip_address: str | None
    created_at: datetime
    # 包含部分详细信息便于审计
    method: str | None = Field(None, description="HTTP 方法")
    path: str | None = Field(None, description="请求路径")
    status_code: int | None = Field(None, description="响应状态码")
    duration_ms: int | None = Field(None, description="请求耗时(毫秒)")

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_detail(cls, log: "OperationLog") -> "OperationLogSummary":
        """从 ORM 对象创建，提取 detail 中的信息"""
        detail = log.detail or {}
        return cls(
            id=log.id,
            user_id=log.user_id,
            project_id=log.project_id,
            action=log.action,
            ip_address=log.ip_address,
            created_at=log.created_at,
            method=detail.get("method"),
            path=detail.get("path"),
            status_code=detail.get("status_code"),
            duration_ms=detail.get("duration_ms"),
        )


class OperationLogList(BaseModel):
    """操作日志列表响应"""
    items: list[OperationLogSummary]
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")


class OperationLogFilter(BaseModel):
    """操作日志筛选条件"""
    user_id: uuid.UUID | None = Field(None, description="按用户筛选")
    project_id: uuid.UUID | None = Field(None, description="按项目筛选")
    action: ActionType | None = Field(None, description="按操作类型筛选")
    start_time: datetime | None = Field(None, description="开始时间")
    end_time: datetime | None = Field(None, description="结束时间")


class AuditLogQuery(BaseModel):
    """审计日志查询参数"""
    user_id: uuid.UUID | None = Field(None, description="按用户 ID 筛选")
    username: str | None = Field(None, description="按用户名筛选（模糊匹配）")
    project_id: uuid.UUID | None = Field(None, description="按项目 ID 筛选")
    action: ActionType | None = Field(None, description="按操作类型筛选")
    start_time: datetime | None = Field(None, description="开始时间")
    end_time: datetime | None = Field(None, description="结束时间")
    ip_address: str | None = Field(None, description="按 IP 地址筛选")
    page: int = Field(1, ge=1, description="页码（从 1 开始）")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class OperationLogDetail(OperationLogResponse):
    """操作日志详情（包含完整信息）"""
    username: str | None = Field(None, description="用户名")
    project_name: str | None = Field(None, description="项目名称")


# 用于类型提示的导入
from ..models.operation_log import OperationLog
