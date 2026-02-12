"""create projects table

Revision ID: 0003_create_projects
Revises: 0002_create_users
Create Date: 2026-02-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "0003_create_projects"
down_revision: Union[str, None] = "0002_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建枚举类型
    project_status = sa.Enum(
        "draft", "in_progress", "reviewing", "completed",
        name="project_status",
        native_enum=False,
        length=20,
    )
    project_member_role = sa.Enum(
        "owner", "editor", "reviewer",
        name="project_member_role",
        native_enum=False,
        length=20,
    )
    project_status.create(op.get_bind(), checkfirst=True)
    project_member_role.create(op.get_bind(), checkfirst=True)

    # 创建 projects 表
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "creator_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            project_status,
            nullable=False,
            server_default="draft",
        ),
        sa.Column("file_content", sa.Text, nullable=True),
        sa.Column("project_overview", sa.Text, nullable=True),
        sa.Column("tech_requirements", sa.Text, nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(op.f("ix_projects_name"), "projects", ["name"])
    op.create_index(op.f("ix_projects_creator_id"), "projects", ["creator_id"])

    # 创建 project_members 关联表
    op.create_table(
        "project_members",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role",
            project_member_role,
            nullable=False,
            server_default="editor",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("user_id", "project_id", name=op.f("pk_project_members")),
    )


def downgrade() -> None:
    op.drop_table("project_members")
    op.drop_index(op.f("ix_projects_creator_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_name"), table_name="projects")
    op.drop_table("projects")

    # 删除枚举类型
    project_status = sa.Enum(
        "draft", "in_progress", "reviewing", "completed",
        name="project_status",
        native_enum=False,
        length=20,
    )
    project_member_role = sa.Enum(
        "owner", "editor", "reviewer",
        name="project_member_role",
        native_enum=False,
        length=20,
    )
    project_status.drop(op.get_bind(), checkfirst=True)
    project_member_role.drop(op.get_bind(), checkfirst=True)
