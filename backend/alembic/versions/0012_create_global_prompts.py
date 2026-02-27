"""create global_prompts table and add custom_prompts to projects

Revision ID: 0011_create_global_prompts
Revises: 0010_create_consistency_results
Create Date: 2026-02-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = "0011_create_global_prompts"
down_revision: Union[str, None] = "0010_create_consistency_results"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 检查并创建枚举类型（如果不存在）
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT 1 FROM pg_type WHERE typname = 'prompt_category'"
    ))
    if not result.fetchone():
        conn.execute(text(
            "CREATE TYPE prompt_category AS ENUM ('analysis', 'generation', 'check')"
        ))
        conn.commit()

    # 创建 global_prompts 表
    conn.execute(text("""
        CREATE TABLE global_prompts (
            id UUID PRIMARY KEY,
            scene_key VARCHAR(64) NOT NULL UNIQUE,
            scene_name VARCHAR(128) NOT NULL,
            category prompt_category NOT NULL,
            prompt TEXT NOT NULL,
            available_vars JSONB,
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """))
    conn.commit()

    # 创建索引
    conn.execute(text("""
        CREATE INDEX ix_global_prompts_scene_key ON global_prompts (scene_key)
    """))
    conn.execute(text("""
        CREATE INDEX ix_global_prompts_category ON global_prompts (category)
    """))
    conn.commit()

    # 创建 global_prompt_versions 表
    conn.execute(text("""
        CREATE TABLE global_prompt_versions (
            id UUID PRIMARY KEY,
            global_prompt_id UUID NOT NULL REFERENCES global_prompts(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            prompt TEXT NOT NULL,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """))
    conn.commit()

    # 创建索引
    conn.execute(text("""
        CREATE INDEX ix_global_prompt_versions_global_prompt_id ON global_prompt_versions (global_prompt_id)
    """))
    conn.execute(text("""
        CREATE INDEX ix_global_prompt_versions_created_by ON global_prompt_versions (created_by)
    """))
    conn.commit()

    # 为 projects 表添加 custom_prompts 字段（如果不存在）
    result = conn.execute(text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'projects' AND column_name = 'custom_prompts'
    """))
    if not result.fetchone():
        conn.execute(text("""
            ALTER TABLE projects ADD COLUMN custom_prompts JSONB
        """))
        conn.commit()


def downgrade() -> None:
    conn = op.get_bind()

    # 删除 projects 表的 custom_prompts 字段
    conn.execute(text("ALTER TABLE projects DROP COLUMN IF EXISTS custom_prompts"))

    # 删除 global_prompt_versions 表
    conn.execute(text("DROP INDEX IF EXISTS ix_global_prompt_versions_created_by"))
    conn.execute(text("DROP INDEX IF EXISTS ix_global_prompt_versions_global_prompt_id"))
    conn.execute(text("DROP TABLE IF EXISTS global_prompt_versions"))

    # 删除 global_prompts 表
    conn.execute(text("DROP INDEX IF EXISTS ix_global_prompts_category"))
    conn.execute(text("DROP INDEX IF EXISTS ix_global_prompts_scene_key"))
    conn.execute(text("DROP TABLE IF EXISTS global_prompts"))

    # 删除枚举类型
    conn.execute(text("DROP TYPE IF EXISTS prompt_category"))
    conn.commit()
