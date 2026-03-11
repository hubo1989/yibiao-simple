"""add vector index support

Revision ID: 0016_vector_index_support
Revises: 0015_multi_model_api_keys
Create Date: 2026-03-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0016_vector_index_support"
down_revision: Union[str, None] = "0015_multi_model_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 启用 pgvector 扩展
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # 在 knowledge_docs 表添加向量索引状态字段
    op.add_column(
        "knowledge_docs",
        sa.Column(
            "vector_index_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
            comment="向量索引状态: pending/indexing/completed/failed",
        ),
    )

    op.add_column(
        "knowledge_docs",
        sa.Column(
            "vector_index_error",
            sa.Text(),
            nullable=True,
            comment="向量索引错误信息",
        ),
    )

    # 创建 knowledge_doc_chunks 表
    op.create_table(
        "knowledge_doc_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "knowledge_docs.id",
                ondelete="CASCADE",
            ),
            nullable=False,
            comment="关联的文档ID",
        ),
        sa.Column(
            "chunk_index",
            sa.Integer(),
            nullable=False,
            comment="分块索引",
        ),
        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
            comment="分块内容",
        ),
        sa.Column(
            "embedding",
            sa.Text(),
            nullable=True,
            comment="向量嵌入数据（pgvector类型），使用Text作为ORM占位符",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=True,
            comment="分块元数据",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
            comment="创建时间",
        ),
    )

    # 创建索引以提高查询性能
    op.create_index(
        "ix_knowledge_doc_chunks_doc_id",
        "knowledge_doc_chunks",
        ["doc_id"],
    )

    op.create_index(
        "ix_knowledge_doc_chunks_chunk_index",
        "knowledge_doc_chunks",
        ["chunk_index"],
    )


def downgrade() -> None:
    # 删除 knowledge_doc_chunks 表
    op.drop_table("knowledge_doc_chunks")

    # 删除 knowledge_docs 表中添加的字段
    op.drop_column("knowledge_docs", "vector_index_error")
    op.drop_column("knowledge_docs", "vector_index_status")

    # 注意：pgvector 扩展通常不删除，因为可能被其他表使用
    # 如果需要删除，可以使用: op.execute('DROP EXTENSION IF EXISTS vector CASCADE')
