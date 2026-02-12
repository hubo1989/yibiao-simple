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

    model_config = {"from_attributes": True}


class OperationLogList(BaseModel):
    """操作日志列表响应"""
    items: list[OperationLogSummary]
    total: int = Field(..., description="总数量")


class OperationLogFilter(BaseModel):
    """操作日志筛选条件"""
    user_id: uuid.UUID | None = Field(None, description="按用户筛选")
    project_id: uuid.UUID | None = Field(None, description="按项目筛选")
    action: ActionType | None = Field(None, description="按操作类型筛选")
    start_time: datetime | None = Field(None, description="开始时间")
    end_time: datetime | None = Field(None, description="结束时间")
