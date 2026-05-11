"""增强导出 API 路由 - Word 格式规范导出"""
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote

from ..auth.dependencies import require_editor
from ..db.database import get_db
from ..models.chapter import Chapter
from ..models.evidence import EvidenceRef
from ..models.user import User
from ..services.anti_hallucination_service import AntiHallucinationService
from ..services.word_export_service import WordExportService, WordFormatConfig

import io

router = APIRouter(prefix="/api/export", tags=["增强导出"])


class ExportChapterItem(BaseModel):
    """导出章节项"""
    title: str = Field(..., description="章节标题")
    content: str = Field("", description="章节 Markdown 内容")


class WordExportRequest(BaseModel):
    """增强 Word 导出请求"""
    project_name: str = Field(..., description="项目名称")
    project_overview: str = Field("", description="项目概述")
    chapters: List[ExportChapterItem] = Field(..., description="章节列表")
    template_id: Optional[str] = Field(None, description="可选的导出格式模板ID")


def _issue_payload(issue) -> dict:
    return {
        "severity": issue.severity,
        "category": issue.category,
        "text": issue.text,
        "reason": issue.reason,
        "suggestion": issue.suggestion,
    }


async def build_export_preflight_payload(db: AsyncSession, project_id: str) -> dict:
    """Scan project chapters against EvidenceRef rows before export."""
    try:
        import uuid
        project_uuid = uuid.UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="无效的项目ID格式") from exc

    chapter_result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_uuid).order_by(Chapter.order_index, Chapter.chapter_number)
    )
    chapters = chapter_result.scalars().all()
    evidence_result = await db.execute(select(EvidenceRef).where(EvidenceRef.project_id == project_uuid))
    evidence_refs = [
        {
            "source_type": ref.source_type.value if hasattr(ref.source_type, "value") else str(ref.source_type),
            "source_title": ref.source_title,
            "quote": ref.quote,
            "source_id": ref.source_id,
            "location": ref.source_location,
        }
        for ref in evidence_result.scalars().all()
    ]

    scanner = AntiHallucinationService()
    blockers: list[dict] = []
    for chapter in chapters:
        if not chapter.content:
            continue
        critical = [
            issue for issue in scanner.scan_text(chapter.content, evidence_refs)
            if issue.severity == "critical"
        ]
        if critical:
            blockers.append({
                "chapter_id": str(chapter.id),
                "chapter_number": chapter.chapter_number,
                "chapter_title": chapter.title,
                "issues": [_issue_payload(issue) for issue in critical],
            })

    return {
        "project_id": str(project_uuid),
        "block_export": bool(blockers),
        "blockers": blockers,
        "summary": {
            "chapter_count": len(chapters),
            "evidence_ref_count": len(evidence_refs),
            "blocker_count": sum(len(item["issues"]) for item in blockers),
        },
    }


@router.get("/preflight/{project_id}")
async def export_preflight(
    project_id: str,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """Non-breaking export quality gate: report anti-hallucination blockers."""
    return await build_export_preflight_payload(db, project_id)


@router.post("/word")
async def export_word(
    request: WordExportRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """导出规范 Word 文档

    从 Markdown 内容生成符合 GB/T 9704 格式规范的 Word 文档。
    支持标题/正文/表格/Mermaid 图表的自动排版。
    """
    try:
        export_service = WordExportService()

        # 加载格式配置
        format_config = await export_service.load_format_config(
            db=db,
            template_id=request.template_id,
        )

        # 导出
        buffer: io.BytesIO = await export_service.export_to_docx(
            project_name=request.project_name,
            chapters=[
                {"title": ch.title, "content": ch.content}
                for ch in request.chapters
            ],
            project_overview=request.project_overview,
            format_config=format_config,
        )

        # 生成文件名
        safe_name = "".join(
            c for c in request.project_name
            if c.isalnum() or c in ('_', '-', ' ', '.', '（', '）')
        )[:50] or "投标文件"
        filename = f"{safe_name}.docx"
        encoded_filename = quote(filename)

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Word 导出失败: {str(e)}",
        ) from e
