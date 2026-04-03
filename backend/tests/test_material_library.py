"""素材库核心能力测试"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from docx import Document

from app.models.material import (
    MaterialAsset,
    MaterialCategory,
    MaterialRequirement,
    ChapterMaterialBinding,
    MaterialRequirementStatus,
    BindingDisplayMode,
    BindingAnchorType,
)
from app.models.schemas import AnalysisType
from app.schemas.material import MaterialRequirementMatchCandidate
from app.services.material_service import (
    build_material_requirement_candidates,
    build_material_storage_paths,
    render_content_with_material_bindings,
)


def make_asset(
    *,
    category: MaterialCategory = MaterialCategory.BUSINESS_LICENSE,
    name: str = "营业执照副本",
    tags: list[str] | None = None,
    extracted_fields: dict | None = None,
    valid_until: date | None = None,
    last_used_at: datetime | None = None,
) -> MaterialAsset:
    now = datetime.now(timezone.utc)
    return MaterialAsset(
        id=uuid.uuid4(),
        scope="user",
        owner_id=uuid.uuid4(),
        uploaded_by=None,
        category=category,
        name=name,
        description=None,
        file_path="/tmp/material.jpg",
        preview_path="/tmp/material-preview.jpg",
        thumbnail_path="/tmp/material-thumb.jpg",
        file_type="image/jpeg",
        file_ext="jpg",
        file_size=1024,
        page_count=1,
        tags=tags or [],
        keywords=[],
        ai_description=None,
        ai_extracted_fields=extracted_fields or {},
        valid_from=None,
        valid_until=valid_until,
        is_expired=False,
        review_status="confirmed",
        usage_count=0,
        last_used_at=last_used_at or now,
    )


def test_analysis_type_includes_material_requirements() -> None:
    assert AnalysisType.MATERIAL_REQUIREMENTS == "material_requirements"


def test_material_models_expose_expected_columns() -> None:
    material_columns = {column.name for column in MaterialAsset.__table__.columns}
    assert {"preview_path", "thumbnail_path", "ai_extracted_fields", "valid_until"} <= material_columns

    requirement_columns = {column.name for column in MaterialRequirement.__table__.columns}
    assert {"project_id", "chapter_hint", "section_hint", "status"} <= requirement_columns

    binding_columns = {column.name for column in ChapterMaterialBinding.__table__.columns}
    assert {"chapter_id", "material_asset_id", "anchor_type", "display_mode"} <= binding_columns


def test_build_material_storage_paths_uses_scope_owner_and_material_id() -> None:
    material_id = uuid.uuid4()
    paths = build_material_storage_paths(
        scope="enterprise",
        owner_id=uuid.uuid4(),
        material_id=material_id,
        extension="pdf",
    )

    assert str(material_id) in paths["original"]
    assert "/enterprise/" in paths["original"]
    assert paths["preview"].endswith("/preview.jpg")
    assert paths["thumbnail"].endswith("/thumb.jpg")


def test_build_material_requirement_candidates_prefers_category_and_subject_match() -> None:
    matched_asset = make_asset(
        name="XX有限公司营业执照副本",
        tags=["营业执照", "资质证明"],
        extracted_fields={"company_name": "XX有限公司"},
        last_used_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    weaker_asset = make_asset(
        category=MaterialCategory.OTHER,
        name="普通附件",
        tags=["附件"],
        extracted_fields={"company_name": "其他公司"},
        last_used_at=datetime(2025, 3, 20, tzinfo=timezone.utc),
    )

    candidates = build_material_requirement_candidates(
        requirement_name="营业执照副本",
        requirement_text="请提供XX有限公司有效期内营业执照副本复印件并加盖公章",
        requirement_category=MaterialCategory.BUSINESS_LICENSE.value,
        requirement_tags=["营业执照", "资质证明"],
        assets=[matched_asset, weaker_asset],
    )

    assert len(candidates) == 2
    assert isinstance(candidates[0], MaterialRequirementMatchCandidate)
    assert candidates[0].asset_id == str(matched_asset.id)
    assert candidates[0].score > candidates[1].score
    assert candidates[0].matched_reasons


def test_build_material_requirement_candidates_filters_expired_assets() -> None:
    expired_asset = make_asset(
        valid_until=date(2024, 1, 1),
        last_used_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    active_asset = make_asset(valid_until=date(2028, 1, 1))

    candidates = build_material_requirement_candidates(
        requirement_name="营业执照副本",
        requirement_text="提供有效期内营业执照副本",
        requirement_category=MaterialCategory.BUSINESS_LICENSE.value,
        requirement_tags=["营业执照"],
        assets=[expired_asset, active_asset],
        today=date(2026, 3, 23),
    )

    assert [candidate.asset_id for candidate in candidates] == [str(active_asset.id)]


def test_render_content_with_material_bindings_replaces_marker_and_handles_missing_binding() -> None:
    binding_id = str(uuid.uuid4())
    document = Document()

    render_content_with_material_bindings(
        document=document,
        content=f"第一段\n[INSERT_MATERIAL:{binding_id}]\n结尾\n[INSERT_MATERIAL:missing-binding]",
        binding_map={
            binding_id: {
                "caption": "营业执照副本",
                "material_name": "营业执照副本",
                "display_mode": BindingDisplayMode.IMAGE.value,
            }
        },
    )

    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    assert any("第一段" in text for text in paragraphs)
    assert any("营业执照副本" in text for text in paragraphs)
    assert any("素材缺失" in text for text in paragraphs)


def test_material_status_enums_are_stable() -> None:
    assert MaterialRequirementStatus.CONFIRMED == "confirmed"
    assert BindingDisplayMode.IMAGE == "image"
    assert BindingAnchorType.APPENDIX_BLOCK == "appendix_block"
