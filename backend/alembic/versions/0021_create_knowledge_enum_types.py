"""create knowledge enum types

KnowledgeDoc model uses SQLEnum (native PostgreSQL enums) but the table was
created with VARCHAR columns. This migration creates the enum types and alters
the columns to use them.

Revision ID: 0021_knowledge_enum_types
Revises: 0020_llamaindex_vector_store
Create Date: 2026-03-24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0021_knowledge_enum_types"
down_revision: Union[str, None] = "0020_llamaindex_vector_store"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENUM_DEFS = {
    "doctype": ["history_bid", "company_info", "case_fragment", "other"],
    "contentsource": ["file", "manual"],
    "indexstatus": ["pending", "indexing", "completed", "failed"],
    "scope": ["global", "enterprise", "user"],
}

COLUMN_ALTERS = [
    ("doc_type", "doctype"),
    ("content_source", "contentsource"),
    ("pageindex_status", "indexstatus"),
    ("scope", "scope"),
]


def upgrade() -> None:
    # Create enum types
    for enum_name, values in ENUM_DEFS.items():
        values_str = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({values_str})")

    # Alter columns from varchar to enum
    for col_name, enum_name in COLUMN_ALTERS:
        op.execute(
            f"ALTER TABLE knowledge_docs ALTER COLUMN {col_name} TYPE {enum_name} "
            f"USING {col_name}::{enum_name}"
        )


def downgrade() -> None:
    # Revert columns back to varchar
    for col_name, _ in COLUMN_ALTERS:
        op.execute(
            f"ALTER TABLE knowledge_docs ALTER COLUMN {col_name} TYPE varchar "
            f"USING {col_name}::varchar"
        )

    # Drop enum types
    for enum_name in ENUM_DEFS:
        op.execute(f"DROP TYPE {enum_name}")
