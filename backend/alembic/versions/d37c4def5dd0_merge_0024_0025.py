"""merge_0024_0025

Revision ID: d37c4def5dd0
Revises: 0024_add_disqualification_checks, 0025_add_scoring_criteria
Create Date: 2026-04-16 23:25:19.822216
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd37c4def5dd0'
down_revision: Union[str, None] = ('0024_add_disqualification_checks', '0025_add_scoring_criteria')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
