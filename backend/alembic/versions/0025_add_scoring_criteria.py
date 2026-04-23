"""add_scoring_criteria

Revision ID: 0025_add_scoring_criteria
Revises: 0023_add_export_templates
Create Date: 2026-04-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0025_add_scoring_criteria'
down_revision: Union[str, None] = '0023_add_export_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scoring_criteria',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('item_id', sa.String(20), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('item', sa.String(200), nullable=False),
        sa.Column('max_score', sa.Float(), nullable=True),
        sa.Column('scoring_rule', sa.Text(), nullable=True),
        sa.Column('keywords', postgresql.JSONB(), nullable=True),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('bound_chapter_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('chapters.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scoring_criteria_project_id', 'scoring_criteria', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_scoring_criteria_project_id', table_name='scoring_criteria')
    op.drop_table('scoring_criteria')
