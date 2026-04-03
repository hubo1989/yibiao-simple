"""create bid_review_tasks table

Revision ID: 0018_create_bid_review_tasks
Revises: 0017_add_outline_binding_fields_to_chapters
Create Date: 2026-03-26 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = "0018_create_bid_review_tasks"
down_revision = "0017_add_outline_binding_fields_to_chapters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bid_review_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id", UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False, index=True
        ),
        sa.Column(
            "created_by", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True
        ),
        sa.Column(
            "status", sa.Enum(
                "pending", "processing", "completed", "failed",
                name="review_task_status", native_enum=False, length=20
            ),
            nullable=False, server_default="pending"
        ),
        sa.Column("bid_file_path", sa.String(500), nullable=False, comment="投标文件磁盘路径"),
        sa.Column("bid_filename", sa.String(255), nullable=False, comment="投标文件原始文件名"),
        sa.Column("bid_content", sa.Text(), nullable=True, comment="投标文件提取文本"),
        sa.Column("paragraph_index", JSONB(), nullable=True, comment="文档段落索引"),
        sa.Column("dimensions", JSONB(), nullable=False, comment="审查维度列表"),
        sa.Column("scope", sa.String(20), nullable=False, server_default="full", comment="审查范围"),
        sa.Column("model_name", sa.String(100), nullable=True, comment="使用的模型名称"),
        sa.Column(
            "provider_config_id", UUID(as_uuid=True),
            sa.ForeignKey("api_key_configs.id", ondelete="SET NULL"),
            nullable=True
        ),
        sa.Column("responsiveness_result", JSONB(), nullable=True, comment="响应性审查结果"),
        sa.Column("compliance_result", JSONB(), nullable=True, comment="合规性审查结果"),
        sa.Column("consistency_result", JSONB(), nullable=True, comment="一致性审查结果"),
        sa.Column("summary", JSONB(), nullable=True, comment="审查汇总"),
        sa.Column("error_message", sa.Text(), nullable=True, comment="失败时的错误信息"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True),
            nullable=True, comment="审查完成时间"
        ),
    )


def downgrade() -> None:
    op.drop_table("bid_review_tasks")
    op.execute("DROP TYPE IF EXISTS review_task_status")
