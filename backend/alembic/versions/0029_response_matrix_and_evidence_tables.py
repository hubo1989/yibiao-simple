"""add response matrix and evidence tables

Revision ID: 0029_response_matrix_evidence
Revises: 0028_add_bid_agent
Create Date: 2026-05-24 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0029_response_matrix_evidence"
down_revision: Union[str, None] = "0028_add_bid_agent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


clause_type = postgresql.ENUM(
    "technical",
    "commercial",
    "qualification",
    "disqualification",
    "scoring",
    "format",
    "other",
    name="clausetype",
    create_type=False,
)
response_status = postgresql.ENUM(
    "not_started",
    "covered",
    "partial",
    "missing",
    "risk",
    "not_applicable",
    name="responsestatus",
    create_type=False,
)
evidence_source_type = postgresql.ENUM(
    "tender_document",
    "knowledge_doc",
    "material_asset",
    "manual_input",
    "generated_content",
    name="evidencesourcetype",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    clause_type.create(bind, checkfirst=True)
    response_status.create(bind, checkfirst=True)
    evidence_source_type.create(bind, checkfirst=True)

    op.create_table(
        "tender_clauses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clause_type", clause_type, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_location", sa.String(length=255), nullable=False),
        sa.Column("raw_requirement", sa.Text(), nullable=False),
        sa.Column("score_value", sa.Numeric(8, 2), nullable=True),
        sa.Column("is_fatal", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tender_clauses_project_id"), "tender_clauses", ["project_id"], unique=False)
    op.create_index(op.f("ix_tender_clauses_clause_type"), "tender_clauses", ["clause_type"], unique=False)
    op.create_index(op.f("ix_tender_clauses_is_fatal"), "tender_clauses", ["is_fatal"], unique=False)

    op.create_table(
        "response_matrix_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clause_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", sa.String(length=100), nullable=False),
        sa.Column("chapter_title", sa.String(length=255), nullable=False),
        sa.Column("response_status", response_status, nullable=False),
        sa.Column("response_summary", sa.Text(), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("risk_note", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=20), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["clause_id"], ["tender_clauses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_response_matrix_items_project_id"),
        "response_matrix_items",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_response_matrix_items_clause_id"),
        "response_matrix_items",
        ["clause_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_response_matrix_items_chapter_id"),
        "response_matrix_items",
        ["chapter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_response_matrix_items_response_status"),
        "response_matrix_items",
        ["response_status"],
        unique=False,
    )

    op.create_table(
        "evidence_refs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", evidence_source_type, nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("source_title", sa.String(length=500), nullable=False),
        sa.Column("source_location", sa.String(length=255), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("relation", sa.Text(), nullable=False, comment="与生成内容的关系说明"),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evidence_refs_project_id"), "evidence_refs", ["project_id"], unique=False)
    op.create_index(op.f("ix_evidence_refs_chapter_id"), "evidence_refs", ["chapter_id"], unique=False)
    op.create_index(op.f("ix_evidence_refs_source_type"), "evidence_refs", ["source_type"], unique=False)
    op.create_index(op.f("ix_evidence_refs_source_id"), "evidence_refs", ["source_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_evidence_refs_source_id"), table_name="evidence_refs")
    op.drop_index(op.f("ix_evidence_refs_source_type"), table_name="evidence_refs")
    op.drop_index(op.f("ix_evidence_refs_chapter_id"), table_name="evidence_refs")
    op.drop_index(op.f("ix_evidence_refs_project_id"), table_name="evidence_refs")
    op.drop_table("evidence_refs")

    op.drop_index(op.f("ix_response_matrix_items_response_status"), table_name="response_matrix_items")
    op.drop_index(op.f("ix_response_matrix_items_chapter_id"), table_name="response_matrix_items")
    op.drop_index(op.f("ix_response_matrix_items_clause_id"), table_name="response_matrix_items")
    op.drop_index(op.f("ix_response_matrix_items_project_id"), table_name="response_matrix_items")
    op.drop_table("response_matrix_items")

    op.drop_index(op.f("ix_tender_clauses_is_fatal"), table_name="tender_clauses")
    op.drop_index(op.f("ix_tender_clauses_clause_type"), table_name="tender_clauses")
    op.drop_index(op.f("ix_tender_clauses_project_id"), table_name="tender_clauses")
    op.drop_table("tender_clauses")

    bind = op.get_bind()
    evidence_source_type.drop(bind, checkfirst=True)
    response_status.drop(bind, checkfirst=True)
    clause_type.drop(bind, checkfirst=True)
