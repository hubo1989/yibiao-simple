"""请求日志相关的 Pydantic schemas"""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RequestLogBase(BaseModel):
    """请求日志基础模型"""
    method: str = Field(..., description="HTTP 方法")
    path: str = Field(..., description="请求路径")
    status_code: int = Field(..., description="HTTP 状态码")
    duration_ms: int = Field(..., description="请求耗时（毫秒）")


class RequestLogResponse(RequestLogBase):
    """请求日志响应模型"""
    id: UUID = Field(..., description="日志 ID")
    user_id: Optional[UUID] = Field(None, description="用户 ID")
    query_params: dict[str, Any] = Field(default_factory=dict, description="查询参数")
    request_headers: dict[str, Any] = Field(default_factory=dict, description="请求头")
    request_body: Optional[dict[str, Any]] = Field(None, description="请求体")
    response_body: Optional[dict[str, Any]] = Field(None, description="响应体")
    ip_address: Optional[str] = Field(None, description="客户端 IP")
    user_agent: Optional[str] = Field(None, description="用户代理")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    
    # 用户信息（可选，通过 join 获取）
    username: Optional[str] = Field(None, description="用户名")

    class Config:
        from_attributes = True


class RequestLogListResponse(BaseModel):
    """请求日志列表响应"""
    items: list[RequestLogResponse] = Field(..., description="日志列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")


class RequestLogQuery(BaseModel):
    """请求日志查询参数"""
    method: Optional[str] = Field(None, description="HTTP 方法过滤")
    path: Optional[str] = Field(None, description="路径过滤（模糊匹配）")
    status_code: Optional[int] = Field(None, description="状态码过滤")
    user_id: Optional[UUID] = Field(None, description="用户 ID 过滤")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    min_duration: Optional[int] = Field(None, description="最小耗时（毫秒）")
    max_duration: Optional[int] = Field(None, description="最大耗时（毫秒）")
    has_error: Optional[bool] = Field(None, description="是否有错误")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
