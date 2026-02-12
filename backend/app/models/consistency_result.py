"""跨章节一致性检查结果 ORM 模型"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Text, DateTime, ForeignKey, func, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class ConsistencySeverity(str, PyEnum):
    """矛盾严重程度"""
    CRITICAL = "critical"  # 严重矛盾，可能导致失分或废标
    WARNING = "warning"    # 一般不一致，建议统一
    INFO = "info"          # 轻微差异，可以优化


class ConsistencyCategory(str, PyEnum):
    """矛盾类别"""
    DATA = "data"              # 数据矛盾：同一数据在不同章节中数值不一致
    TERMINOLOGY = "terminology"  # 术语矛盾：同一概念使用不同术语
    TIMELINE = "timeline"      # 时间线矛盾：项目计划时间节点冲突
    COMMITMENT = "commitment"  # 承诺矛盾：服务承诺或保证不一致
    SCOPE = "scope"           # 范围矛盾：工作范围描述不一致


class ConsistencyResult(Base):
    """一致性检查结果表 - 存储跨章节一致性检查的结果"""
    __tablename__ = "consistency_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    contradictions: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="矛盾列表（JSON 格式）"
    )
    summary: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="整体一致性评估摘要"
    )
    overall_consistency: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="整体一致性评估: consistent/minor_issues/major_issues"
    )
    contradiction_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="矛盾总数"
    )
    critical_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="严重矛盾数量"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project", foreign_keys=[project_id], backref="consistency_results"
    )

    def __repr__(self) -> str:
        return f"<ConsistencyResult {self.id} project={self.project_id}>"
