"""请求日志查询 API"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db.database import async_session_factory
from ..models.request_log import RequestLog
from ..models.user import User
from ..schemas.request_log import (
    RequestLogResponse,
    RequestLogListResponse,
)
from ..auth.dependencies import get_current_active_user, require_admin

router = APIRouter(prefix="/api/request-logs", tags=["请求日志"])


@router.get("", response_model=RequestLogListResponse)
async def list_request_logs(
    method: Optional[str] = Query(None, description="HTTP 方法过滤"),
    path: Optional[str] = Query(None, description="路径过滤（模糊匹配）"),
    status_code: Optional[int] = Query(None, description="状态码过滤"),
    user_id: Optional[UUID] = Query(None, description="用户 ID 过滤"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    min_duration: Optional[int] = Query(None, description="最小耗时（毫秒）"),
    max_duration: Optional[int] = Query(None, description="最大耗时（毫秒）"),
    has_error: Optional[bool] = Query(None, description="是否有错误"),
    is_llm_request: Optional[bool] = Query(None, description="是否为 LLM API 请求"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(require_admin),
):
    """
    查询请求日志列表
    
    需要管理员权限
    """
    async with async_session_factory() as db:
        # 构建查询条件
        conditions = []
        
        if method:
            conditions.append(RequestLog.method == method.upper())
        
        if path:
            conditions.append(RequestLog.path.ilike(f"%{path}%"))
        
        if status_code:
            conditions.append(RequestLog.status_code == status_code)
        
        if user_id:
            conditions.append(RequestLog.user_id == user_id)
        
        if start_time:
            conditions.append(RequestLog.created_at >= start_time)
        
        if end_time:
            conditions.append(RequestLog.created_at <= end_time)
        
        if min_duration is not None:
            conditions.append(RequestLog.duration_ms >= min_duration)
        
        if max_duration is not None:
            conditions.append(RequestLog.duration_ms <= max_duration)
        
        if has_error is not None:
            if has_error:
                conditions.append(RequestLog.error_message.isnot(None))
            else:
                conditions.append(RequestLog.error_message.is_(None))

        # LLM API 请求过滤
        if is_llm_request is not None and is_llm_request:
            llm_paths = [
                "/api/outline/generate",
                "/api/outline/generate-stream",
                "/api/content/generate",
                "/api/content/generate-stream",
                "/api/document/analyze",
                "/api/document/analyze-stream",
                "/api/knowledge/chat",
            ]
            conditions.append(
                or_(*[RequestLog.path.ilike(f"{path}%") for path in llm_paths])
            )

        # 查询总数
        count_query = select(func.count()).select_from(RequestLog)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # 计算分页
        offset = (page - 1) * page_size
        total_pages = (total + page_size - 1) // page_size
        
        # 查询数据
        query = (
            select(RequestLog)
            .options(selectinload(RequestLog.user))
            .order_by(desc(RequestLog.created_at))
            .offset(offset)
            .limit(page_size)
        )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        # 转换为响应模型
        items = []
        for log in logs:
            item = RequestLogResponse.model_validate(log)
            # 添加用户名
            if log.user:
                item.username = log.user.username
            items.append(item)
        
        return RequestLogListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


@router.get("/stats/summary")
async def get_request_stats(
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    current_user: User = Depends(require_admin),
):
    """
    获取请求统计摘要

    需要管理员权限
    """
    async with async_session_factory() as db:
        # 默认统计最近 24 小时
        if not start_time:
            start_time = datetime.utcnow() - timedelta(hours=24)
        if not end_time:
            end_time = datetime.utcnow()

        # 总请求数
        total_query = select(func.count()).select_from(RequestLog).where(
            RequestLog.created_at >= start_time,
            RequestLog.created_at <= end_time,
        )
        total_result = await db.execute(total_query)
        total_requests = total_result.scalar()

        # 成功请求数（2xx）
        success_query = select(func.count()).select_from(RequestLog).where(
            RequestLog.created_at >= start_time,
            RequestLog.created_at <= end_time,
            RequestLog.status_code >= 200,
            RequestLog.status_code < 300,
        )
        success_result = await db.execute(success_query)
        success_requests = success_result.scalar()

        # 客户端错误数（4xx）
        client_error_query = select(func.count()).select_from(RequestLog).where(
            RequestLog.created_at >= start_time,
            RequestLog.created_at <= end_time,
            RequestLog.status_code >= 400,
            RequestLog.status_code < 500,
        )
        client_error_result = await db.execute(client_error_query)
        client_errors = client_error_result.scalar()

        # 服务端错误数（5xx）
        server_error_query = select(func.count()).select_from(RequestLog).where(
            RequestLog.created_at >= start_time,
            RequestLog.created_at <= end_time,
            RequestLog.status_code >= 500,
        )
        server_error_result = await db.execute(server_error_query)
        server_errors = server_error_result.scalar()

        # 平均耗时
        avg_duration_query = select(func.avg(RequestLog.duration_ms)).where(
            RequestLog.created_at >= start_time,
            RequestLog.created_at <= end_time,
        )
        avg_duration_result = await db.execute(avg_duration_query)
        avg_duration = avg_duration_result.scalar() or 0

        # 最慢的 10 个请求
        slowest_query = (
            select(RequestLog)
            .where(
                RequestLog.created_at >= start_time,
                RequestLog.created_at <= end_time,
            )
            .order_by(desc(RequestLog.duration_ms))
            .limit(10)
        )
        slowest_result = await db.execute(slowest_query)
        slowest_requests = slowest_result.scalars().all()

        # 最热门的 10 个路径
        popular_paths_query = (
            select(
                RequestLog.path,
                func.count(RequestLog.id).label('count')
            )
            .where(
                RequestLog.created_at >= start_time,
                RequestLog.created_at <= end_time,
            )
            .group_by(RequestLog.path)
            .order_by(desc('count'))
            .limit(10)
        )
        popular_paths_result = await db.execute(popular_paths_query)
        popular_paths = popular_paths_result.all()

        return {
            "total_requests": total_requests,
            "success_requests": success_requests,
            "client_errors": client_errors,
            "server_errors": server_errors,
            "success_rate": (success_requests / total_requests * 100) if total_requests > 0 else 0,
            "avg_duration_ms": round(avg_duration, 2),
            "slowest_requests": [
                {
                    "path": req.path,
                    "method": req.method,
                    "duration_ms": req.duration_ms,
                    "created_at": req.created_at.isoformat(),
                }
                for req in slowest_requests
            ],
            "popular_paths": [
                {"path": path, "count": count}
                for path, count in popular_paths
            ],
        }


@router.get("/{log_id}", response_model=RequestLogResponse)
async def get_request_log(
    log_id: UUID,
    current_user: User = Depends(require_admin),
):
    """
    获取请求日志详情

    需要管理员权限
    """
    async with async_session_factory() as db:
        query = (
            select(RequestLog)
            .options(selectinload(RequestLog.user))
            .where(RequestLog.id == log_id)
        )

        result = await db.execute(query)
        log = result.scalar_one_or_none()

        if not log:
            raise HTTPException(status_code=404, detail="请求日志不存在")

        item = RequestLogResponse.model_validate(log)
        if log.user:
            item.username = log.user.username

        return item
