"""add_consistency_checks — 为 consistency_results 添加 warning_count 字段

Revision ID: 0027_add_consistency_checks
Revises: d37c4def5dd0
Create Date: 2026-04-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0027_add_consistency_checks'
down_revision: Union[str, None] = '0026_add_chapter_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 warning_count 字段（补充原表缺少的 warning 级别计数）
    op.add_column(
        'consistency_results',
        sa.Column('warning_count', sa.Integer(), nullable=False, server_default='0',
                  comment='一般不一致数量'),
    )


def downgrade() -> None:
    op.drop_column('consistency_results', 'warning_count')
