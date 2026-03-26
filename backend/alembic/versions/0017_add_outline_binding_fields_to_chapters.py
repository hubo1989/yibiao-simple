"""add outline binding fields to chapters

Revision ID: 0017_add_outline_binding_fields_to_chapters
Revises: 0016_add_vector_index_support
Create Date: 2026-03-11 09:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0017_add_outline_binding_fields_to_chapters"
down_revision = "0016_vector_index_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chapters", sa.Column("rating_item", sa.Text(), nullable=True, comment="当前章节绑定的评分项原文或摘要"))
    op.add_column("chapters", sa.Column("chapter_role", sa.Text(), nullable=True, comment="当前章节主职责定位"))
    op.add_column("chapters", sa.Column("avoid_overlap", sa.Text(), nullable=True, comment="当前章节与其他章节的去重边界"))


def downgrade() -> None:
    op.drop_column("chapters", "avoid_overlap")
    op.drop_column("chapters", "chapter_role")
    op.drop_column("chapters", "rating_item")
