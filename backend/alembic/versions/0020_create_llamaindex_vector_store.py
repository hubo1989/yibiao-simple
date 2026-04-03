"""add llamaindex vector store fields

Revision ID: 0020_llamaindex_vector_store
Revises: 0019_ingestion_and_material_source_fields
Create Date: 2026-03-24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0020_llamaindex_vector_store"
down_revision: Union[str, None] = "0019_ingestion_and_material_source_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 确保 pgvector 扩展已启用
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # 添加 index_backend 和 index_version 字段
    op.add_column(
        "knowledge_docs",
        sa.Column(
            "index_backend",
            sa.String(length=20),
            nullable=False,
            server_default="llamaindex",
            comment="索引后端: llamaindex",
        ),
    )
    op.add_column(
        "knowledge_docs",
        sa.Column(
            "index_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="索引版本号",
        ),
    )

def downgrade() -> None:
    op.drop_column("knowledge_docs", "index_version")
    op.drop_column("knowledge_docs", "index_backend")
