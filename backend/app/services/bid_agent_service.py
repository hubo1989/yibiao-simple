"""Bid Agent end-to-end orchestration service."""
from __future__ import annotations

import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.bid_agent import BidAgentRun, BidAgentRunStatus, BidAgentStep, BidAgentStepStatus
from ..models.chapter import Chapter, ChapterStatus
from ..models.project import Project
from ..models.response_matrix import ResponseMatrixItem, ResponseStatus, TenderClause
from ..config import settings
from . import response_matrix_service
from .anti_hallucination_service import AntiHallucinationService
from .openai_service import OpenAIService

logger = logging.getLogger(__name__)
BidAgentEventCallback = Callable[[dict[str, Any]], Awaitable[None]]

# Lazy import to avoid circular dependency at module level
def _get_export_preflight_fn():
    from ..routers.export import build_export_preflight_payload
    return build_export_preflight_payload


GENERATE_DRAFT_STEPS: list[tuple[str, str]] = [
    ("ensure_project_analysis", "分析招标文件"),
    ("ensure_outline", "生成目录结构"),
    ("rebuild_response_matrix", "重建响应矩阵"),
    ("generate_chapter_contents", "逐章生成正文并保存证据"),
    ("response_matrix_preflight", "响应矩阵质量检查"),
    ("export_preflight", "导出前质量检查"),
    ("assemble_quality_report", "生成质量报告"),
]

FIX_RISKS_STEPS: list[tuple[str, str]] = [
    ("response_matrix_preflight", "响应矩阵质量检查"),
    ("export_preflight", "导出前质量检查"),
    ("assemble_quality_report", "生成质量报告"),
]


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


async def create_run(
    db: AsyncSession,
    project_id: uuid.UUID,
    created_by: uuid.UUID | None,
    goal: str = "generate_draft",
) -> BidAgentRun:
    run = BidAgentRun(project_id=project_id, created_by=created_by, goal=goal)
    db.add(run)
    await db.flush()
    await initialize_steps(db, run)
    return run


async def initialize_steps(db: AsyncSession, run: BidAgentRun) -> list[BidAgentStep]:
    definitions = FIX_RISKS_STEPS if run.goal == "fix_risks" else GENERATE_DRAFT_STEPS
    steps = [
        BidAgentStep(run_id=run.id, step_key=key, step_name=name, order_index=index)
        for index, (key, name) in enumerate(definitions, start=1)
    ]
    for step in steps:
        db.add(step)
    await db.flush()
    return steps


async def get_run(db: AsyncSession, run_id: uuid.UUID) -> BidAgentRun | None:
    result = await db.execute(select(BidAgentRun).where(BidAgentRun.id == run_id))
    return result.scalar_one_or_none()


async def get_latest_run(db: AsyncSession, project_id: uuid.UUID) -> BidAgentRun | None:
    result = await db.execute(
        select(BidAgentRun)
        .where(BidAgentRun.project_id == project_id)
        .order_by(BidAgentRun.created_at.desc(), BidAgentRun.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one_or_none()


async def list_steps(db: AsyncSession, run_id: uuid.UUID) -> list[BidAgentStep]:
    result = await db.execute(
        select(BidAgentStep).where(BidAgentStep.run_id == run_id).order_by(BidAgentStep.order_index)
    )
    return list(result.scalars().all())


async def _complete_step(step: BidAgentStep, summary: str, result: dict[str, Any] | None = None) -> None:
    step.status = BidAgentStepStatus.completed
    step.progress = 100
    step.summary = summary
    step.result_json = result or {}
    step.completed_at = datetime.now(timezone.utc)


async def _start_step(step: BidAgentStep) -> None:
    step.status = BidAgentStepStatus.running
    step.progress = 10
    step.started_at = datetime.now(timezone.utc)


def _dt(value: Any) -> str | None:
    return value.isoformat() if value else None


def run_payload(run: BidAgentRun) -> dict[str, Any]:
    data = run.__dict__
    status = data.get("status")
    return {
        "id": str(data.get("id") or ""),
        "project_id": str(data.get("project_id") or ""),
        "created_by": str(data.get("created_by")) if data.get("created_by") else None,
        "goal": data.get("goal") or "",
        "status": status.value if hasattr(status, "value") else str(status or ""),
        "progress": data.get("progress") or 0,
        "summary": data.get("summary") or "",
        "error_message": data.get("error_message") or "",
        "result_json": _jsonable(data.get("result_json") or {}),
        "created_at": _dt(data.get("created_at")),
        "updated_at": _dt(data.get("updated_at")),
    }


def step_payload(step: BidAgentStep) -> dict[str, Any]:
    data = step.__dict__
    status = data.get("status")
    return {
        "id": str(data.get("id") or ""),
        "run_id": str(data.get("run_id") or ""),
        "step_key": data.get("step_key") or "",
        "step_name": data.get("step_name") or "",
        "status": status.value if hasattr(status, "value") else str(status or ""),
        "order_index": data.get("order_index") or 0,
        "progress": data.get("progress") or 0,
        "summary": data.get("summary") or "",
        "error_message": data.get("error_message") or "",
        "result_json": _jsonable(data.get("result_json") or {}),
        "started_at": _dt(data.get("started_at")),
        "completed_at": _dt(data.get("completed_at")),
    }


async def _emit(callback: BidAgentEventCallback | None, event: dict[str, Any]) -> None:
    if callback:
        await callback(event)


def _fallback_project_analysis(file_content: str, raw_text: str = "") -> dict[str, str]:
    """Build a usable analysis when the model returns empty or non-JSON content."""
    source = (file_content or "").strip()
    raw = (raw_text or "").strip()
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    requirement_lines = [
        line
        for line in lines
        if any(keyword in line for keyword in ("技术", "评分", "要求", "响应", "服务", "交付", "验收", "资格"))
    ]

    overview = raw[:1200] or "\n".join(lines[:20])[:1500] or "已上传招标文件，系统将基于原文生成投标响应。"
    requirements = "\n".join(requirement_lines[:80])[:5000] or source[:5000] or raw[:5000]
    return {
        "project_overview": overview,
        "tech_requirements": requirements or "未识别到明确评分条款，请在后续响应矩阵中人工补充。",
    }


async def ensure_project_analysis(db: AsyncSession, project_id: uuid.UUID) -> dict[str, Any]:
    project = await get_project(db, project_id)
    if not project:
        raise ValueError("Project not found")
    if project.project_overview and project.tech_requirements:
        return {"skipped": True, "reason": "analysis_exists"}
    if not project.file_content:
        raise ValueError("项目缺少招标文件内容，无法分析")

    service = OpenAIService(db=db, project_id=project_id)
    if hasattr(service, "analyze_document"):
        analysis = await service.analyze_document(project.file_content)  # type: ignore[attr-defined]
    else:
        prompt = (
            "请分析以下招标文件，返回 JSON："
            "{\"project_overview\":\"项目概述\",\"tech_requirements\":\"技术/评分要求\"}\n\n"
            f"{project.file_content}"
        )
        chunks: list[str] = []
        raw_analysis = ""
        try:
            async with asyncio.timeout(60):
                async for chunk in service.stream_chat_completion([{"role": "user", "content": prompt}], temperature=0.2):
                    chunks.append(chunk)
            raw_analysis = "".join(chunks).strip()
            analysis = json.loads(raw_analysis)
        except Exception:
            analysis = _fallback_project_analysis(project.file_content, raw_analysis)

    project.project_overview = str(analysis.get("project_overview") or analysis.get("overview") or "")
    project.tech_requirements = str(analysis.get("tech_requirements") or analysis.get("requirements") or "")
    if not project.project_overview or not project.tech_requirements:
        raise ValueError("招标文件分析结果不完整")
    await db.flush()
    return {
        "skipped": False,
        "project_overview_length": len(project.project_overview),
        "tech_requirements_length": len(project.tech_requirements),
    }


def _outline_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("children", "sub_chapters", "chapters", "sections", "items"):
        value = node.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


async def _create_chapters_from_outline(
    db: AsyncSession,
    project_id: uuid.UUID,
    nodes: list[dict[str, Any]],
    parent_id: uuid.UUID | None = None,
    prefix: str = "",
) -> int:
    count = 0
    for index, node in enumerate(nodes, start=1):
        number = str(node.get("chapter_number") or node.get("number") or (f"{prefix}.{index}" if prefix else str(index)))
        chapter = Chapter(
            project_id=project_id,
            parent_id=parent_id,
            chapter_number=number,
            title=str(node.get("title") or node.get("new_title") or node.get("name") or f"第{number}章"),
            rating_item=node.get("rating_item"),
            chapter_role=node.get("chapter_role"),
            avoid_overlap=node.get("avoid_overlap"),
            order_index=index,
        )
        db.add(chapter)
        await db.flush()
        count += 1
        count += await _create_chapters_from_outline(db, project_id, _outline_children(node), chapter.id, number)
    return count


async def ensure_outline(db: AsyncSession, project_id: uuid.UUID) -> dict[str, Any]:
    existing = await db.execute(select(Chapter.id).where(Chapter.project_id == project_id).limit(1))
    if existing.scalar_one_or_none():
        return {"skipped": True, "reason": "chapters_exist"}
    project = await get_project(db, project_id)
    if not project:
        raise ValueError("Project not found")
    if not project.project_overview or not project.tech_requirements:
        await ensure_project_analysis(db, project_id)
        project = await get_project(db, project_id)
    outline_result = {"outline": _fallback_outline_from_analysis(project)}

    nodes = outline_result.get("outline") if isinstance(outline_result, dict) else outline_result
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("目录生成结果为空")
    created = await _create_chapters_from_outline(db, project_id, nodes)
    return {
        "skipped": False,
        "created_count": created,
        "fallback": True,
        "fallback_reason": "bid_agent_stable_outline",
    }


def _fallback_outline_from_analysis(project: Project) -> list[dict[str, Any]]:
    """Build a stable bid outline when the LLM outline JSON drifts or times out."""
    overview = (project.project_overview or "").strip()
    requirements = (project.tech_requirements or "").strip()
    context_hint = "\n\n".join(part for part in [overview[:800], requirements[:1200]] if part)
    suffix = f"\n\n写作依据：{context_hint}" if context_hint else ""
    return [
        {
            "chapter_number": "1",
            "title": "项目理解与总体响应",
            "rating_item": "项目理解、总体方案与服务响应",
            "chapter_role": "说明对招标目标、服务范围、实施边界和响应承诺的整体理解。",
            "avoid_overlap": "不展开具体技术参数逐项应答，避免与后续章节重复。",
            "children": [
                {
                    "chapter_number": "1.1",
                    "title": "项目背景与建设目标理解",
                    "rating_item": "项目背景与目标",
                    "chapter_role": f"提炼项目背景、采购目标、服务期和实施范围。{suffix}",
                },
                {
                    "chapter_number": "1.2",
                    "title": "总体响应承诺",
                    "rating_item": "响应承诺",
                    "chapter_role": "对招标文件的实质性要求、关键条款和服务承诺进行总括响应。",
                },
            ],
        },
        {
            "chapter_number": "2",
            "title": "技术方案与产品响应",
            "rating_item": "技术指标、产品参数、定制化能力",
            "chapter_role": "逐项回应技术指标、产品要求、参数符合性和定制化特色。",
            "avoid_overlap": "具体实施计划放在实施组织章节，售后服务放在服务保障章节。",
            "children": [
                {
                    "chapter_number": "2.1",
                    "title": "技术指标逐项响应",
                    "rating_item": "技术指标",
                    "chapter_role": "按照招标技术指标逐条说明满足情况、支撑依据和风险控制。",
                },
                {
                    "chapter_number": "2.2",
                    "title": "产品能力与场景适配",
                    "rating_item": "产品知名度、市场口碑、场景适配",
                    "chapter_role": "说明产品成熟度、市场应用、场景适配和邮政定制化能力。",
                },
            ],
        },
        {
            "chapter_number": "3",
            "title": "实施组织与交付计划",
            "rating_item": "实施方案、人员组织、进度保障",
            "chapter_role": "描述项目组织、实施路径、里程碑、培训上线和验收安排。",
            "children": [
                {
                    "chapter_number": "3.1",
                    "title": "项目组织与职责分工",
                    "rating_item": "人员与组织保障",
                    "chapter_role": "说明项目团队角色、职责边界、沟通机制和资源投入。",
                },
                {
                    "chapter_number": "3.2",
                    "title": "实施进度与验收安排",
                    "rating_item": "实施进度与交付验收",
                    "chapter_role": "给出可执行的实施计划、关键节点、验收标准和交付物。",
                },
            ],
        },
        {
            "chapter_number": "4",
            "title": "服务保障与风险控制",
            "rating_item": "售后服务、运维保障、风险控制",
            "chapter_role": "说明服务体系、响应时效、故障处理、风险识别与应急措施。",
            "children": [
                {
                    "chapter_number": "4.1",
                    "title": "售后与运维服务体系",
                    "rating_item": "服务保障",
                    "chapter_role": "阐述售后服务组织、服务内容、响应时限和持续运维机制。",
                },
                {
                    "chapter_number": "4.2",
                    "title": "风险识别与应急预案",
                    "rating_item": "风险控制",
                    "chapter_role": "覆盖实施、技术、运营、数据安全等风险及处置预案。",
                },
            ],
        },
        {
            "chapter_number": "5",
            "title": "商务与合规响应",
            "rating_item": "商务条款、资质要求、无效投标风险",
            "chapter_role": "汇总商务、资质、签署、报价和无效投标条款响应。",
            "children": [
                {
                    "chapter_number": "5.1",
                    "title": "商务条款响应",
                    "rating_item": "商务响应",
                    "chapter_role": "说明服务期、报价、付款、协议履约和订单执行等商务条款响应。",
                },
                {
                    "chapter_number": "5.2",
                    "title": "资质与合规材料响应",
                    "rating_item": "资质材料与合规要求",
                    "chapter_role": "列明需提交的资质、证明材料、签章要求和废标风险控制。",
                },
            ],
        },
    ]


async def get_leaf_chapters(db: AsyncSession, project_id: uuid.UUID) -> list[Chapter]:
    result = await db.execute(select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_number, Chapter.order_index))
    chapters = list(result.scalars().all())
    parent_ids = {c.parent_id for c in chapters if c.parent_id}
    return [c for c in chapters if c.id not in parent_ids]


async def update_response_matrix_after_chapter_generation(
    db: AsyncSession,
    project_id: uuid.UUID,
    chapter: Chapter,
    content: str,
    source_refs: list[dict[str, Any]],
    hallucination_issues: list[Any],
) -> dict[str, int]:
    """Upgrade/downgrade matrix item status based on generated content and evidence.

    Auto-bind only establishes likely ownership. This pass records whether the
    generated chapter actually mentions/supports each bound clause.
    """
    result = await db.execute(
        select(ResponseMatrixItem, TenderClause)
        .join(TenderClause, ResponseMatrixItem.clause_id == TenderClause.id)
        .where(
            ResponseMatrixItem.project_id == project_id,
            ResponseMatrixItem.chapter_id == str(chapter.id),
            TenderClause.project_id == project_id,
        )
    )
    content_lower = (content or "").lower()
    evidence_text = " ".join(
        str(ref.get("quote") or "") + " " + str(ref.get("source_title") or "")
        for ref in source_refs
    ).lower()
    critical_count = sum(1 for issue in hallucination_issues if getattr(issue, "severity", "") == "critical")
    updated = covered = risk = missing = 0
    for item, clause in result.all():
        clause_text = " ".join(part for part in [clause.title, clause.content, clause.raw_requirement] if part)
        keywords = []
        if clause.metadata_json:
            keywords = [str(k).lower() for k in clause.metadata_json.get("keywords", []) if str(k).strip()]
        candidates = [w.lower() for w in clause_text.replace("，", " ").replace("。", " ").split() if len(w) >= 2][:12]
        hit = any(kw and kw in content_lower for kw in keywords) or any(w in content_lower for w in candidates)
        evidence_hit = bool(evidence_text and any(w in evidence_text for w in candidates[:8]))
        if critical_count:
            item.response_status = ResponseStatus.risk
            item.risk_note = f"章节生成后仍存在 {critical_count} 项无证据关键表述"
            risk += 1
        elif hit or evidence_hit:
            item.response_status = ResponseStatus.covered
            item.response_summary = f"已在章节《{chapter.title}》生成内容中响应该条款"
            item.evidence_summary = "已关联证据引用" if source_refs else "基于章节正文匹配"
            item.risk_note = ""
            covered += 1
        else:
            item.response_status = ResponseStatus.missing if clause.is_fatal else ResponseStatus.partial
            item.risk_note = "章节已生成，但未在正文中明显覆盖该条款"
            missing += 1
        updated += 1
    await db.flush()
    return {"updated": updated, "covered": covered, "risk": risk, "missing": missing}


async def generate_chapter_with_evidence(
    db: AsyncSession,
    project_id: uuid.UUID,
    chapter: Chapter,
    created_by: uuid.UUID | None,
) -> dict[str, Any]:
    from ..routers.content import _get_response_matrix_context, _get_response_matrix_source_refs, save_evidence_refs

    project = await get_project(db, project_id)
    if not project:
        raise ValueError("Project not found")
    response_matrix_context = await _get_response_matrix_context(db, project_id, str(chapter.id), chapter.title)
    source_refs = await _get_response_matrix_source_refs(db, project_id, str(chapter.id), chapter.title)
    content_parts: list[str] = []
    if settings.bid_agent_use_llm_chapters:
        service = OpenAIService(db=db, project_id=project_id)
        try:
            async with asyncio.timeout(max(1, settings.bid_agent_chapter_timeout_seconds)):
                async for chunk in service._generate_chapter_content(
                    chapter={
                        "id": str(chapter.id),
                        "title": chapter.title,
                        "rating_item": chapter.rating_item,
                        "chapter_role": chapter.chapter_role,
                        "avoid_overlap": chapter.avoid_overlap,
                    },
                    project_overview=project.project_overview or "",
                    tech_requirements=project.tech_requirements or "",
                    knowledge_context=response_matrix_context,
                    project_response_matrix=response_matrix_context,
                    chapter_rating_focus=chapter.rating_item or "",
                    chapter_role=chapter.chapter_role or "",
                    adjacent_boundary=chapter.avoid_overlap or "",
                ):
                    content_parts.append(chunk)
        except Exception as exc:
            logger.warning(
                "BidAgent chapter LLM generation fell back for chapter %s: %s",
                chapter.id,
                exc,
            )

    if not content_parts:
        content_parts = [
            _fallback_chapter_content(
                project=project,
                chapter=chapter,
                response_matrix_context=response_matrix_context,
            )
        ]
    content = "".join(content_parts)
    chapter.content = content
    chapter.status = ChapterStatus.GENERATED
    await save_evidence_refs(db, project_id, chapter.id, source_refs)
    issues = AntiHallucinationService().scan_text(content, source_refs)
    matrix_update = await update_response_matrix_after_chapter_generation(
        db, project_id, chapter, content, source_refs, issues
    )
    await db.flush()
    return {
        "chapter_id": str(chapter.id),
        "title": chapter.title,
        "content_length": len(content),
        "evidence_ref_count": len(source_refs),
        "hallucination_issue_count": len(issues),
        "response_matrix_update": matrix_update,
    }


def _fallback_chapter_content(
    *,
    project: Project,
    chapter: Chapter,
    response_matrix_context: str = "",
) -> str:
    """Generate a deterministic chapter body when model generation is unavailable."""
    overview = (project.project_overview or "").strip()[:800]
    requirements = (project.tech_requirements or "").strip()[:1200]
    matrix = (response_matrix_context or "").strip()[:1200]
    role = chapter.chapter_role or "围绕本章主题说明响应方案、执行动作和验收方式。"
    rating = chapter.rating_item or "本章相关评分项"
    return (
        f"## {chapter.chapter_number} {chapter.title}\n\n"
        f"### 响应目标\n"
        f"本章围绕“{rating}”展开，重点回应招标文件中与本章相关的实质性要求。{role}\n\n"
        f"### 招标要求理解\n"
        f"{overview or '本项目已上传招标文件，以下内容基于招标原文和响应矩阵组织。'}\n\n"
        f"### 响应措施\n"
        f"1. 建立与招标要求一致的工作机制，明确责任人、交付物、验收口径和时间节点。\n"
        f"2. 围绕技术、服务、合规和交付要求逐项响应，确保正文内容可回溯到招标条款。\n"
        f"3. 对关键风险设置检查点，形成过程记录、问题闭环和最终验收材料。\n\n"
        f"### 条款覆盖\n"
        f"{matrix or requirements or '响应矩阵尚未提取到明确条款，本章按项目概述和技术要求进行基础响应。'}\n\n"
        f"### 交付与验收\n"
        f"本章承诺按招标文件要求完成对应工作，并在实施过程中提供必要的证明材料、过程记录和验收依据。"
    )


async def generate_chapter_contents(
    db: AsyncSession,
    project_id: uuid.UUID,
    created_by: uuid.UUID | None = None,
) -> dict[str, Any]:
    leaves = await get_leaf_chapters(db, project_id)
    summaries: list[dict[str, Any]] = []
    skipped = 0
    issue_count = 0
    for chapter in leaves:
        if chapter.content:
            skipped += 1
            continue
        summary = await generate_chapter_with_evidence(db, project_id, chapter, created_by)
        summaries.append(summary)
        issue_count += int(summary.get("hallucination_issue_count") or 0)
    return {
        "generated_count": len(summaries),
        "skipped_count": skipped,
        "hallucination_issue_count": issue_count,
        "per_chapter": summaries,
    }


async def build_quality_report(
    db: AsyncSession,
    project_id: uuid.UUID,
    pipeline_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _get_preflight = _get_export_preflight_fn()
    matrix_preflight = _jsonable(await response_matrix_service.preflight(db, project_id))
    export_preflight = _jsonable(await _get_preflight(db, str(project_id)))
    blockers = list(matrix_preflight.get("blockers") or [])
    blockers.extend(
        f"{item.get('chapter_title', '章节')} 存在 {len(item.get('issues') or [])} 项导出阻断问题"
        for item in export_preflight.get("blockers") or []
    )
    stats = pipeline_stats or {}
    return {
        "project_id": str(project_id),
        "response_matrix_preflight": matrix_preflight,
        "export_preflight": export_preflight,
        "ready": bool(matrix_preflight.get("ready")) and not bool(export_preflight.get("block_export")),
        "blockers": blockers,
        "generated_count": int(stats.get("generated_count") or 0),
        "pipeline_stats": stats,
    }


async def execute_generate_draft(
    db: AsyncSession,
    run_id: uuid.UUID,
    on_event: BidAgentEventCallback | None = None,
) -> BidAgentRun:
    """Run full Bid Agent orchestration synchronously."""
    run = await get_run(db, run_id)
    if not run:
        raise ValueError("BidAgentRun not found")

    run.status = BidAgentRunStatus.running
    run.progress = 1
    await db.flush()
    await _emit(on_event, {"type": "run", "run": run_payload(run)})

    steps = await list_steps(db, run.id)
    pipeline_stats: dict[str, Any] = {}
    try:
        for index, step in enumerate(steps, start=1):
            await _start_step(step)
            await db.flush()
            await _emit(on_event, {"type": "step", "step": step_payload(step), "run": run_payload(run)})

            try:
                if step.step_key == "ensure_project_analysis":
                    result = await ensure_project_analysis(db, run.project_id)
                    await _complete_step(
                        step,
                        "招标文件分析完成" if not result.get("skipped") else "已有招标文件分析，已跳过",
                        result,
                    )
                elif step.step_key == "ensure_outline":
                    result = await ensure_outline(db, run.project_id)
                    await _complete_step(
                        step,
                        "目录结构已生成" if not result.get("skipped") else "已有目录结构，已跳过",
                        result,
                    )
                elif step.step_key == "rebuild_response_matrix":
                    logger.info(f"BidAgent step 'rebuild_response_matrix' for project {run.project_id}")
                    summary = await response_matrix_service.rebuild_from_project(db, run.project_id)
                    await _complete_step(step, "响应矩阵已重建", {"response_matrix_summary": _jsonable(summary)})
                elif step.step_key == "generate_chapter_contents":
                    logger.info(f"BidAgent step 'generate_chapter_contents' for project {run.project_id}")
                    pipeline_stats = await generate_chapter_contents(db, run.project_id, run.created_by)
                    await _complete_step(step, "章节正文生成完成", pipeline_stats)
                elif step.step_key == "response_matrix_preflight":
                    preflight = await response_matrix_service.preflight(db, run.project_id)
                    await _complete_step(step, "响应矩阵检查完成", {"preflight": _jsonable(preflight)})
                elif step.step_key == "export_preflight":
                    build_export_preflight_payload = _get_export_preflight_fn()
                    export_preflight = await build_export_preflight_payload(db, str(run.project_id))
                    await _complete_step(step, "导出前检查完成", {"export_preflight": _jsonable(export_preflight)})
                elif step.step_key == "assemble_quality_report":
                    report = await build_quality_report(db, run.project_id, pipeline_stats)
                    await _complete_step(step, "质量报告已生成", {"quality_report": report})
                else:
                    step.status = BidAgentStepStatus.skipped
                    step.progress = 100
                    step.summary = "未知步骤，已跳过"
                    step.completed_at = datetime.now(timezone.utc)

            except Exception as step_exc:
                # Per-step failure: mark this step failed but continue with remaining steps
                # This gives the user a partial result instead of a total 500
                logger.error(f"BidAgent step '{step.step_key}' failed: {step_exc}", exc_info=True)
                step.status = BidAgentStepStatus.failed
                step.error_message = f"{type(step_exc).__name__}: {step_exc}"
                step.progress = 0
                step.completed_at = datetime.now(timezone.utc)
                step.summary = f"步骤执行失败: {str(step_exc)[:200]}"
                await db.flush()
                await _emit(
                    on_event,
                    {"type": "step", "step": step_payload(step), "run": run_payload(run)},
                )
                continue

            run.progress = round(index / len(steps) * 100)
            await db.flush()
            await _emit(on_event, {"type": "step", "step": step_payload(step), "run": run_payload(run)})
            await _emit(on_event, {"type": "run", "run": run_payload(run)})

        failed_steps = [step for step in steps if step.status == BidAgentStepStatus.failed]
        quality_report = await build_quality_report(db, run.project_id, pipeline_stats)
        run.result_json = {"quality_report": quality_report}
        run.progress = 100
        if failed_steps:
            failed_keys = "、".join(step.step_key for step in failed_steps)
            run.status = BidAgentRunStatus.failed
            run.error_message = f"以下步骤执行失败：{failed_keys}"
            run.summary = f"编排未完成，失败步骤：{failed_keys}"
            await db.flush()
            await _emit(
                on_event,
                {
                    "type": "failed",
                    "run": run_payload(run),
                    "quality_report": quality_report,
                    "error": run.error_message,
                },
            )
            return run

        run.summary = "一键草稿编排完成" if quality_report.get("ready") else "一键草稿编排完成，但存在导出/响应矩阵阻断项"
        if run.goal == "fix_risks":
            run.summary = "风险检查完成"
        run.status = BidAgentRunStatus.completed
        await db.flush()
        await _emit(on_event, {"type": "completed", "run": run_payload(run), "quality_report": quality_report})
    except Exception as exc:  # pragma: no cover - defensive failure path
        logger.error(f"BidAgent run {run_id} failed at top level: {exc}", exc_info=True)
        run.status = BidAgentRunStatus.failed
        run.error_message = str(exc)
        for step in steps:
            if step.status == BidAgentStepStatus.running:
                step.status = BidAgentStepStatus.failed
                step.error_message = str(exc)
                step.completed_at = datetime.now(timezone.utc)
        await db.flush()
        await _emit(on_event, {"type": "failed", "run": run_payload(run), "error": str(exc)})
        raise
    finally:
        await db.commit()
        await db.refresh(run)

    return run
