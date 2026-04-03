"""素材库与材料需求 API"""
from __future__ import annotations

import os
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from PIL import Image
from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_active_user, require_editor
from ..config import settings
from ..db.database import get_db
from ..models.chapter import Chapter
from ..models.knowledge import Scope
from ..models.material import (
    BindingDisplayMode,
    ChapterMaterialBinding,
    MaterialAsset,
    MaterialCategory,
    MaterialExtractedBy,
    MaterialRequirement,
    MaterialRequirementStatus,
    MaterialReviewStatus,
)
from ..models.project import Project, project_members
from ..models.user import User, UserRole
from ..schemas.material import (
    ChapterMaterialBindingCreate,
    ChapterMaterialBindingResponse,
    ChapterMaterialBindingUpdate,
    MaterialAssetResponse,
    MaterialAssetUpdate,
    MaterialMatchConfirmRequest,
    MaterialRequirementResponse,
    MaterialRequirementUpdate,
)
from ..services.material_service import build_material_requirement_candidates, build_material_storage_paths

router = APIRouter(tags=["素材库"])

ALLOWED_MATERIAL_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "application/pdf": "pdf",
}
MAX_MATERIAL_FILE_SIZE = 20 * 1024 * 1024


def _material_owner(scope: Scope, current_user: User) -> uuid.UUID | None:
    if scope == Scope.GLOBAL:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以创建全局素材")
        return None
    return current_user.id


async def _verify_project_member(project_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project)
        .join(project_members, Project.id == project_members.c.project_id)
        .where(and_(Project.id == project_id, project_members.c.user_id == user_id))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在或您没有访问权限")
    return project


def _check_magic_bytes(content_type: str, header: bytes) -> bool:
    if content_type == "application/pdf":
        return header[:5] == b"%PDF-"
    if content_type == "image/png":
        return header[:8] == b"\x89PNG\r\n\x1a\n"
    if content_type == "image/jpeg":
        return header[:2] == b"\xff\xd8"
    return False


async def _persist_material_file(file: UploadFile, *, scope: Scope, owner_id: uuid.UUID | None, material_id: uuid.UUID) -> dict[str, str | int | None]:
    header = await file.read(16)
    await file.seek(0)

    if file.content_type not in ALLOWED_MATERIAL_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 PNG、JPG、PDF 素材")
    if not _check_magic_bytes(file.content_type, header):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容与类型不匹配")

    content = await file.read()
    await file.seek(0)
    if len(content) > MAX_MATERIAL_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="素材文件大小不能超过 20MB")

    owner_part = owner_id or uuid.UUID(int=0)
    paths = build_material_storage_paths(
        scope=scope.value,
        owner_id=owner_part,
        material_id=material_id,
        extension=ALLOWED_MATERIAL_TYPES[file.content_type],
    )
    os.makedirs(paths["base_dir"], exist_ok=True)

    with open(paths["original"], "wb") as output:
        output.write(content)

    preview_path = None
    thumb_path = None
    page_count = 1

    if file.content_type.startswith("image/"):
        with Image.open(paths["original"]) as image:
            preview = image.copy()
            preview.thumbnail((1600, 1600))
            preview.convert("RGB").save(paths["preview"], "JPEG", quality=90)

            thumb = image.copy()
            thumb.thumbnail((360, 360))
            thumb.convert("RGB").save(paths["thumbnail"], "JPEG", quality=85)
        preview_path = paths["preview"]
        thumb_path = paths["thumbnail"]
    else:
        try:
            import fitz
        except ImportError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="缺少 PDF 预览依赖") from exc

        pdf = fitz.open(paths["original"])
        try:
            page_count = pdf.page_count
            page = pdf[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            pix.save(paths["preview"])
            with Image.open(paths["preview"]) as preview_image:
                thumb = preview_image.copy()
                thumb.thumbnail((360, 360))
                thumb.convert("RGB").save(paths["thumbnail"], "JPEG", quality=85)
            preview_path = paths["preview"]
            thumb_path = paths["thumbnail"]
        finally:
            pdf.close()

    return {
        "file_path": paths["original"],
        "preview_path": preview_path,
        "thumbnail_path": thumb_path,
        "file_size": len(content),
        "page_count": page_count,
        "file_ext": ALLOWED_MATERIAL_TYPES[file.content_type],
    }


def _serialize_material(material: MaterialAsset) -> MaterialAssetResponse:
    return MaterialAssetResponse.model_validate(material, from_attributes=True)


def _serialize_requirement(requirement: MaterialRequirement) -> MaterialRequirementResponse:
    response = MaterialRequirementResponse.model_validate(requirement)
    response.id = str(requirement.id)
    response.project_id = str(requirement.project_id)
    response.source_document_id = str(requirement.source_document_id) if requirement.source_document_id else None
    return response


def _serialize_binding(binding: ChapterMaterialBinding) -> ChapterMaterialBindingResponse:
    response = ChapterMaterialBindingResponse.model_validate(binding)
    response.id = str(binding.id)
    response.project_id = str(binding.project_id)
    response.chapter_id = str(binding.chapter_id)
    response.material_requirement_id = str(binding.material_requirement_id) if binding.material_requirement_id else None
    response.material_asset_id = str(binding.material_asset_id)
    response.created_by = str(binding.created_by) if binding.created_by else None
    if binding.material_asset:
        response.material_asset = _serialize_material(binding.material_asset)
    return response


def _guess_category(text: str) -> tuple[MaterialCategory, list[str]]:
    mapping = [
        ("营业执照", MaterialCategory.BUSINESS_LICENSE, ["营业执照", "资质证明"]),
        ("身份证", MaterialCategory.LEGAL_PERSON_ID, ["身份证", "法人证件"]),
        ("资质", MaterialCategory.QUALIFICATION_CERT, ["资质证书"]),
        ("奖项", MaterialCategory.AWARD_CERT, ["奖项证书"]),
        ("iso", MaterialCategory.ISO_CERT, ["ISO"]),
        ("合同", MaterialCategory.CONTRACT_SAMPLE, ["合同样本"]),
        ("案例", MaterialCategory.PROJECT_CASE, ["项目案例"]),
    ]
    lowered = text.lower()
    for keyword, category, tags in mapping:
        if keyword.lower() in lowered:
            return category, tags
    return MaterialCategory.OTHER, []


def _extract_project_material_requirements(project: Project) -> list[dict]:
    source_text = "\n".join(filter(None, [project.tech_requirements, project.file_content]))
    requirement_lines = []
    for raw_line in source_text.splitlines():
        line = raw_line.strip(" -\t")
        if not line:
            continue
        if not any(keyword in line for keyword in ["提供", "附", "提交", "营业执照", "身份证", "资质", "合同", "案例"]):
            continue
        category, tags = _guess_category(line)
        requirement_lines.append(
            {
                "requirement_name": line[:40],
                "requirement_text": line,
                "category": category.value,
                "chapter_hint": "资格审查" if "资格" in line or "营业执照" in line else None,
                "section_hint": "投标人资格证明材料" if "提供" in line or "附" in line else None,
                "tags": tags,
                "is_mandatory": True,
            }
        )
    if not requirement_lines:
        requirement_lines.append(
            {
                "requirement_name": "请人工补充材料需求",
                "requirement_text": "未从当前项目文档中识别到明确材料要求，请人工新增。",
                "category": MaterialCategory.OTHER.value,
                "chapter_hint": None,
                "section_hint": None,
                "tags": ["人工确认"],
                "is_mandatory": False,
            }
        )
    return requirement_lines


@router.post("/api/materials/upload", response_model=MaterialAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_material(
    file: UploadFile = File(...),
    name: str = Form(...),
    category: MaterialCategory = Form(MaterialCategory.OTHER),
    scope: Scope = Form(Scope.USER),
    description: str | None = Form(None),
    tags: str | None = Form(None),
    valid_until: date | None = Form(None),
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    owner_id = _material_owner(scope, current_user)
    material_id = uuid.uuid4()
    file_meta = await _persist_material_file(file, scope=scope, owner_id=owner_id, material_id=material_id)
    material = MaterialAsset(
        id=material_id,
        scope=scope.value,
        owner_id=owner_id,
        uploaded_by=current_user.id,
        category=category,
        name=name,
        description=description,
        file_path=str(file_meta["file_path"]),
        preview_path=file_meta["preview_path"],
        thumbnail_path=file_meta["thumbnail_path"],
        file_type=file.content_type or "application/octet-stream",
        file_ext=str(file_meta["file_ext"]),
        file_size=int(file_meta["file_size"]),
        page_count=file_meta["page_count"],
        tags=[item.strip() for item in (tags or "").split(",") if item.strip()],
        keywords=[],
        ai_description=None,
        ai_extracted_fields={},
        valid_until=valid_until,
        is_expired=bool(valid_until and valid_until < date.today()),
        review_status=MaterialReviewStatus.PENDING,
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)
    return _serialize_material(material)


@router.post("/api/materials/batch-upload", response_model=list[MaterialAssetResponse], status_code=status.HTTP_201_CREATED)
async def batch_upload_materials(
    files: list[UploadFile] = File(...),
    scope: Scope = Form(Scope.USER),
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    materials: list[MaterialAssetResponse] = []
    for upload in files:
        material_id = uuid.uuid4()
        owner_id = _material_owner(scope, current_user)
        file_meta = await _persist_material_file(upload, scope=scope, owner_id=owner_id, material_id=material_id)
        category, tags = _guess_category(upload.filename or "")
        material = MaterialAsset(
            id=material_id,
            scope=scope.value,
            owner_id=owner_id,
            uploaded_by=current_user.id,
            category=category,
            name=upload.filename or f"素材-{material_id}",
            file_path=str(file_meta["file_path"]),
            preview_path=file_meta["preview_path"],
            thumbnail_path=file_meta["thumbnail_path"],
            file_type=upload.content_type or "application/octet-stream",
            file_ext=str(file_meta["file_ext"]),
            file_size=int(file_meta["file_size"]),
            page_count=file_meta["page_count"],
            tags=tags,
            keywords=[],
            ai_extracted_fields={},
            is_expired=False,
            review_status=MaterialReviewStatus.PENDING,
        )
        db.add(material)
        await db.flush()
        await db.refresh(material)
        materials.append(_serialize_material(material))
    return materials


@router.get("/api/materials", response_model=list[MaterialAssetResponse])
async def list_materials(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: MaterialCategory | None = Query(None),
    expired: bool | None = Query(None),
    keyword: str | None = Query(None),
):
    query = select(MaterialAsset).where(
        (MaterialAsset.scope == Scope.GLOBAL.value)
        | (MaterialAsset.owner_id == current_user.id)
        | (MaterialAsset.uploaded_by == current_user.id)
    )
    if category:
        query = query.where(MaterialAsset.category == category)
    if expired is not None:
        query = query.where(MaterialAsset.is_expired == expired)
    result = await db.execute(query.order_by(MaterialAsset.updated_at.desc()))
    materials = result.scalars().all()
    if keyword:
        keyword_lower = keyword.lower()
        materials = [item for item in materials if keyword_lower in item.name.lower() or keyword_lower in (item.description or "").lower()]
    return [_serialize_material(item) for item in materials]


@router.get("/api/materials/{material_id}", response_model=MaterialAssetResponse)
async def get_material(
    material_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(MaterialAsset).where(MaterialAsset.id == material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
    if material.scope != Scope.GLOBAL.value and material.owner_id not in (None, current_user.id) and material.uploaded_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该素材")
    return _serialize_material(material)


@router.put("/api/materials/{material_id}", response_model=MaterialAssetResponse)
async def update_material(
    material_id: uuid.UUID,
    payload: MaterialAssetUpdate,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(MaterialAsset).where(MaterialAsset.id == material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
    if material.owner_id not in (None, current_user.id) and material.uploaded_by != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权编辑该素材")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(material, field, value)
    material.is_expired = bool(material.valid_until and material.valid_until < date.today())
    await db.flush()
    await db.refresh(material)
    return _serialize_material(material)


@router.delete("/api/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material(
    material_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(MaterialAsset).where(MaterialAsset.id == material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
    if material.owner_id not in (None, current_user.id) and material.uploaded_by != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该素材")
    binding_exists = await db.execute(
        select(exists().where(ChapterMaterialBinding.material_asset_id == material_id))
    )
    if binding_exists.scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="素材已被项目绑定，暂不能删除")
    for path in [material.file_path, material.preview_path, material.thumbnail_path]:
        if path and os.path.exists(path):
            os.remove(path)
    await db.delete(material)


@router.post("/api/projects/{project_id}/material-requirements/analyze", response_model=list[MaterialRequirementResponse])
async def analyze_project_material_requirements(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    project = await _verify_project_member(project_id, current_user.id, db)
    extracted = _extract_project_material_requirements(project)

    result = await db.execute(
        select(MaterialRequirement).where(
            and_(MaterialRequirement.project_id == project_id, MaterialRequirement.extracted_by == MaterialExtractedBy.AI)
        )
    )
    for requirement in result.scalars().all():
        await db.delete(requirement)
    await db.flush()

    created: list[MaterialRequirement] = []
    for index, item in enumerate(extracted):
        requirement = MaterialRequirement(
            project_id=project_id,
            chapter_hint=item["chapter_hint"],
            section_hint=item["section_hint"],
            requirement_name=item["requirement_name"],
            requirement_text=item["requirement_text"],
            category=item["category"],
            tags=item["tags"],
            is_mandatory=item["is_mandatory"],
            status=MaterialRequirementStatus.PENDING,
            extracted_by=MaterialExtractedBy.AI,
            sort_index=index,
        )
        db.add(requirement)
        created.append(requirement)
    await db.flush()
    return [_serialize_requirement(item) for item in created]


@router.get("/api/projects/{project_id}/material-requirements", response_model=list[MaterialRequirementResponse])
async def list_project_material_requirements(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_project_member(project_id, current_user.id, db)
    result = await db.execute(
        select(MaterialRequirement)
        .where(MaterialRequirement.project_id == project_id)
        .order_by(MaterialRequirement.sort_index.asc(), MaterialRequirement.created_at.asc())
    )
    return [_serialize_requirement(item) for item in result.scalars().all()]


@router.put("/api/projects/{project_id}/material-requirements/{requirement_id}", response_model=MaterialRequirementResponse)
async def update_project_material_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    payload: MaterialRequirementUpdate,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_project_member(project_id, current_user.id, db)
    result = await db.execute(
        select(MaterialRequirement).where(
            and_(MaterialRequirement.id == requirement_id, MaterialRequirement.project_id == project_id)
        )
    )
    requirement = result.scalar_one_or_none()
    if not requirement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="材料需求不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(requirement, field, value)
    await db.flush()
    await db.refresh(requirement)
    return _serialize_requirement(requirement)


@router.post("/api/projects/{project_id}/material-requirements/{requirement_id}/match")
async def match_project_material_requirement(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_project_member(project_id, current_user.id, db)
    requirement_result = await db.execute(
        select(MaterialRequirement).where(
            and_(MaterialRequirement.id == requirement_id, MaterialRequirement.project_id == project_id)
        )
    )
    requirement = requirement_result.scalar_one_or_none()
    if not requirement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="材料需求不存在")
    asset_result = await db.execute(
        select(MaterialAsset).where(
            (MaterialAsset.scope == Scope.GLOBAL.value)
            | (MaterialAsset.owner_id == current_user.id)
            | (MaterialAsset.uploaded_by == current_user.id)
        )
    )
    candidates = build_material_requirement_candidates(
        requirement_name=requirement.requirement_name,
        requirement_text=requirement.requirement_text,
        requirement_category=requirement.category,
        requirement_tags=requirement.tags,
        assets=list(asset_result.scalars().all()),
    )
    if not candidates:
        requirement.status = MaterialRequirementStatus.MISSING
        await db.flush()
    return candidates


@router.post("/api/projects/{project_id}/material-requirements/{requirement_id}/confirm-match", response_model=MaterialRequirementResponse)
async def confirm_project_material_match(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    payload: MaterialMatchConfirmRequest,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_project_member(project_id, current_user.id, db)
    requirement_result = await db.execute(
        select(MaterialRequirement).where(
            and_(MaterialRequirement.id == requirement_id, MaterialRequirement.project_id == project_id)
        )
    )
    requirement = requirement_result.scalar_one_or_none()
    if not requirement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="材料需求不存在")
    asset_result = await db.execute(select(MaterialAsset).where(MaterialAsset.id == payload.material_asset_id))
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材不存在")
    requirement.status = MaterialRequirementStatus.MATCHED
    asset.usage_count += 1
    await db.flush()
    return _serialize_requirement(requirement)


@router.get("/api/projects/{project_id}/chapters/{chapter_id}/material-bindings", response_model=list[ChapterMaterialBindingResponse])
async def list_chapter_material_bindings(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_project_member(project_id, current_user.id, db)
    result = await db.execute(
        select(ChapterMaterialBinding)
        .where(
            and_(ChapterMaterialBinding.project_id == project_id, ChapterMaterialBinding.chapter_id == chapter_id)
        )
        .order_by(ChapterMaterialBinding.sort_index.asc(), ChapterMaterialBinding.created_at.asc())
    )
    bindings = result.scalars().all()
    for binding in bindings:
        await db.refresh(binding, attribute_names=["material_asset"])
    return [_serialize_binding(item) for item in bindings]


@router.post("/api/projects/{project_id}/chapters/{chapter_id}/material-bindings", response_model=ChapterMaterialBindingResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter_material_binding(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    payload: ChapterMaterialBindingCreate,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_project_member(project_id, current_user.id, db)
    chapter_result = await db.execute(select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.project_id == project_id)))
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")
    binding = ChapterMaterialBinding(
        project_id=project_id,
        chapter_id=chapter_id,
        material_requirement_id=payload.material_requirement_id,
        material_asset_id=payload.material_asset_id,
        anchor_type=payload.anchor_type,
        anchor_value=payload.anchor_value,
        display_mode=payload.display_mode,
        caption=payload.caption,
        sort_index=payload.sort_index,
        created_by=current_user.id,
    )
    db.add(binding)
    chapter.material_marker_enabled = True
    await db.flush()
    await db.refresh(binding)
    await db.refresh(binding, attribute_names=["material_asset"])
    return _serialize_binding(binding)


@router.put("/api/projects/{project_id}/chapters/{chapter_id}/material-bindings/{binding_id}", response_model=ChapterMaterialBindingResponse)
async def update_chapter_material_binding(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    binding_id: uuid.UUID,
    payload: ChapterMaterialBindingUpdate,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_project_member(project_id, current_user.id, db)
    result = await db.execute(
        select(ChapterMaterialBinding).where(
            and_(
                ChapterMaterialBinding.id == binding_id,
                ChapterMaterialBinding.project_id == project_id,
                ChapterMaterialBinding.chapter_id == chapter_id,
            )
        )
    )
    binding = result.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="绑定不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(binding, field, value)
    await db.flush()
    await db.refresh(binding)
    await db.refresh(binding, attribute_names=["material_asset"])
    return _serialize_binding(binding)


@router.delete("/api/projects/{project_id}/chapters/{chapter_id}/material-bindings/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chapter_material_binding(
    project_id: uuid.UUID,
    chapter_id: uuid.UUID,
    binding_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _verify_project_member(project_id, current_user.id, db)
    result = await db.execute(
        select(ChapterMaterialBinding).where(
            and_(
                ChapterMaterialBinding.id == binding_id,
                ChapterMaterialBinding.project_id == project_id,
                ChapterMaterialBinding.chapter_id == chapter_id,
            )
        )
    )
    binding = result.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="绑定不存在")
    await db.delete(binding)
