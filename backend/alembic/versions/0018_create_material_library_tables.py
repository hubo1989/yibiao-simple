"""create material library tables

Revision ID: 0018_create_material_library_tables
Revises: 0017_add_outline_binding_fields_to_chapters
Create Date: 2026-03-23 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0018_create_material_library_tables"
down_revision = "0017_add_outline_binding_fields_to_chapters"
branch_labels = None
depends_on = None


scope_enum = sa.Enum("global", "enterprise", "user", name="scope")
material_category_enum = sa.Enum(
    "business_license",
    "legal_person_id",
    "qualification_cert",
    "award_cert",
    "iso_cert",
    "contract_sample",
    "project_case",
    "team_photo",
    "equipment_photo",
    "financial_report",
    "bank_credit",
    "social_security",
    "other",
    name="materialcategory",
)
material_review_status_enum = sa.Enum("pending", "confirmed", "rejected", name="materialreviewstatus")
material_requirement_status_enum = sa.Enum(
    "pending", "matched", "missing", "ignored", "confirmed", name="materialrequirementstatus"
)
material_extracted_by_enum = sa.Enum("ai", "user", name="materialextractedby")
binding_anchor_type_enum = sa.Enum(
    "section_end", "paragraph_after", "paragraph_before", "appendix_block", name="bindinganchortype"
)
binding_display_mode_enum = sa.Enum("image", "attachment_note", name="bindingdisplaymode")


def upgrade() -> None:
    bind = op.get_bind()

    # 检查并创建 enum 类型（避免重复创建）
    conn = bind.connect()
    existing_types = conn.execute(sa.text("SELECT typname FROM pg_type WHERE typcategory = 'E'")).fetchall()
    existing_type_names = {t[0] for t in existing_types}
    conn.close()

    enums_to_create = [
        (scope_enum, "scope"),
        (material_category_enum, "materialcategory"),
        (material_review_status_enum, "materialreviewstatus"),
        (material_requirement_status_enum, "materialrequirementstatus"),
        (material_extracted_by_enum, "materialextractedby"),
        (binding_anchor_type_enum, "bindinganchortype"),
        (binding_display_mode_enum, "bindingdisplaymode"),
    ]

    for enum_obj, enum_name in enums_to_create:
        if enum_name not in existing_type_names:
            enum_obj.create(bind)

    op.add_column("chapters", sa.Column("material_marker_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "material_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("scope", scope_enum, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category", material_category_enum, nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("preview_path", sa.String(length=1000), nullable=True),
        sa.Column("thumbnail_path", sa.String(length=1000), nullable=True),
        sa.Column("file_type", sa.String(length=100), nullable=False),
        sa.Column("file_ext", sa.String(length=20), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ai_description", sa.Text(), nullable=True),
        sa.Column("ai_extracted_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("is_expired", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_status", material_review_status_enum, nullable=False, server_default="pending"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_material_assets_owner_id", "material_assets", ["owner_id"])
    op.create_index("ix_material_assets_scope", "material_assets", ["scope"])
    op.create_index("ix_material_assets_category", "material_assets", ["category"])
    op.create_index("ix_material_assets_is_expired", "material_assets", ["is_expired"])

    op.create_table(
        "material_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chapter_hint", sa.String(length=255), nullable=True),
        sa.Column("section_hint", sa.String(length=255), nullable=True),
        sa.Column("requirement_name", sa.String(length=500), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", material_requirement_status_enum, nullable=False, server_default="pending"),
        sa.Column("extracted_by", material_extracted_by_enum, nullable=False, server_default="ai"),
        sa.Column("sort_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_material_requirements_project_id", "material_requirements", ["project_id"])
    op.create_index("ix_material_requirements_category", "material_requirements", ["category"])
    op.create_index("ix_material_requirements_status", "material_requirements", ["status"])

    op.create_table(
        "chapter_material_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_requirement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("material_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("anchor_type", binding_anchor_type_enum, nullable=False, server_default="section_end"),
        sa.Column("anchor_value", sa.String(length=255), nullable=True),
        sa.Column("display_mode", binding_display_mode_enum, nullable=False, server_default="image"),
        sa.Column("caption", sa.String(length=500), nullable=True),
        sa.Column("sort_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_requirement_id"], ["material_requirements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["material_asset_id"], ["material_assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_chapter_material_bindings_project_id", "chapter_material_bindings", ["project_id"])
    op.create_index("ix_chapter_material_bindings_chapter_id", "chapter_material_bindings", ["chapter_id"])
    op.create_index("ix_chapter_material_bindings_material_asset_id", "chapter_material_bindings", ["material_asset_id"])


def downgrade() -> None:
    op.drop_index("ix_chapter_material_bindings_material_asset_id", table_name="chapter_material_bindings")
    op.drop_index("ix_chapter_material_bindings_chapter_id", table_name="chapter_material_bindings")
    op.drop_index("ix_chapter_material_bindings_project_id", table_name="chapter_material_bindings")
    op.drop_table("chapter_material_bindings")

    op.drop_index("ix_material_requirements_status", table_name="material_requirements")
    op.drop_index("ix_material_requirements_category", table_name="material_requirements")
    op.drop_index("ix_material_requirements_project_id", table_name="material_requirements")
    op.drop_table("material_requirements")

    op.drop_index("ix_material_assets_is_expired", table_name="material_assets")
    op.drop_index("ix_material_assets_category", table_name="material_assets")
    op.drop_index("ix_material_assets_scope", table_name="material_assets")
    op.drop_index("ix_material_assets_owner_id", table_name="material_assets")
    op.drop_table("material_assets")

    op.drop_column("chapters", "material_marker_enabled")

    bind = op.get_bind()
    binding_display_mode_enum.drop(bind, checkfirst=True)
    binding_anchor_type_enum.drop(bind, checkfirst=True)
    material_extracted_by_enum.drop(bind, checkfirst=True)
    material_requirement_status_enum.drop(bind, checkfirst=True)
    material_review_status_enum.drop(bind, checkfirst=True)
    material_category_enum.drop(bind, checkfirst=True)
