"""create chapters table

Revision ID: 0004_create_chapters
Revises: 0003_create_projects
Create Date: 2026-02-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "0004_create_chapters"
down_revision: Union[str, None] = "0003_create_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建章节状态枚举类型
    chapter_status = sa.Enum(
        "pending", "generated", "reviewing", "finalized",
        name="chapter_status",
        native_enum=False,
        length=20,
    )
    chapter_status.create(op.get_bind(), checkfirst=True)

    # 创建 chapters 表
    op.create_table(
        "chapters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("chapter_number", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column(
            "status",
            chapter_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "locked_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chapters")),
    )

    # 创建索引
    op.create_index(op.f("ix_chapters_project_id"), "chapters", ["project_id"])
    op.create_index(op.f("ix_chapters_parent_id"), "chapters", ["parent_id"])
    op.create_index(op.f("ix_chapters_chapter_number"), "chapters", ["chapter_number"])
    op.create_index(op.f("ix_chapters_locked_by"), "chapters", ["locked_by"])


def downgrade() -> None:
    op.drop_index(op.f("ix_chapters_locked_by"), table_name="chapters")
    op.drop_index(op.f("ix_chapters_chapter_number"), table_name="chapters")
    op.drop_index(op.f("ix_chapters_parent_id"), table_name="chapters")
    op.drop_index(op.f("ix_chapters_project_id"), table_name="chapters")
    op.drop_table("chapters")

    # 删除枚举类型
    chapter_status = sa.Enum(
        "pending", "generated", "reviewing", "finalized",
        name="chapter_status",
        native_enum=False,
        length=20,
    )
    chapter_status.drop(op.get_bind(), checkfirst=True)
