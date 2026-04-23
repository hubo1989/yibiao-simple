"""应用配置管理"""

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseSettings
    SettingsConfigDict = dict  # type: ignore[assignment]
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_parse_none_str="",
    )

    app_name: str = "AI写标书助手"
    app_version: str = "2.0.0"
    debug: bool = False
    env: str = "development"  # development | production

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
        "http://localhost:3033",
        "http://127.0.0.1:3033",
        "http://localhost:3088",
        "http://127.0.0.1:3088",
        "http://localhost",
        "http://127.0.0.1",
    ]

    # 文件上传设置
    max_file_size: int = 50 * 1024 * 1024  # 50MB（招标文件常超 10MB）
    upload_dir: str = "uploads"

    # 数据库设置 - 支持环境变量注入
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/yibiao"

    # LlamaIndex 知识库设置
    knowledge_vector_backend: str = "llamaindex"
    embedding_model: str = "qwen3-embedding:4b"
    embedding_dimension: int = 2560
    ollama_base_url: str = "http://localhost:11434"
    knowledge_chunk_size: int = 512
    knowledge_chunk_overlap: int = 50
    knowledge_top_k: int = 5
    knowledge_vector_table: str = "knowledge_nodes"

    # OpenAI默认设置
    default_model: str = "gpt-3.5-turbo"

    # JWT 认证设置 - 支持环境变量注入
    secret_key: Optional[str] = None
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.secret_key is None:
            env_secret = os.getenv("SECRET_KEY")
            if env_secret:
                self.secret_key = env_secret
            else:
                # 生产环境必须设置 SECRET_KEY
                if self.env == "production":
                    raise ValueError(
                        "生产环境必须设置 SECRET_KEY 环境变量！"
                        "请设置强随机密钥，例如: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                    )
                # 开发环境使用默认值并发出警告
                import warnings
                warnings.warn(
                    "SECRET_KEY 环境变量未设置，使用开发默认值。"
                    "生产环境必须设置 SECRET_KEY 环境变量！",
                    UserWarning,
                )
                self.secret_key = "dev-secret-key-do-not-use-in-production-12345"
        cors_env = os.getenv("CORS_ORIGINS")
        if cors_env:
            self.cors_origins = parse_cors_origins(cors_env)

# 全局设置实例
settings = Settings()

# 确保上传目录存在
os.makedirs(settings.upload_dir, exist_ok=True)
