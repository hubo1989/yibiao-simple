"""create proofread_results table

Revision ID: 0009
Revises: 0008
Create Date: 2026-02-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建问题严重程度枚举
    op.execute("CREATE TYPE issue_severity AS ENUM ('critical', 'warning', 'info')")

    # 创建问题类别枚举
    op.execute("CREATE TYPE issue_category AS ENUM ('compliance', 'language', 'consistency', 'redundancy')")

    # 创建校对结果表
    op.create_table(
        'proofread_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chapter_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('issues', sa.Text(), nullable=False, comment='问题列表（JSON 格式）'),
        sa.Column('summary', sa.Text(), nullable=True, comment='问题摘要'),
        sa.Column('issue_count', sa.Integer(), nullable=False, server_default='0', comment='问题总数'),
        sa.Column('critical_count', sa.Integer(), nullable=False, server_default='0', comment='严重问题数量'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index(op.f('ix_proofread_results_chapter_id'), 'proofread_results', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_proofread_results_project_id'), 'proofread_results', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_proofread_results_project_id'), table_name='proofread_results')
    op.drop_index(op.f('ix_proofread_results_chapter_id'), table_name='proofread_results')
    op.drop_table('proofread_results')
    op.execute('DROP TYPE IF EXISTS issue_category')
    op.execute('DROP TYPE IF EXISTS issue_severity')
