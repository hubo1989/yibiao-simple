"""Bid Agent deterministic orchestration service."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.bid_agent import BidAgentRun, BidAgentRunStatus, BidAgentStep, BidAgentStepStatus
from . import response_matrix_service
from ..routers.export import build_export_preflight_payload


GENERATE_DRAFT_STEPS: list[tuple[str, str]] = [
    ("rebuild_response_matrix", "重建响应矩阵"),
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


async def build_quality_report(db: AsyncSession, project_id: uuid.UUID) -> dict[str, Any]:
    matrix_preflight = _jsonable(await response_matrix_service.preflight(db, project_id))
    export_preflight = _jsonable(await build_export_preflight_payload(db, str(project_id)))
    blockers = list(matrix_preflight.get("blockers") or [])
    blockers.extend(
        f"{item.get('chapter_title', '章节')} 存在 {len(item.get('issues') or [])} 项导出阻断问题"
        for item in export_preflight.get("blockers") or []
    )
    return {
        "project_id": str(project_id),
        "response_matrix_preflight": matrix_preflight,
        "export_preflight": export_preflight,
        "ready": bool(matrix_preflight.get("ready")) and not bool(export_preflight.get("block_export")),
        "blockers": blockers,
    }


async def execute_generate_draft(db: AsyncSession, run_id: uuid.UUID) -> BidAgentRun:
    """Run deterministic MVP orchestration synchronously. Never calls LLM."""
    run = await get_run(db, run_id)
    if not run:
        raise ValueError("BidAgentRun not found")

    run.status = BidAgentRunStatus.running
    run.progress = 1
    await db.flush()

    steps = await list_steps(db, run.id)
    try:
        for index, step in enumerate(steps, start=1):
            await _start_step(step)
            await db.flush()

            if step.step_key == "rebuild_response_matrix":
                summary = await response_matrix_service.rebuild_from_project(db, run.project_id)
                await _complete_step(step, "响应矩阵已重建", {"response_matrix_summary": _jsonable(summary)})
            elif step.step_key == "response_matrix_preflight":
                preflight = await response_matrix_service.preflight(db, run.project_id)
                await _complete_step(step, "响应矩阵检查完成", {"preflight": _jsonable(preflight)})
            elif step.step_key == "export_preflight":
                export_preflight = await build_export_preflight_payload(db, str(run.project_id))
                await _complete_step(step, "导出前检查完成", {"export_preflight": _jsonable(export_preflight)})
            elif step.step_key == "assemble_quality_report":
                report = await build_quality_report(db, run.project_id)
                await _complete_step(step, "质量报告已生成", {"quality_report": report})
            else:
                step.status = BidAgentStepStatus.skipped
                step.progress = 100
                step.summary = "未知步骤，已跳过"
                step.completed_at = datetime.now(timezone.utc)

            run.progress = round(index / len(steps) * 100)
            await db.flush()

        quality_report = await build_quality_report(db, run.project_id)
        run.result_json = {"quality_report": quality_report}
        run.summary = "一键草稿编排完成（MVP：已完成确定性质量检查，未调用大模型生成正文）"
        if run.goal == "fix_risks":
            run.summary = "风险修复检查完成（MVP：已完成确定性质量检查）"
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
