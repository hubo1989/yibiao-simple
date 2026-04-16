"""废标检查 API 路由

提供从招标文件提取否决性条款、查询检查清单、更新检查状态等接口。
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import require_editor
from ..db.database import get_db
from ..models.disqualification import DisqualificationCheck
from ..models.project import Project, project_members
from ..models.user import User
from ..services.openai_service import OpenAIService
from ..services.prompt_service import PromptService

router = APIRouter(prefix="/api/disqualification", tags=["废标检查"])


# ============ Pydantic Schema ============

class ExtractDisqualificationRequest(BaseModel):
    project_id: str = Field(..., description="项目ID")
    model_name: Optional[str] = Field(None, description="可选模型名称")
    provider_config_id: Optional[str] = Field(None, description="可选 Provider 配置 ID")


class DisqualificationItemResponse(BaseModel):
    id: str
    item_id: str
    category: str
    requirement: str
    check_type: str
    severity: str
    source_text: Optional[str] = None
    status: str
    checked_by: Optional[str] = None
    checked_at: Optional[str] = None
    note: Optional[str] = None


class UpdateCheckItemRequest(BaseModel):
    status: str = Field(..., description="passed / failed / not_applicable / unchecked")
    note: Optional[str] = Field(None, description="备注")


class DisqualificationSummary(BaseModel):
    total: int
    checked: int
    passed: int
    failed: int
    not_applicable: int
    unchecked: int
    fatal_unresolved: int  # fatal 且未通过（failed 或 unchecked）


class ValidateBeforeExportResponse(BaseModel):
    has_risk: bool
    fatal_unresolved_items: List[DisqualificationItemResponse]
    message: str


# ============ 辅助函数 ============

async def _verify_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Project:
    """验证用户是项目成员并返回项目"""
    from sqlalchemy import exists

    member_exists = await db.execute(
        select(
            exists().where(
                and_(
                    project_members.c.project_id == project_id,
                    project_members.c.user_id == user_id,
                )
            )
        )
    )
    if not member_exists.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或您没有访问权限",
        )

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )
    return project


def _item_to_response(item: DisqualificationCheck) -> DisqualificationItemResponse:
    return DisqualificationItemResponse(
        id=str(item.id),
        item_id=item.item_id,
        category=item.category,
        requirement=item.requirement,
        check_type=item.check_type,
        severity=item.severity,
        source_text=item.source_text,
        status=item.status,
        checked_by=str(item.checked_by) if item.checked_by else None,
        checked_at=item.checked_at.isoformat() if item.checked_at else None,
        note=item.note,
    )


# ============ 接口 ============

@router.post("/extract", response_model=List[DisqualificationItemResponse])
async def extract_disqualification_items(
    request: ExtractDisqualificationRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """从项目招标文件中提取否决性条款（调用 AI），保存到数据库并返回结果"""
    try:
        project_uuid = uuid.UUID(request.project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的项目ID格式")

    project = await _verify_project_member(project_uuid, current_user.id, db)

    if not project.file_content:
        raise HTTPException(status_code=400, detail="项目尚未上传招标文件，请先上传")

    # 调用 AI 提取
    openai_service = OpenAIService(db=db, project_id=project_uuid)
    if request.provider_config_id:
        configured = await openai_service.use_config_by_id(request.provider_config_id)
        if not configured:
            raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
    else:
        await openai_service._ensure_initialized()

    if not openai_service.api_key:
        raise HTTPException(status_code=400, detail="请先配置 AI API 密钥")

    if request.model_name:
        openai_service.set_model(request.model_name)

    prompt_service = PromptService(db)
    prompt, _ = await prompt_service.get_prompt("extract_disqualification_items", project_uuid)
    system_prompt, user_template = PromptService.split_prompt(prompt)
    user_prompt = prompt_service.render_prompt(
        user_template, {"file_content": project.file_content}
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # 收集完整结果（使用内部辅助方法）
    full_response = await openai_service._collect_stream_text(messages, temperature=0.1)

    # 解析 JSON
    raw_text = full_response.strip()
    # 去掉可能的代码块标记
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    try:
        parsed: Dict[str, Any] = json.loads(raw_text)
        items_data: List[Dict[str, Any]] = parsed.get("disqualification_items", [])
    except (json.JSONDecodeError, AttributeError):
        raise HTTPException(status_code=500, detail="AI 返回的数据格式无效，请重试")

    if not items_data:
        raise HTTPException(status_code=422, detail="未能从招标文件中提取到废标检查项，请检查文件内容")

    # 清除该项目旧的检查项
    await db.execute(
        delete(DisqualificationCheck).where(
            DisqualificationCheck.project_id == project_uuid
        )
    )

    # 写入新数据
    new_items: List[DisqualificationCheck] = []
    for item_data in items_data:
        check = DisqualificationCheck(
            id=uuid.uuid4(),
            project_id=project_uuid,
            item_id=item_data.get("id", "DQ000"),
            category=item_data.get("category", "其他"),
            requirement=item_data.get("requirement", ""),
            check_type=item_data.get("check_type", "other"),
            severity=item_data.get("severity", "warning"),
            source_text=item_data.get("source_text"),
            status="unchecked",
        )
        db.add(check)
        new_items.append(check)

    await db.commit()
    for item in new_items:
        await db.refresh(item)

    return [_item_to_response(item) for item in new_items]


@router.get("/{project_id}", response_model=List[DisqualificationItemResponse])
async def list_disqualification_items(
    project_id: str,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取项目的废标检查清单"""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的项目ID格式")

    await _verify_project_member(project_uuid, current_user.id, db)

    result = await db.execute(
        select(DisqualificationCheck)
        .where(DisqualificationCheck.project_id == project_uuid)
        .order_by(DisqualificationCheck.item_id)
    )
    items = result.scalars().all()
    return [_item_to_response(item) for item in items]


@router.put("/{project_id}/{item_id}", response_model=DisqualificationItemResponse)
async def update_disqualification_item(
    project_id: str,
    item_id: str,
    request: UpdateCheckItemRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """更新废标检查项状态（passed/failed/not_applicable + 备注）"""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的项目ID格式")

    await _verify_project_member(project_uuid, current_user.id, db)

    # 先尝试按数据库 UUID 查找，再按 item_id 查找
    db_item: Optional[DisqualificationCheck] = None
    try:
        item_uuid = uuid.UUID(item_id)
        result = await db.execute(
            select(DisqualificationCheck).where(
                and_(
                    DisqualificationCheck.id == item_uuid,
                    DisqualificationCheck.project_id == project_uuid,
                )
            )
        )
        db_item = result.scalar_one_or_none()
    except ValueError:
        pass

    if not db_item:
        # 按 item_id 字段查
        result = await db.execute(
            select(DisqualificationCheck).where(
                and_(
                    DisqualificationCheck.item_id == item_id,
                    DisqualificationCheck.project_id == project_uuid,
                )
            )
        )
        db_item = result.scalar_one_or_none()

    if not db_item:
        raise HTTPException(status_code=404, detail="检查项不存在")

    valid_statuses = {"unchecked", "passed", "failed", "not_applicable"}
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效状态，合法值：{valid_statuses}")

    db_item.status = request.status
    if request.note is not None:
        db_item.note = request.note
    if request.status != "unchecked":
        db_item.checked_by = current_user.id
        db_item.checked_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(db_item)
    return _item_to_response(db_item)


@router.get("/{project_id}/summary", response_model=DisqualificationSummary)
async def get_disqualification_summary(
    project_id: str,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取废标检查摘要"""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的项目ID格式")

    await _verify_project_member(project_uuid, current_user.id, db)

    result = await db.execute(
        select(DisqualificationCheck).where(
            DisqualificationCheck.project_id == project_uuid
        )
    )
    items = result.scalars().all()

    total = len(items)
    passed = sum(1 for i in items if i.status == "passed")
    failed = sum(1 for i in items if i.status == "failed")
    not_applicable = sum(1 for i in items if i.status == "not_applicable")
    unchecked = sum(1 for i in items if i.status == "unchecked")
    checked = total - unchecked

    # fatal 且未解决（failed 或 unchecked）
    fatal_unresolved = sum(
        1 for i in items
        if i.severity == "fatal" and i.status in ("unchecked", "failed")
    )

    return DisqualificationSummary(
        total=total,
        checked=checked,
        passed=passed,
        failed=failed,
        not_applicable=not_applicable,
        unchecked=unchecked,
        fatal_unresolved=fatal_unresolved,
    )


@router.post("/{project_id}/validate-before-export", response_model=ValidateBeforeExportResponse)
async def validate_before_export(
    project_id: str,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """导出前校验：返回所有 fatal 且未通过的检查项"""
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的项目ID格式")

    await _verify_project_member(project_uuid, current_user.id, db)

    result = await db.execute(
        select(DisqualificationCheck).where(
            and_(
                DisqualificationCheck.project_id == project_uuid,
                DisqualificationCheck.severity == "fatal",
                DisqualificationCheck.status.in_(["unchecked", "failed"]),
            )
        ).order_by(DisqualificationCheck.item_id)
    )
    risk_items = result.scalars().all()

    has_risk = len(risk_items) > 0
    message = ""
    if has_risk:
        message = f"存在 {len(risk_items)} 项废标风险（fatal 级别未通过），请确认后再导出"
    else:
        message = "未发现废标风险，可以安全导出"

    return ValidateBeforeExportResponse(
        has_risk=has_risk,
        fatal_unresolved_items=[_item_to_response(i) for i in risk_items],
        message=message,
    )
