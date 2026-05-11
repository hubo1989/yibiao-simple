"""响应矩阵服务层 — 从 scoring_criteria / disqualification_checks 同步统一条款，自动绑定章节"""
from __future__ import annotations

import logging
import uuid
from typing import Sequence

from sqlalchemy import delete, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.response_matrix import (
    ClauseType,
    ResponseMatrixItem,
    ResponseStatus,
    TenderClause,
)
from ..models.scoring import ScoringCriteria
from ..models.disqualification import DisqualificationCheck
from ..models.chapter import Chapter
from ..models.project import Project
from ..schemas.response_matrix import ResponseMatrixSummary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clause_to_dict(tc: TenderClause) -> dict:
    return {
        "id": str(tc.id),
        "project_id": str(tc.project_id),
        "clause_type": tc.clause_type.value,
        "title": tc.title,
        "content": tc.content,
        "source_page": tc.source_page,
        "source_location": tc.source_location,
        "score_value": float(tc.score_value) if tc.score_value is not None else None,
        "is_fatal": tc.is_fatal,
    }


def _item_to_dict(item: ResponseMatrixItem) -> dict:
    return {
        "id": str(item.id),
        "project_id": str(item.project_id),
        "clause_id": str(item.clause_id),
        "chapter_id": item.chapter_id,
        "chapter_title": item.chapter_title,
        "response_status": item.response_status.value,
        "response_summary": item.response_summary,
        "evidence_summary": item.evidence_summary,
        "risk_note": item.risk_note,
        "confidence": item.confidence,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Core service functions
# ---------------------------------------------------------------------------

async def extract_clauses_from_analysis(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> list[TenderClause]:
    """Parse existing scoring_criteria + disqualification_checks into unified TenderClause rows."""
    created: list[TenderClause] = []

    # -- from scoring_criteria --
    sc_result = await db.execute(
        select(ScoringCriteria).where(ScoringCriteria.project_id == project_id)
    )
    for sc in sc_result.scalars().all():
        tc = TenderClause(
            project_id=project_id,
            clause_type=ClauseType.scoring,
            title=sc.item or "",
            content=sc.scoring_rule or "",
            raw_requirement=sc.source_text or "",
            score_value=sc.max_score,
            is_fatal=False,
            metadata_json={
                "source_item_id": sc.item_id,
                "category": sc.category,
                "keywords": sc.keywords or [],
                "bound_chapter_id": str(sc.bound_chapter_id) if sc.bound_chapter_id else None,
            },
        )
        db.add(tc)
        created.append(tc)

    # -- from disqualification_checks --
    dq_result = await db.execute(
        select(DisqualificationCheck).where(
            DisqualificationCheck.project_id == project_id
        )
    )
    for dq in dq_result.scalars().all():
        clause_type = ClauseType.disqualification
        if dq.check_type == "format":
            clause_type = ClauseType.format
        elif dq.category in ("资质要求",):
            clause_type = ClauseType.qualification

        tc = TenderClause(
            project_id=project_id,
            clause_type=clause_type,
            title=dq.requirement[:255] if dq.requirement else "",
            content=dq.requirement or "",
            raw_requirement=dq.source_text or "",
            is_fatal=dq.severity == "fatal",
            metadata_json={
                "source_item_id": dq.item_id,
                "category": dq.category,
                "check_type": dq.check_type,
                "original_status": dq.status,
            },
        )
        db.add(tc)
        created.append(tc)

    if not created:
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()
        requirements = (project.tech_requirements or project.file_content or "") if project else ""
        lines = [line.strip(" -•\t") for line in requirements.splitlines() if line.strip()]
        candidate_lines = [line for line in lines if any(key in line for key in ("评分", "要求", "必须", "需", "应", "不得", "否决", "废标"))]
        for index, line in enumerate((candidate_lines or lines)[:20], start=1):
            clause_type = ClauseType.disqualification if any(key in line for key in ("废标", "否决", "不得")) else ClauseType.technical
            tc = TenderClause(
                project_id=project_id,
                clause_type=clause_type,
                title=line[:120],
                content=line,
                raw_requirement=line,
                is_fatal=clause_type == ClauseType.disqualification,
                metadata_json={"source": "project_tech_requirements_fallback", "index": index},
            )
            db.add(tc)
            created.append(tc)

    await db.flush()
    return created


async def auto_bind_to_chapters(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> int:
    """Keyword-heuristic binding of unbound TenderClauses to Chapters.

    Uses title/content keyword overlap between clause & chapter to find the
    best matching chapter.  Returns the number of newly bound items.
    """
    # Load unbound clauses (those with no matrix item yet)
    clause_result = await db.execute(
        select(TenderClause).where(
            and_(
                TenderClause.project_id == project_id,
            )
        )
    )
    clauses = clause_result.scalars().all()
    if not clauses:
        return 0

    # Load existing matrix items for this project to know which clauses are already bound
    existing_result = await db.execute(
        select(ResponseMatrixItem.clause_id).where(
            ResponseMatrixItem.project_id == project_id
        )
    )
    bound_clause_ids: set[uuid.UUID] = {row[0] for row in existing_result.all()}

    # Load chapters
    ch_result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id)
    )
    chapters = ch_result.scalars().all()
    if not chapters:
        return 0

    bound_count = 0
    for tc in clauses:
        if tc.id in bound_clause_ids:
            continue

        title_lower = tc.title.lower()
        content_lower = tc.content.lower()
        keywords: list[str] = tc.metadata_json.get("keywords", []) if tc.metadata_json else []

        best_chapter = None
        best_score = 0

        for ch in chapters:
            ch_title = ch.title.lower()
            ch_content = (ch.content or "").lower()
            ch_role = (ch.chapter_role or "").lower()

            score = 0
            if title_lower and title_lower in ch_title:
                score += 5
            for kw in keywords:
                kw_l = kw.lower()
                if kw_l in ch_title:
                    score += 3
                elif kw_l in ch_role:
                    score += 2
                elif kw_l in ch_content:
                    score += 1
            # Also match content keywords against chapter
            if content_lower:
                for word in content_lower.split()[:20]:
                    if len(word) >= 2 and word in ch_title:
                        score += 1

            if score > best_score:
                best_score = score
                best_chapter = ch

        if best_chapter and best_score >= 2:
            item = ResponseMatrixItem(
                project_id=project_id,
                clause_id=tc.id,
                chapter_id=str(best_chapter.id),
                chapter_title=best_chapter.title,
                # Auto-binding only identifies the likely chapter. Actual coverage is
                # upgraded after generated content is checked against the clause.
                response_status=ResponseStatus.partial if tc.clause_type == ClauseType.scoring else ResponseStatus.not_started,
                confidence="high" if best_score >= 6 else "medium" if best_score >= 4 else "low",
            )
            db.add(item)
            bound_count += 1

    await db.flush()
    return bound_count


async def update_item_status(
    db: AsyncSession,
    item_id: uuid.UUID,
    status: str | None = None,
    summary: str | None = None,
    evidence: str | None = None,
    risk_note: str | None = None,
    confidence: str | None = None,
) -> ResponseMatrixItem | None:
    """Update a single ResponseMatrixItem's fields."""
    result = await db.execute(
        select(ResponseMatrixItem).where(ResponseMatrixItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        return None

    if status is not None:
        item.response_status = ResponseStatus(status)
    if summary is not None:
        item.response_summary = summary
    if evidence is not None:
        item.evidence_summary = evidence
    if risk_note is not None:
        item.risk_note = risk_note
    if confidence is not None:
        item.confidence = confidence

    await db.flush()
    await db.refresh(item)
    return item


async def summarize(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> ResponseMatrixSummary:
    """Compute summary statistics for the response matrix."""
    # Load all clauses
    tc_result = await db.execute(
        select(TenderClause).where(TenderClause.project_id == project_id)
    )
    clauses = tc_result.scalars().all()
    total_clauses = len(clauses)
    if total_clauses == 0:
        return ResponseMatrixSummary()

    # Load all matrix items
    item_result = await db.execute(
        select(ResponseMatrixItem).where(ResponseMatrixItem.project_id == project_id)
    )
    items = item_result.scalars().all()

    # Build lookup: clause_id -> item
    item_map: dict[uuid.UUID, ResponseMatrixItem] = {it.clause_id: it for it in items}

    covered = 0
    partial = 0
    missing = 0
    risk = 0
    fatal_missing = 0
    scoring_total_score = 0.0
    scoring_covered_score = 0.0

    for tc in clauses:
        item = item_map.get(tc.id)
        if item is None:
            missing += 1
            if tc.is_fatal:
                fatal_missing += 1
            if tc.clause_type == ClauseType.scoring:
                val = float(tc.score_value) if tc.score_value else 0
                scoring_total_score += val
        else:
            st = item.response_status
            if st == ResponseStatus.covered:
                covered += 1
                if tc.clause_type == ClauseType.scoring:
                    val = float(tc.score_value) if tc.score_value else 0
                    scoring_total_score += val
                    scoring_covered_score += val
            elif st == ResponseStatus.partial:
                partial += 1
                if tc.clause_type == ClauseType.scoring:
                    val = float(tc.score_value) if tc.score_value else 0
                    scoring_total_score += val
                    scoring_covered_score += val * 0.5
            elif st == ResponseStatus.risk:
                risk += 1
                if tc.clause_type == ClauseType.scoring:
                    val = float(tc.score_value) if tc.score_value else 0
                    scoring_total_score += val
            elif st == ResponseStatus.missing:
                missing += 1
                if tc.is_fatal:
                    fatal_missing += 1
                if tc.clause_type == ClauseType.scoring:
                    val = float(tc.score_value) if tc.score_value else 0
                    scoring_total_score += val
            elif st == ResponseStatus.not_applicable:
                pass  # skip
            else:
                # not_started counts as missing
                missing += 1
                if tc.is_fatal:
                    fatal_missing += 1
                if tc.clause_type == ClauseType.scoring:
                    val = float(tc.score_value) if tc.score_value else 0
                    scoring_total_score += val

    scoring_coverage_rate = (
        (scoring_covered_score / scoring_total_score * 100)
        if scoring_total_score > 0
        else 0.0
    )

    if fatal_missing > 0:
        overall_status = "risk"
    elif missing == 0 and risk == 0:
        overall_status = "ready"
    else:
        overall_status = "not_ready"

    return ResponseMatrixSummary(
        total_clauses=total_clauses,
        covered=covered,
        partial=partial,
        missing=missing,
        risk=risk,
        fatal_missing=fatal_missing,
        scoring_coverage_rate=round(scoring_coverage_rate, 2),
        overall_status=overall_status,
    )


async def rebuild(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> ResponseMatrixSummary:
    """Delete existing clauses+items, re-extract from scoring/disqualification data, auto-bind."""
    # Delete old data
    await db.execute(
        delete(ResponseMatrixItem).where(
            ResponseMatrixItem.project_id == project_id
        )
    )
    await db.execute(
        delete(TenderClause).where(TenderClause.project_id == project_id)
    )
    await db.flush()

    # Re-extract
    await extract_clauses_from_analysis(db, project_id)

    # Auto-bind
    await auto_bind_to_chapters(db, project_id)

    await db.commit()

    # Return summary
    return await summarize(db, project_id)


async def rebuild_from_project(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> ResponseMatrixSummary:
    """Compatibility entrypoint used by project workflows to refresh the matrix."""
    return await rebuild(db, project_id)


async def preflight(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> dict:
    """Return export readiness summary and human-readable blockers."""
    summary = await summarize(db, project_id)
    blockers: list[str] = []
    if summary.total_clauses == 0:
        blockers.append("未提取到任何招标响应条款，请先完成评分项/废标项/技术要求提取")
    else:
        if summary.fatal_missing > 0:
            blockers.append(f"存在 {summary.fatal_missing} 项致命条款未覆盖")
        if summary.missing > 0:
            blockers.append(f"存在 {summary.missing} 项条款缺失或未开始响应")
        if summary.risk > 0:
            blockers.append(f"存在 {summary.risk} 项风险响应")

    return {
        "ready": not blockers,
        "summary": summary,
        "blockers": blockers,
    }
