"""create api_key_configs table

Revision ID: 0007_create_api_key_configs
Revises: 0006_create_operation_logs
Create Date: 2026-02-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "0007_create_api_key_configs"
down_revision: Union[str, None] = "0006_create_operation_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 api_key_configs 表
    op.create_table(
        "api_key_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "provider",
            sa.String(64),
            nullable=False,
            comment="提供商名称，如 openai, anthropic",
        ),
        sa.Column(
            "api_key_encrypted",
            sa.Text,
            nullable=False,
            comment="加密后的 API Key",
        ),
        sa.Column(
            "base_url",
            sa.String(512),
            nullable=True,
            comment="API 基础 URL",
        ),
        sa.Column(
            "model_name",
            sa.String(128),
            nullable=False,
            server_default="gpt-3.5-turbo",
            comment="默认模型名称",
        ),
        sa.Column(
            "is_default",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
            comment="是否为默认配置",
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="创建者 ID",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_key_configs")),
    )

    # 创建索引
    op.create_index(op.f("ix_api_key_configs_provider"), "api_key_configs", ["provider"])
    op.create_index(op.f("ix_api_key_configs_is_default"), "api_key_configs", ["is_default"])


def downgrade() -> None:
    op.drop_index(op.f("ix_api_key_configs_is_default"), table_name="api_key_configs")
    op.drop_index(op.f("ix_api_key_configs_provider"), table_name="api_key_configs")
    op.drop_table("api_key_configs")
