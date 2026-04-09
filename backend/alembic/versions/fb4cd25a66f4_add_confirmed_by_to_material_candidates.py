"""add confirmed_by to material_candidates

Revision ID: fb4cd25a66f4
Revises: 0022_add_is_disabled_to_material_assets
Create Date: 2026-04-09 11:02:21.524855
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fb4cd25a66f4'
down_revision: Union[str, None] = '0022_add_is_disabled_to_material_assets'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'material_candidates',
        sa.Column('confirmed_by', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_material_candidates_confirmed_by',
        'material_candidates',
        'users',
        ['confirmed_by'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_material_candidates_confirmed_by', 'material_candidates', type_='foreignkey')
    op.drop_column('material_candidates', 'confirmed_by')
