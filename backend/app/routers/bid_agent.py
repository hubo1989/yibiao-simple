"""Bid Agent Orchestrator API routes."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import require_editor
from ..db.database import get_db
from ..models.bid_agent import BidAgentRun, BidAgentStep
from ..models.project import Project, project_members
from ..models.user import User
from ..schemas.bid_agent import BidAgentQualityReport, BidAgentRunResponse, BidAgentStepResponse
from ..services import bid_agent_service

router = APIRouter(prefix="/api/bid-agent", tags=["Bid Agent"])


async def _verify_project_access(project_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(
        select(project_members.c.role).where(
            and_(project_members.c.project_id == project_id, project_members.c.user_id == user_id)
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="项目不存在或您没有访问权限")
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


def _run_response(run: BidAgentRun) -> BidAgentRunResponse:
    return BidAgentRunResponse(
        id=str(run.id),
        project_id=str(run.project_id),
        created_by=str(run.created_by) if run.created_by else None,
        goal=run.goal,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        progress=run.progress,
        summary=run.summary,
        error_message=run.error_message,
        result_json=run.result_json or {},
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _step_response(step: BidAgentStep) -> BidAgentStepResponse:
    return BidAgentStepResponse(
        id=str(step.id),
        run_id=str(step.run_id),
        step_key=step.step_key,
        step_name=step.step_name,
        status=step.status.value if hasattr(step.status, "value") else str(step.status),
        order_index=step.order_index,
        progress=step.progress,
        summary=step.summary,
        error_message=step.error_message,
        result_json=step.result_json or {},
        started_at=step.started_at,
        completed_at=step.completed_at,
    )


async def _verify_run_access(run_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> BidAgentRun:
    run = await bid_agent_service.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Bid Agent 运行记录不存在")
    await _verify_project_access(run.project_id, user_id, db)
    return run


@router.post("/{project_id}/generate-draft", response_model=BidAgentRunResponse)
async def generate_draft(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> BidAgentRunResponse:
    """Create and synchronously execute a deterministic draft-generation MVP run."""
    await _verify_project_access(project_id, current_user.id, db)
    run = await bid_agent_service.create_run(db, project_id, current_user.id, goal="generate_draft")
    run = await bid_agent_service.execute_generate_draft(db, run.id)
    return _run_response(run)


@router.post("/{project_id}/fix-risks", response_model=BidAgentRunResponse)
async def fix_risks(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> BidAgentRunResponse:
    """Create and synchronously execute quality checks for risk-fix workflow."""
    await _verify_project_access(project_id, current_user.id, db)
    run = await bid_agent_service.create_run(db, project_id, current_user.id, goal="fix_risks")
    run = await bid_agent_service.execute_generate_draft(db, run.id)
    return _run_response(run)


@router.get("/runs/{run_id}", response_model=BidAgentRunResponse)
async def get_run(
    run_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> BidAgentRunResponse:
    run = await _verify_run_access(run_id, current_user.id, db)
    return _run_response(run)


@router.get("/runs/{run_id}/steps", response_model=list[BidAgentStepResponse])
async def get_run_steps(
    run_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> list[BidAgentStepResponse]:
    await _verify_run_access(run_id, current_user.id, db)
    steps = await bid_agent_service.list_steps(db, run_id)
    return [_step_response(step) for step in steps]


@router.get("/{project_id}/quality-report", response_model=BidAgentQualityReport)
async def quality_report(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
) -> BidAgentQualityReport:
    await _verify_project_access(project_id, current_user.id, db)
    return BidAgentQualityReport(**await bid_agent_service.build_quality_report(db, project_id))
