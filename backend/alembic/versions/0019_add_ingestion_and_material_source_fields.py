"""add ingestion and material source fields

Revision ID: 0019
Revises: 0018_create_material_library_tables
Create Date: 2026-03-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0019_ingestion_and_material_source_fields'
down_revision: Union[str, None] = '0018_create_material_library_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 为 material_assets 增加溯源字段
    op.add_column('material_assets', sa.Column('source_document_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('material_assets', sa.Column('source_page_from', sa.Integer(), nullable=True))
    op.add_column('material_assets', sa.Column('source_page_to', sa.Integer(), nullable=True))
    op.add_column('material_assets', sa.Column('source_excerpt', sa.Text(), nullable=True))
    op.add_column('material_assets', sa.Column('extraction_method', sa.String(20), nullable=True))

    # 创建索引
    op.create_index(op.f('ix_material_assets_source_document_id'), 'material_assets', ['source_document_id'], unique=False)

    # 添加外键
    op.create_foreign_key(
        'fk_material_assets_source_document_id',
        'material_assets',
        'knowledge_docs',
        ['source_document_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # 2. 创建 ingestion_tasks 表
    op.create_table(
        'ingestion_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='ingestiontaskstatus'), nullable=False),
        sa.Column('total_candidates', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confirmed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rejected_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processing_log', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['knowledge_docs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    )

    op.create_index(op.f('ix_ingestion_tasks_id'), 'ingestion_tasks', ['id'], unique=False)
    op.create_index(op.f('ix_ingestion_tasks_document_id'), 'ingestion_tasks', ['document_id'], unique=False)
    op.create_index(op.f('ix_ingestion_tasks_created_by'), 'ingestion_tasks', ['created_by'], unique=False)
    op.create_index(op.f('ix_ingestion_tasks_status'), 'ingestion_tasks', ['status'], unique=False)

    # 3. 创建 material_candidates 表
    op.create_table(
        'material_candidates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('source_page_from', sa.Integer(), nullable=True),
        sa.Column('source_page_to', sa.Integer(), nullable=True),
        sa.Column('source_excerpt', sa.Text(), nullable=True),
        sa.Column('temp_file_path', sa.String(1000), nullable=True),
        sa.Column('preview_path', sa.String(1000), nullable=True),
        sa.Column('thumbnail_path', sa.String(1000), nullable=True),
        sa.Column('file_type', sa.String(100), nullable=True),
        sa.Column('file_ext', sa.String(20), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('extraction_method', sa.String(20), nullable=False, server_default='rule'),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('ai_description', sa.Text(), nullable=True),
        sa.Column('ai_extracted_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('review_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['task_id'], ['ingestion_tasks.id'], ondelete='CASCADE'),
    )

    op.create_index(op.f('ix_material_candidates_id'), 'material_candidates', ['id'], unique=False)
    op.create_index(op.f('ix_material_candidates_task_id'), 'material_candidates', ['task_id'], unique=False)
    op.create_index(op.f('ix_material_candidates_category'), 'material_candidates', ['category'], unique=False)
    op.create_index(op.f('ix_material_candidates_review_status'), 'material_candidates', ['review_status'], unique=False)


def downgrade() -> None:
    # 删除 material_candidates 表
    op.drop_index(op.f('ix_material_candidates_review_status'), table_name='material_candidates')
    op.drop_index(op.f('ix_material_candidates_category'), table_name='material_candidates')
    op.drop_index(op.f('ix_material_candidates_task_id'), table_name='material_candidates')
    op.drop_index(op.f('ix_material_candidates_id'), table_name='material_candidates')
    op.drop_table('material_candidates')

    # 删除 ingestion_tasks 表
    op.drop_index(op.f('ix_ingestion_tasks_status'), table_name='ingestion_tasks')
    op.drop_index(op.f('ix_ingestion_tasks_created_by'), table_name='ingestion_tasks')
    op.drop_index(op.f('ix_ingestion_tasks_document_id'), table_name='ingestion_tasks')
    op.drop_index(op.f('ix_ingestion_tasks_id'), table_name='ingestion_tasks')
    op.drop_table('ingestion_tasks')
    op.execute('DROP TYPE IF EXISTS ingestiontaskstatus')

    # 删除 material_assets 溯源字段
    op.drop_constraint('fk_material_assets_source_document_id', 'material_assets', type_='foreignkey')
    op.drop_index(op.f('ix_material_assets_source_document_id'), table_name='material_assets')
    op.drop_column('material_assets', 'extraction_method')
    op.drop_column('material_assets', 'source_excerpt')
    op.drop_column('material_assets', 'source_page_to')
    op.drop_column('material_assets', 'source_page_from')
    op.drop_column('material_assets', 'source_document_id')
