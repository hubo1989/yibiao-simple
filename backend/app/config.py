"""应用配置管理"""
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from typing import Optional, List, Union
import os
import secrets
import json


def parse_cors_origins(value: Union[str, List[str], None]) -> List[str]:
    """解析 CORS 来源配置，支持 JSON 数组或逗号分隔的字符串"""
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        # 尝试解析为 JSON 数组
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

        # 尝试解析为逗号分隔的字符串
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    return []


class Settings(BaseSettings):
    """应用设置"""
    app_name: str = "AI写标书助手"
    app_version: str = "2.0.0"
    debug: bool = False

    # CORS设置 - 支持环境变量注入
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
        "http://localhost:3004",
        "http://127.0.0.1:3004",
        "http://localhost",
        "http://127.0.0.1",
    ]

    # 文件上传设置
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    upload_dir: str = "uploads"

    # 数据库设置 - 支持环境变量注入
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/yibiao"

    # OpenAI默认设置
    default_model: str = "gpt-3.5-turbo"

    # JWT 认证设置 - 支持环境变量注入
    secret_key: str = secrets.token_urlsafe(32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    class Config:
        env_file = ".env"
        # 支持从环境变量读取复杂类型
        env_parse_none_str = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 处理 CORS_ORIGINS 环境变量
        cors_env = os.getenv("CORS_ORIGINS")
        if cors_env:
            self.cors_origins = parse_cors_origins(cors_env)


# 全局设置实例
settings = Settings()

# 确保上传目录存在
os.makedirs(settings.upload_dir, exist_ok=True)