"""merge_heads_for_p3

Revision ID: 9cb4c6c07ce9
Revises: 0018_create_bid_review_tasks, 0021_knowledge_enum_types
Create Date: 2026-04-08 20:57:13.844183
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9cb4c6c07ce9'
down_revision: Union[str, None] = ('0018_create_bid_review_tasks', '0021_knowledge_enum_types')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
