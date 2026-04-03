"""
统一日志配置模块

提供结构化日志配置，支持 JSON 格式输出（可选）。

使用方式:
    from app.logging_config import setup_logging
    setup_logging()

    logger = logging.getLogger("app.module")
    logger.info("message", extra={"key": "value"})
"""
import logging
import logging.config
import sys
from pathlib import Path
from typing import Any


# JSON 格式化器（可选，需要 python-json-logger）
try:
    from pythonjsonlogger import jsonlogger

    class JsonFormatter(jsonlogger.JsonFormatter):
        """结构化 JSON 日志格式化器"""

        def add_fields(
            self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]
        ) -> None:
            super().add_fields(log_record, record, message_dict)
            # 添加额外字段
            log_record["logger"] = record.name
            log_record["level"] = record.levelname
            log_record["timestamp"] = self.formatTime(record, self.datefmt)

    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False


class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""

    # ANSI 颜色代码
    COLORS = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        return super().format(record)


def get_default_logging_config(use_json: bool = False, log_level: str = "INFO") -> dict[str, Any]:
    """
    获取默认日志配置

    Args:
        use_json: 是否使用 JSON 格式输出
        log_level: 日志级别

    Returns:
        logging.config.dictConfig 格式的配置字典
    """
    log_format = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if not use_json
        else "%(asctime)s %(name)s %(levelname)s %(message)s"
    )

    formatter_class = "pythonjsonlogger.jsonlogger.JsonFormatter" if use_json and HAS_JSON_LOGGER else None

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": log_format,
                "class": formatter_class,
            } if use_json and HAS_JSON_LOGGER else {
                "()": "app.logging_config.ColoredFormatter",
                "format": log_format,
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "detailed",
                "filename": "logs/app.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": "logs/error.log",
                "maxBytes": 10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {  # root logger
                "level": log_level,
                "handlers": ["console"],
            },
            "app": {
                "level": log_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "app.audit": {
                "level": "INFO",
                "handlers": ["file", "error_file"],
                "propagate": False,
            },
            "app.request": {
                "level": "INFO",
                "handlers": ["file", "error_file"],
                "propagate": False,
            },
            # 第三方库日志级别控制
            "uvicorn": {"level": "INFO"},
            "uvicorn.access": {"level": "INFO"},
            "uvicorn.error": {"level": "INFO"},
            "sqlalchemy": {"level": "WARNING"},
            "sqlalchemy.engine": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
        },
    }


def setup_logging(
    use_json: bool = False,
    log_level: str = "INFO",
    log_dir: str = "logs",
) -> None:
    """
    设置应用日志配置

    Args:
        use_json: 是否使用 JSON 格式输出（生产环境推荐）
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: 日志文件目录
    """
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # 更新日志配置中的文件路径
    config = get_default_logging_config(use_json=use_json, log_level=log_level)
    config["handlers"]["file"]["filename"] = str(log_path / "app.log")
    config["handlers"]["error_file"]["filename"] = str(log_path / "error.log")

    # 应用配置
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """
    获取已配置的 logger

    Args:
        name: logger 名称，建议使用 "app.module" 格式

    Returns:
        logging.Logger 实例
    """
    return logging.getLogger(name)


# 预配置的专用 logger
def get_audit_logger() -> logging.Logger:
    """获取审计日志专用 logger"""
    return logging.getLogger("app.audit")


def get_request_logger() -> logging.Logger:
    """获取请求日志专用 logger"""
    return logging.getLogger("app.request")


def get_security_logger() -> logging.Logger:
    """获取安全事件日志专用 logger"""
    return logging.getLogger("app.security")
