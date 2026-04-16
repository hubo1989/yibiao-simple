"""FastAPI应用主入口"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, Request
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
import os

from .config import settings
from .db.database import engine
from .routers import config, document, outline, content, search, expand, auth, admin, projects, versions, chapters, comments, templates, knowledge, request_logs, materials, ingestion, review, export_template, disqualification, scoring
from .middleware import AuditMiddleware, RequestLoggingMiddleware
from .auth.csrf import CSRFMiddleware


# ========== 速率限制中间件 ==========
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address)
except ImportError:
    # 如果 slowapi 未安装，创建一个空装饰器
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    limiter = DummyLimiter()


# ========== 安全响应头中间件 ==========
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """添加安全响应头"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 基本安全头（所有环境）
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 内容安全策略
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        # 生产环境额外安全头
        if settings.env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时验证数据库连接，关闭时释放连接池"""
    # startup
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    # shutdown
    await engine.dispose()


# 创建FastAPI应用实例
# 包装 slowapi 的状态
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="基于FastAPI的AI写标书助手后端API",
        lifespan=lifespan,
        state=limiter._state,  # type: ignore
    )
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except (ImportError, AttributeError):
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="基于FastAPI的AI写标书助手后端API",
        lifespan=lifespan,
    )

# 添加CORS中间件 - 生产环境严格限制
if settings.env == "production":
    # 生产环境：只允许配置的来源，不使用通配符
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    )
else:
    # 开发环境：较为宽松
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 添加安全响应头中间件
app.add_middleware(SecurityHeadersMiddleware)

# 添加 CSRF 保护中间件
app.add_middleware(CSRFMiddleware)

# 添加请求日志中间件
app.add_middleware(RequestLoggingMiddleware)

# 添加审计日志中间件
app.add_middleware(AuditMiddleware)

# 注册路由
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(projects.router)
app.include_router(templates.router)
app.include_router(knowledge.router)
app.include_router(materials.router)
app.include_router(ingestion.router)
app.include_router(versions.router)
app.include_router(chapters.router)
app.include_router(comments.router)
app.include_router(config.router)
app.include_router(document.router)
app.include_router(outline.router)
app.include_router(content.router)
app.include_router(search.router)
app.include_router(expand.router)
app.include_router(request_logs.router)
app.include_router(review.router)
app.include_router(export_template.router)
app.include_router(disqualification.router)
app.include_router(scoring.router)

# 健康检查端点
@app.get("/health")
@limiter.limit("60/minute")  # 全局速率限制
async def health_check(request: Request):
    """健康检查"""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version
    }

# uploads 目录静态文件服务（素材/知识库文件访问）
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

# 静态文件服务（用于服务前端构建文件）
if os.path.exists("static"):
    # 挂载静态资源文件夹
    app.mount("/static", StaticFiles(directory="static/static"), name="static")
    
    # 处理React应用的路由（SPA路由支持）
    @app.get("/")
    async def read_index():
        """根路径，返回前端首页"""
        return FileResponse("static/index.html")
    
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """处理React路由，所有非API路径都返回index.html"""
        # 排除API路径
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("health"):
            # 这些路径应该由FastAPI处理，如果到这里说明404
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="API endpoint not found")

        # 路径遍历防护：使用绝对路径规范化，确保不逃逸出 static 目录
        static_dir = os.path.abspath("static")
        requested_path = os.path.abspath(os.path.join("static", full_path))

        # 确保请求的路径在 static 目录内
        if not requested_path.startswith(static_dir + os.sep) and requested_path != static_dir:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid path")

        # 检查是否是静态文件
        if os.path.exists(requested_path) and os.path.isfile(requested_path):
            return FileResponse(requested_path)

        # 对于其他所有路径，返回React应用的index.html（SPA路由）
        return FileResponse("static/index.html")
else:
    # 如果没有静态文件，返回API信息
    @app.get("/")
    async def read_root():
        """根路径，返回API信息"""
        return {
            "message": f"欢迎使用 {settings.app_name} API",
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health"
        }
