"""add_export_templates

Revision ID: 0023_add_export_templates
Revises: fb4cd25a66f4
Create Date: 2026-04-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0023_add_export_templates'
down_revision: Union[str, None] = 'fb4cd25a66f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ============ 内置模板配置 ============
BUILTIN_TEMPLATES = [
    {
        "name": "GB/T 9704 标准",
        "description": "国家标准公文格式（GB/T 9704），黑体/仿宋排版，固定行间距 28 磅",
        "is_builtin": True,
        "format_config": {
            "font": {
                "body_font": "仿宋",
                "body_size": 12,
                "h1_font": "黑体",
                "h1_size": 16,
                "h2_font": "黑体",
                "h2_size": 14,
                "h3_font": "黑体",
                "h3_size": 12,
                "table_font": "仿宋",
                "table_size": 10.5,
            },
            "spacing": {
                "line_spacing_pt": 28,
                "first_indent_chars": 2,
                "h1_before": 24,
                "h1_after": 12,
                "h2_before": 12,
                "h2_after": 6,
                "h3_before": 6,
                "h3_after": 3,
            },
            "margin": {"top": 37, "bottom": 35, "left": 28, "right": 26},
            "page": {
                "page_number_format": "第X页 共Y页",
                "header_text": "{project_name}",
                "header_position": "center",
            },
            "cover": {
                "show_cover": True,
                "title_font": "黑体",
                "title_size": 22,
                "subtitle": "投标技术文件",
                "show_bidder_info": True,
                "cover_fields": ["投标人", "编制日期"],
            },
            "toc": {
                "show_toc": True,
                "toc_title": "目  录",
                "toc_levels": 3,
            },
        },
    },
    {
        "name": "通用简洁",
        "description": "通用商务文档格式，宋体排版，页边距 2.54cm，适合一般投标文件",
        "is_builtin": True,
        "format_config": {
            "font": {
                "body_font": "宋体",
                "body_size": 12,
                "h1_font": "宋体",
                "h1_size": 16,
                "h2_font": "宋体",
                "h2_size": 14,
                "h3_font": "宋体",
                "h3_size": 12,
                "table_font": "宋体",
                "table_size": 10.5,
            },
            "spacing": {
                "line_spacing_pt": 22,
                "first_indent_chars": 2,
                "h1_before": 18,
                "h1_after": 12,
                "h2_before": 12,
                "h2_after": 6,
                "h3_before": 6,
                "h3_after": 3,
            },
            "margin": {"top": 25.4, "bottom": 25.4, "left": 31.7, "right": 31.7},
            "page": {
                "page_number_format": "X",
                "header_text": "{project_name}",
                "header_position": "right",
            },
            "cover": {
                "show_cover": True,
                "title_font": "宋体",
                "title_size": 22,
                "subtitle": "投标技术文件",
                "show_bidder_info": True,
                "cover_fields": ["投标人", "编制日期"],
            },
            "toc": {
                "show_toc": True,
                "toc_title": "目录",
                "toc_levels": 3,
            },
        },
    },
]


def upgrade() -> None:
    # 1. 创建 export_templates 表
    op.create_table(
        'export_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('format_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('source_file_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_export_templates_name', 'export_templates', ['name'])
    op.create_index('ix_export_templates_created_by', 'export_templates', ['created_by'])

    # 2. 向 projects 表添加 default_template_id 列
    op.add_column(
        'projects',
        sa.Column('default_template_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_projects_default_template_id',
        'projects',
        'export_templates',
        ['default_template_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # 3. 插入内置模板
    import uuid
    import json
    from datetime import datetime, timezone

    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    for tmpl in BUILTIN_TEMPLATES:
        conn.execute(
            sa.text(
                """
                INSERT INTO export_templates (id, name, description, is_builtin, created_by, format_config, created_at, updated_at)
                VALUES (:id, :name, :description, :is_builtin, NULL, :format_config, :created_at, :updated_at)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "name": tmpl["name"],
                "description": tmpl["description"],
                "is_builtin": tmpl["is_builtin"],
                "format_config": json.dumps(tmpl["format_config"], ensure_ascii=False),
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.drop_constraint('fk_projects_default_template_id', 'projects', type_='foreignkey')
    op.drop_column('projects', 'default_template_id')
    op.drop_index('ix_export_templates_created_by', table_name='export_templates')
    op.drop_index('ix_export_templates_name', table_name='export_templates')
    op.drop_table('export_templates')
