"""create consistency_results table

Revision ID: 0010
Revises: 0009
Create Date: 2026-02-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建矛盾严重程度枚举
    op.execute("CREATE TYPE consistency_severity AS ENUM ('critical', 'warning', 'info')")

    # 创建矛盾类别枚举
    op.execute("CREATE TYPE consistency_category AS ENUM ('data', 'terminology', 'timeline', 'commitment', 'scope')")

    # 创建一致性检查结果表
    op.create_table(
        'consistency_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('contradictions', sa.Text(), nullable=False, comment='矛盾列表（JSON 格式）'),
        sa.Column('summary', sa.Text(), nullable=True, comment='整体一致性评估摘要'),
        sa.Column('overall_consistency', sa.String(20), nullable=False, comment='整体一致性评估: consistent/minor_issues/major_issues'),
        sa.Column('contradiction_count', sa.Integer(), nullable=False, server_default='0', comment='矛盾总数'),
        sa.Column('critical_count', sa.Integer(), nullable=False, server_default='0', comment='严重矛盾数量'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index(op.f('ix_consistency_results_project_id'), 'consistency_results', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_consistency_results_project_id'), table_name='consistency_results')
    op.drop_table('consistency_results')
    op.execute('DROP TYPE IF EXISTS consistency_category')
    op.execute('DROP TYPE IF EXISTS consistency_severity')
