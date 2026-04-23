"""add_disqualification_checks

Revision ID: 0024_add_disqualification_checks
Revises: 0023_add_export_templates
Create Date: 2026-04-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0024_add_disqualification_checks'
down_revision: Union[str, None] = '0023_add_export_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'disqualification_checks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('item_id', sa.String(20), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('requirement', sa.Text(), nullable=False),
        sa.Column('check_type', sa.String(20), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False, server_default='fatal'),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='unchecked'),
        sa.Column('checked_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_disqualification_checks_project_id', 'disqualification_checks', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_disqualification_checks_project_id', table_name='disqualification_checks')
    op.drop_table('disqualification_checks')
