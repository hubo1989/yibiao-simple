"""全局提示词 ORM 模型"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, func, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class PromptCategory(str, PyEnum):
    """提示词类别枚举"""
    ANALYSIS = "analysis"      # 解析类：doc_analysis_overview, doc_analysis_requirements, outline_extract
    GENERATION = "generation"  # 生成类：chapter_content, outline_l1, outline_l2l3
    CHECK = "check"            # 检查类：proofread, consistency_check


class GlobalPrompt(Base):
    """全局提示词配置表"""
    __tablename__ = "global_prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scene_key: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True,
        comment="场景标识，如 doc_analysis_overview, chapter_content"
    )
    scene_name: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="场景中文名称，如 文档分析-项目概述"
    )
    category: Mapped[PromptCategory] = mapped_column(
        Enum(PromptCategory, name="prompt_category", native_enum=False, length=20),
        nullable=False,
        comment="提示词类别：analysis/generation/check"
    )
    prompt: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="完整提示词（包含系统指令和用户输入模板）"
    )
    available_vars: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="可用变量列表及其描述"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="当前版本号"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 关系
    versions = relationship("GlobalPromptVersion", back_populates="global_prompt", order_by="GlobalPromptVersion.version.desc()")

    def __repr__(self) -> str:
        return f"<GlobalPrompt {self.scene_key} v{self.version}>"


class GlobalPromptVersion(Base):
    """全局提示词版本历史表"""
    __tablename__ = "global_prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    global_prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("global_prompts.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="版本号"
    )
    prompt: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="该版本的完整提示词"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="创建该版本的用户"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 关系
    global_prompt = relationship("GlobalPrompt", back_populates="versions")

    def __repr__(self) -> str:
        return f"<GlobalPromptVersion {self.global_prompt_id} v{self.version}>"
