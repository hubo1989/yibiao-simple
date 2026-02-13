"""create comments table

Revision ID: 0008_create_comments
Revises: 0007_create_api_key_configs
Create Date: 2026-02-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "0008_create_comments"
down_revision: Union[str, None] = "0007_create_api_key_configs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 comments 表
    op.create_table(
        "comments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chapter_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("position_start", sa.Integer, nullable=True),
        sa.Column("position_end", sa.Integer, nullable=True),
        sa.Column("is_resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "resolved_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comments")),
    )

    # 创建索引
    op.create_index(op.f("ix_comments_chapter_id"), "comments", ["chapter_id"])
    op.create_index(op.f("ix_comments_user_id"), "comments", ["user_id"])
    op.create_index(op.f("ix_comments_is_resolved"), "comments", ["is_resolved"])


def downgrade() -> None:
    op.drop_index(op.f("ix_comments_is_resolved"), table_name="comments")
    op.drop_index(op.f("ix_comments_user_id"), table_name="comments")
    op.drop_index(op.f("ix_comments_chapter_id"), table_name="comments")
    op.drop_table("comments")
