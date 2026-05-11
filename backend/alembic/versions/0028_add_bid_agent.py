"""add bid agent runs and steps

Revision ID: 0028_add_bid_agent
Revises: 0027_add_consistency_checks
Create Date: 2026-05-12 01:13:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0028_add_bid_agent'
down_revision: Union[str, None] = '0027_add_consistency_checks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


run_status = sa.Enum('pending', 'running', 'completed', 'failed', 'cancelled', name='bidagentrunstatus')
step_status = sa.Enum('pending', 'running', 'completed', 'failed', 'skipped', name='bidagentstepstatus')


def upgrade() -> None:
    bind = op.get_bind()
    run_status.create(bind, checkfirst=True)
    step_status.create(bind, checkfirst=True)

    op.create_table(
        'bid_agent_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('goal', sa.String(length=100), nullable=False),
        sa.Column('status', run_status, nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('result_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bid_agent_runs_project_id'), 'bid_agent_runs', ['project_id'], unique=False)
    op.create_index(op.f('ix_bid_agent_runs_created_by'), 'bid_agent_runs', ['created_by'], unique=False)
    op.create_index(op.f('ix_bid_agent_runs_status'), 'bid_agent_runs', ['status'], unique=False)

    op.create_table(
        'bid_agent_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_key', sa.String(length=100), nullable=False),
        sa.Column('step_name', sa.String(length=255), nullable=False),
        sa.Column('status', step_status, nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('result_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['bid_agent_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bid_agent_steps_run_id'), 'bid_agent_steps', ['run_id'], unique=False)
    op.create_index(op.f('ix_bid_agent_steps_step_key'), 'bid_agent_steps', ['step_key'], unique=False)
    op.create_index(op.f('ix_bid_agent_steps_status'), 'bid_agent_steps', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_bid_agent_steps_status'), table_name='bid_agent_steps')
    op.drop_index(op.f('ix_bid_agent_steps_step_key'), table_name='bid_agent_steps')
    op.drop_index(op.f('ix_bid_agent_steps_run_id'), table_name='bid_agent_steps')
    op.drop_table('bid_agent_steps')
    op.drop_index(op.f('ix_bid_agent_runs_status'), table_name='bid_agent_runs')
    op.drop_index(op.f('ix_bid_agent_runs_created_by'), table_name='bid_agent_runs')
    op.drop_index(op.f('ix_bid_agent_runs_project_id'), table_name='bid_agent_runs')
    op.drop_table('bid_agent_runs')
    bind = op.get_bind()
    step_status.drop(bind, checkfirst=True)
    run_status.drop(bind, checkfirst=True)
