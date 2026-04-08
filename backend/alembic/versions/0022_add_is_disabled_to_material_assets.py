"""add is_disabled to material_assets

Revision ID: 0022_add_is_disabled_to_material_assets
Revises: 9cb4c6c07ce9
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0022_add_is_disabled_to_material_assets'
down_revision: Union[str, None] = '9cb4c6c07ce9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'material_assets',
        sa.Column(
            'is_disabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment='手动停用',
        ),
    )
    op.create_index('ix_material_assets_is_disabled', 'material_assets', ['is_disabled'])


def downgrade() -> None:
    op.drop_index('ix_material_assets_is_disabled', table_name='material_assets')
    op.drop_column('material_assets', 'is_disabled')
