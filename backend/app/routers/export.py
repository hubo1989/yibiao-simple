"""增强导出 API 路由 - Word 格式规范导出"""
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote

from ..auth.dependencies import require_editor
from ..db.database import get_db
from ..models.user import User
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
