"""add multi model config to api_key_configs

Revision ID: 0015_multi_model_api_keys
Revises: 0014
Create Date: 2026-03-06
"""
from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0015_multi_model_api_keys"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_MODEL_NAME = "gpt-3.5-turbo"


def upgrade() -> None:
    op.add_column(
        "api_key_configs",
        sa.Column(
            "model_configs_json",
            sa.Text(),
            nullable=True,
            comment="模型配置 JSON，支持分别设置生成模型与索引模型",
        ),
    )

    connection = op.get_bind()
    metadata = sa.MetaData()
    api_key_configs = sa.Table(
        "api_key_configs",
        metadata,
        sa.Column("id", postgresql.UUID(as_uuid=True)),
        sa.Column("model_name", sa.String(length=128)),
        sa.Column("model_configs_json", sa.Text()),
    )

    rows = connection.execute(
        sa.select(
            api_key_configs.c.id,
            api_key_configs.c.model_name,
            api_key_configs.c.model_configs_json,
        )
    ).mappings()

    for row in rows:
        if row["model_configs_json"]:
            continue

        model_name = (row["model_name"] or "").strip() or DEFAULT_MODEL_NAME
        model_configs_json = json.dumps(
            [
                {
                    "model_id": model_name,
                    "use_for_generation": True,
                    "use_for_indexing": True,
                }
            ],
            ensure_ascii=False,
        )
        connection.execute(
            api_key_configs.update()
            .where(api_key_configs.c.id == row["id"])
            .values(model_configs_json=model_configs_json)
        )


def downgrade() -> None:
    op.drop_column("api_key_configs", "model_configs_json")
