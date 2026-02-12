"""操作日志 ORM 模型"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base

if TYPE_CHECKING:
    from .user import User
    from .project import Project


class ActionType(str, PyEnum):
    """操作类型枚举"""
    # 用户认证
    LOGIN = "login"                     # 登录
    LOGOUT = "logout"                   # 登出
    REGISTER = "register"               # 注册

    # 项目操作
    PROJECT_CREATE = "project_create"   # 创建项目
    PROJECT_UPDATE = "project_update"   # 更新项目
    PROJECT_DELETE = "project_delete"   # 删除项目
    PROJECT_VIEW = "project_view"       # 查看项目

    # 章节操作
    CHAPTER_CREATE = "chapter_create"   # 创建章节
    CHAPTER_UPDATE = "chapter_update"   # 更新章节
    CHAPTER_DELETE = "chapter_delete"   # 删除章节
    CHAPTER_STATUS_CHANGE = "chapter_status_change"  # 章节状态变更

    # 版本操作
    VERSION_CREATE = "version_create"   # 创建版本
    VERSION_ROLLBACK = "version_rollback"  # 版本回滚

    # AI 操作
    AI_GENERATE = "ai_generate"         # AI 生成内容
    AI_PROOFREAD = "ai_proofread"       # AI 校对
    CONSISTENCY_CHECK = "consistency_check"  # 跨章节一致性检查

    # 导出操作
    EXPORT_DOCX = "export_docx"         # 导出 Word
    EXPORT_PDF = "export_pdf"           # 导出 PDF

    # 系统操作
    SETTINGS_CHANGE = "settings_change"  # 设置变更


class OperationLog(Base):
    """操作日志表 - 记录用户操作行为"""
    __tablename__ = "operation_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="操作用户 ID（系统操作时为空）"
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联项目 ID（非项目操作时为空）"
    )
    action: Mapped[ActionType] = mapped_column(
        Enum(ActionType, name="action_type", native_enum=False, length=30),
        nullable=False,
        comment="操作类型"
    )
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="操作详情（JSON 格式）"
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True,
        comment="客户端 IP 地址（支持 IPv6）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 关系
    user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id], backref="operation_logs"
    )
    project: Mapped["Project | None"] = relationship(
        "Project", foreign_keys=[project_id], backref="operation_logs"
    )

    def __repr__(self) -> str:
        return f"<OperationLog {self.action} by user:{self.user_id}>"
