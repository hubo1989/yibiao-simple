"""create operation_logs table

Revision ID: 0006_create_operation_logs
Revises: 0005_create_project_versions
Create Date: 2026-02-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = "0006_create_operation_logs"
down_revision: Union[str, None] = "0005_create_project_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建操作类型枚举类型
    action_type = sa.Enum(
        "login", "logout", "register",
        "project_create", "project_update", "project_delete", "project_view",
        "chapter_create", "chapter_update", "chapter_delete",
        "version_create", "version_rollback",
        "ai_generate", "ai_proofread",
        "export_docx", "export_pdf",
        "settings_change",
        name="action_type",
        native_enum=False,
        length=30,
    )
    action_type.create(op.get_bind(), checkfirst=True)

    # 创建 operation_logs 表
    op.create_table(
        "operation_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "action",
            action_type,
            nullable=False,
        ),
        sa.Column("detail", JSONB, nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operation_logs")),
    )

    # 创建索引
    op.create_index(op.f("ix_operation_logs_user_id"), "operation_logs", ["user_id"])
    op.create_index(op.f("ix_operation_logs_project_id"), "operation_logs", ["project_id"])
    # 复合索引：按用户查询操作历史（按时间降序）
    op.create_index(
        "ix_operation_logs_user_time",
        "operation_logs",
        ["user_id", "created_at"],
    )
    # 复合索引：按项目查询操作历史（按时间降序）
    op.create_index(
        "ix_operation_logs_project_time",
        "operation_logs",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_operation_logs_project_time", table_name="operation_logs")
    op.drop_index("ix_operation_logs_user_time", table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_project_id"), table_name="operation_logs")
    op.drop_index(op.f("ix_operation_logs_user_id"), table_name="operation_logs")
    op.drop_table("operation_logs")

    # 删除枚举类型
    action_type = sa.Enum(
        "login", "logout", "register",
        "project_create", "project_update", "project_delete", "project_view",
        "chapter_create", "chapter_update", "chapter_delete",
        "version_create", "version_rollback",
        "ai_generate", "ai_proofread",
        "export_docx", "export_pdf",
        "settings_change",
        name="action_type",
        native_enum=False,
        length=30,
    )
    action_type.drop(op.get_bind(), checkfirst=True)
