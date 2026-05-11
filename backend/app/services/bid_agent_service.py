"""Bid Agent end-to-end orchestration service."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.bid_agent import BidAgentRun, BidAgentRunStatus, BidAgentStep, BidAgentStepStatus
from ..models.chapter import Chapter, ChapterStatus
from ..models.project import Project
from ..models.response_matrix import ResponseMatrixItem, ResponseStatus, TenderClause
from . import response_matrix_service
from .anti_hallucination_service import AntiHallucinationService
from .openai_service import OpenAIService
from ..routers.export import build_export_preflight_payload


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
    await db.commit()
    await db.refresh(run)
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
        async for chunk in service.stream_chat_completion([{"role": "user", "content": prompt}], temperature=0.2):
            chunks.append(chunk)
        analysis = json.loads("".join(chunks).strip())

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
    service = OpenAIService(db=db, project_id=project_id)
    outline_result = await service.generate_outline_v2(project.project_overview or "", project.tech_requirements or "")
    nodes = outline_result.get("outline") if isinstance(outline_result, dict) else outline_result
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("目录生成结果为空")
    created = await _create_chapters_from_outline(db, project_id, nodes)
    return {"skipped": False, "created_count": created}


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
    service = OpenAIService(db=db, project_id=project_id)
    content_parts: list[str] = []
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
    matrix_preflight = _jsonable(await response_matrix_service.preflight(db, project_id))
    export_preflight = _jsonable(await build_export_preflight_payload(db, str(project_id)))
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


async def execute_generate_draft(db: AsyncSession, run_id: uuid.UUID) -> BidAgentRun:
    """Run full Bid Agent orchestration synchronously."""
    run = await get_run(db, run_id)
    if not run:
        raise ValueError("BidAgentRun not found")

    run.status = BidAgentRunStatus.running
    run.progress = 1
    await db.flush()

    steps = await list_steps(db, run.id)
    pipeline_stats: dict[str, Any] = {}
    try:
        for index, step in enumerate(steps, start=1):
            await _start_step(step)
            await db.flush()

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
                summary = await response_matrix_service.rebuild_from_project(db, run.project_id)
                await _complete_step(step, "响应矩阵已重建", {"response_matrix_summary": _jsonable(summary)})
            elif step.step_key == "generate_chapter_contents":
                pipeline_stats = await generate_chapter_contents(db, run.project_id, run.created_by)
                await _complete_step(step, "章节正文生成完成", pipeline_stats)
            elif step.step_key == "response_matrix_preflight":
                preflight = await response_matrix_service.preflight(db, run.project_id)
                await _complete_step(step, "响应矩阵检查完成", {"preflight": _jsonable(preflight)})
            elif step.step_key == "export_preflight":
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

            run.progress = round(index / len(steps) * 100)
            await db.flush()

        quality_report = await build_quality_report(db, run.project_id, pipeline_stats)
        run.result_json = {"quality_report": quality_report}
        run.summary = "一键草稿编排完成" if quality_report.get("ready") else "一键草稿编排完成，但存在导出/响应矩阵阻断项"
        if run.goal == "fix_risks":
            run.summary = "风险检查完成"
        run.status = BidAgentRunStatus.completed
        run.progress = 100
    except Exception as exc:  # pragma: no cover - defensive failure path
        run.status = BidAgentRunStatus.failed
        run.error_message = str(exc)
        for step in steps:
            if step.status == BidAgentStepStatus.running:
                step.status = BidAgentStepStatus.failed
                step.error_message = str(exc)
                step.completed_at = datetime.now(timezone.utc)
        raise
    finally:
        await db.commit()
        await db.refresh(run)

    return run
