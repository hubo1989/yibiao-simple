"""create project_versions table

Revision ID: 0005_create_project_versions
Revises: 0004_create_chapters
Create Date: 2026-02-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = "0005_create_project_versions"
down_revision: Union[str, None] = "0004_create_chapters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建变更类型枚举类型
    change_type = sa.Enum(
        "ai_generate",
        "manual_edit",
        "proofread",
        "rollback",
        name="change_type",
        native_enum=False,
        length=20,
    )
    change_type.create(op.get_bind(), checkfirst=True)

    # 创建 project_versions 表
    op.create_table(
        "project_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chapter_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chapters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("snapshot_data", JSONB, nullable=False),
        sa.Column(
            "change_type",
            change_type,
            nullable=False,
        ),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_versions")),
    )

    # 创建索引
    op.create_index(
        op.f("ix_project_versions_project_id"), "project_versions", ["project_id"]
    )
    op.create_index(
        op.f("ix_project_versions_chapter_id"), "project_versions", ["chapter_id"]
    )
    op.create_index(
        op.f("ix_project_versions_created_by"), "project_versions", ["created_by"]
    )
    # 复合唯一索引：按项目查询版本历史（按版本号降序），确保同一项目版本号唯一
    op.create_index(
        "ix_project_versions_project_version",
        "project_versions",
        ["project_id", "version_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_project_versions_project_version", table_name="project_versions")
    op.drop_index(op.f("ix_project_versions_created_by"), table_name="project_versions")
    op.drop_index(op.f("ix_project_versions_chapter_id"), table_name="project_versions")
    op.drop_index(op.f("ix_project_versions_project_id"), table_name="project_versions")
    op.drop_table("project_versions")

    # 删除枚举类型
    change_type = sa.Enum(
        "ai_generate",
        "manual_edit",
        "proofread",
        "rollback",
        name="change_type",
        native_enum=False,
        length=20,
    )
    change_type.drop(op.get_bind(), checkfirst=True)
