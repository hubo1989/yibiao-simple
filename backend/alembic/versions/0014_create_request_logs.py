"""create request_logs table

Revision ID: 0014
Revises: 0013_update_knowledge_tables
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0014'
down_revision = '0013_update_knowledge_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 request_logs 表
    op.create_table(
        'request_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=False, comment='HTTP 方法'),
        sa.Column('path', sa.String(length=500), nullable=False, comment='请求路径'),
        sa.Column('query_params', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='查询参数'),
        sa.Column('request_headers', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='请求头'),
        sa.Column('request_body', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='请求体'),
        sa.Column('status_code', sa.Integer(), nullable=False, comment='HTTP 状态码'),
        sa.Column('response_body', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='响应体'),
        sa.Column('duration_ms', sa.Integer(), nullable=False, comment='请求耗时(毫秒)'),
        sa.Column('ip_address', sa.String(length=45), nullable=True, comment='客户端 IP'),
        sa.Column('user_agent', sa.String(length=500), nullable=True, comment='用户代理'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引
    op.create_index(op.f('ix_request_logs_user_id'), 'request_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_request_logs_path'), 'request_logs', ['path'], unique=False)
    op.create_index(op.f('ix_request_logs_status_code'), 'request_logs', ['status_code'], unique=False)
    op.create_index(op.f('ix_request_logs_created_at'), 'request_logs', ['created_at'], unique=False)


def downgrade() -> None:
    # 删除索引
    op.drop_index(op.f('ix_request_logs_created_at'), table_name='request_logs')
    op.drop_index(op.f('ix_request_logs_status_code'), table_name='request_logs')
    op.drop_index(op.f('ix_request_logs_path'), table_name='request_logs')
    op.drop_index(op.f('ix_request_logs_user_id'), table_name='request_logs')
    
    # 删除表
    op.drop_table('request_logs')
