"""内容相关API路由"""
from typing import Annotated
import uuid

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.schemas import (
    ChapterContentRequest,
    ChapterGenerationResult,
    HallucinationIssueResponse,
    SourceRef,
)
from ..models.user import User
from ..models.disqualification import DisqualificationCheck
from ..models.response_matrix import TenderClause, ResponseMatrixItem
from ..models.evidence import EvidenceRef, EvidenceSourceType
from ..services.openai_service import OpenAIService
from ..services.knowledge_retrieval_service import KnowledgeRetrievalService
from ..services.chart_service import ChartService
from ..services.terminology_service import TerminologyService
from ..services.anti_hallucination_service import AntiHallucinationService
from ..db.database import get_db
from ..utils.sse import sse_response
from ..auth.dependencies import require_editor

import json

router = APIRouter(prefix="/api/content", tags=["内容管理"])


async def _get_disqualification_redlines(
    db: AsyncSession, project_id: uuid.UUID
) -> str:
    """获取项目的废标红线条款文本。"""
    result = await db.execute(
        select(DisqualificationCheck).where(
            DisqualificationCheck.project_id == project_id,
            DisqualificationCheck.severity == "fatal",
        )
    )
    items = result.scalars().all()
    if not items:
        return ""

    lines = []
    for idx, item in enumerate(items, start=1):
        status_mark = "▢ 未检查" if item.status == "unchecked" else (
            "✓ 已通过" if item.status == "passed" else (
                "✗ 未通过" if item.status == "failed" else "N/A"
            )
        )
        lines.append(
            f"{idx}. [{item.category}] {item.requirement}"
            f" — 处罚：废标/否决 — 状态：{status_mark}"
        )

    return "\n".join(lines)


async def _get_response_matrix_context(
    db: AsyncSession,
    project_id: uuid.UUID,
    chapter_id: str | None = None,
    chapter_title: str | None = None,
) -> str:
    """Build prompt context from response-matrix clauses bound to this chapter."""
    conditions = [ResponseMatrixItem.project_id == project_id]
    if chapter_id:
        conditions.append(ResponseMatrixItem.chapter_id == str(chapter_id))
    elif chapter_title:
        conditions.append(ResponseMatrixItem.chapter_title == chapter_title)
    else:
        return ""

    result = await db.execute(
        select(ResponseMatrixItem, TenderClause)
        .join(TenderClause, ResponseMatrixItem.clause_id == TenderClause.id)
        .where(*conditions)
        .order_by(TenderClause.clause_type, TenderClause.created_at)
    )
    rows = result.all()
    if not rows:
        return ""

    lines = ["## 本章节必须响应的招标条款（响应矩阵）"]
    for idx, (item, clause) in enumerate(rows, start=1):
        score = f"；分值：{float(clause.score_value):g}" if clause.score_value is not None else ""
        fatal = "；致命条款/废标风险" if clause.is_fatal else ""
        lines.append(
            f"{idx}. [{clause.clause_type.value}] {clause.title or clause.content[:60]}"
            f"{score}{fatal}\n"
            f"   要求：{clause.content or clause.raw_requirement}\n"
            f"   当前状态：{item.response_status.value}；风险备注：{item.risk_note or '无'}"
        )
    return "\n".join(lines)


def _issue_to_response(issue) -> HallucinationIssueResponse:
    """Convert anti-hallucination dataclass output to API schema."""
    return HallucinationIssueResponse(
        severity=issue.severity,
        category=issue.category,
        text=issue.text,
        reason=issue.reason,
        suggestion=issue.suggestion,
    )


async def _get_response_matrix_source_refs(
    db: AsyncSession,
    project_id: uuid.UUID,
    chapter_id: str | None = None,
    chapter_title: str | None = None,
) -> list[dict]:
    """Build SourceRef-like dicts from tender clauses bound by the response matrix."""
    conditions = [ResponseMatrixItem.project_id == project_id]
    if chapter_id:
        conditions.append(ResponseMatrixItem.chapter_id == str(chapter_id))
    elif chapter_title:
        conditions.append(ResponseMatrixItem.chapter_title == chapter_title)
    else:
        return []

    result = await db.execute(
        select(ResponseMatrixItem, TenderClause)
        .join(TenderClause, ResponseMatrixItem.clause_id == TenderClause.id)
        .where(*conditions)
        .order_by(TenderClause.clause_type, TenderClause.created_at)
    )
    refs: list[dict] = []
    for item, clause in result.all():
        refs.append({
            "ref_id": str(clause.id),
            "source_type": EvidenceSourceType.tender_document.value,
            "source_id": str(clause.id),
            "source_title": clause.title or clause.clause_type.value,
            "location": clause.source_location or (f"page {clause.source_page}" if clause.source_page else "响应矩阵"),
            "quote": clause.content or clause.raw_requirement or item.evidence_summary or "",
            "relation": "响应矩阵绑定的招标条款",
        })
    return refs


def _knowledge_results_to_source_refs(results: list[dict]) -> list[dict]:
    refs: list[dict] = []
    for r in results or []:
        source_id = str(r.get("doc_id") or r.get("id") or r.get("material_id") or "")
        title = str(r.get("title") or r.get("name") or "参考文档")
        quote = str(r.get("content") or r.get("content_preview") or r.get("text") or "")
        if not quote and not title:
            continue
        refs.append({
            "ref_id": source_id,
            "source_type": EvidenceSourceType.knowledge_doc.value,
            "source_id": source_id,
            "source_title": title,
            "location": str(r.get("location") or r.get("source_location") or "知识库检索"),
            "quote": quote,
            "relation": "知识库检索命中的参考资料",
        })
    return refs


async def save_evidence_refs(
    db: AsyncSession,
    project_id: uuid.UUID,
    chapter_id: str | uuid.UUID | None,
    source_refs: list[dict],
) -> list[EvidenceRef]:
    """Persist SourceRef-like dicts as EvidenceRef rows for a generated chapter."""
    if not source_refs:
        return []
    chapter_uuid = None
    if chapter_id:
        try:
            chapter_uuid = chapter_id if isinstance(chapter_id, uuid.UUID) else uuid.UUID(str(chapter_id))
        except (TypeError, ValueError):
            chapter_uuid = None

    rows: list[EvidenceRef] = []
    valid_types = {e.value for e in EvidenceSourceType}
    for ref in source_refs:
        source_type = str(ref.get("source_type") or EvidenceSourceType.manual_input.value)
        if source_type not in valid_types:
            source_type = EvidenceSourceType.manual_input.value
        row = EvidenceRef(
            project_id=project_id,
            chapter_id=chapter_uuid,
            source_type=EvidenceSourceType(source_type),
            source_id=str(ref.get("source_id") or ref.get("ref_id") or ""),
            source_title=str(ref.get("source_title") or ref.get("title") or ""),
            source_location=str(ref.get("location") or ref.get("source_location") or ""),
            quote=str(ref.get("quote") or ""),
            relation=str(ref.get("relation") or ""),
            metadata_json={"ref_id": str(ref.get("ref_id") or "")},
        )
        db.add(row)
        rows.append(row)
    await db.commit()
    return rows


def _source_ref_schema(ref: dict) -> SourceRef:
    return SourceRef(
        ref_id=str(ref.get("ref_id") or ref.get("source_id") or ""),
        source_type=str(ref.get("source_type") or ""),
        source_id=str(ref.get("source_id")) if ref.get("source_id") is not None else None,
        location=str(ref.get("location") or ref.get("source_location") or ""),
        quote=str(ref.get("quote") or ""),
        relation=str(ref.get("relation") or ""),
    )


async def _get_terminology_guide(
    project_title: str = "", project_description: str = ""
) -> str:
    """检测行业并获取术语使用指南。"""
    industry = TerminologyService.detect_industry(
        project_title=project_title,
        project_description=project_description,
    )
    if not industry:
        return ""
    return TerminologyService.get_terminology_guide(industry)


def _build_material_suggestions_block(
    materials: list,
) -> str:
    """构建素材建议 Markdown 块

    Material suggestions are wrapped in <!-- MATERIAL_SUGGESTIONS -->
    so the Word exporter can optionally handle them specially.
    """
    if not materials:
        return ""

    lines = [
        "\n\n---\n\n",
        "<!-- MATERIAL_SUGGESTIONS -->\n",
        "## 📎 建议引用素材\n\n",
        "| 序号 | 素材名称 | 类型 | 建议插入位置 |\n",
        "|------|---------|------|-------------|\n",
    ]

    for i, mat in enumerate(materials, 1):
        name = mat.get("name", "未命名素材")
        mapped = mat.get("mapped_category", "其他")
        placement = mat.get("suggested_placement", "章节末尾")
        lines.append(f"| {i} | {name} | {mapped} | {placement} |\n")

    return "".join(lines)


async def _generate_charts_for_content(
    chapter_title: str,
    chapter_content: str,
    openai_service,
) -> str:
    """为章节内容生成图表并返回 Mermaid 代码块字符串"""
    try:
        chart_service = ChartService(openai_service=openai_service)
        charts = await chart_service.generate_charts_for_content(
            chapter_title=chapter_title,
            chapter_content=chapter_content,
        )
        if charts:
            blocks = [c["markdown_block"] for c in charts]
            return "".join(blocks)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"图表生成跳过: {e}")
    return ""


async def _retrieve_materials_for_content(
    chapter_title: str,
    chapter_content: str,
    db: AsyncSession,
    current_user=None,
) -> list:
    """检索章节匹配的素材"""
    try:
        retrieval_service = KnowledgeRetrievalService(db)
        materials = await retrieval_service.retrieve_materials_for_chapter(
            chapter_title=chapter_title,
            chapter_content=chapter_content,
            top_k=3,
            user_id=current_user.id if current_user else None,
        )
        return materials
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"素材检索跳过: {e}")
        return []


@router.post("/generate-chapter")
async def generate_chapter_content(
    request: ChapterContentRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """为单个章节生成内容"""
    try:
        # 创建OpenAI服务实例，从数据库加载配置
        openai_service = OpenAIService(db=db)
        if request.provider_config_id:
            configured = await openai_service.use_config_by_id(request.provider_config_id)
            if not configured:
                raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
        else:
            await openai_service._ensure_initialized()

        if not openai_service.api_key:
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        if request.model_name:
            openai_service.set_model(request.model_name)

        # 项目级上下文：废标红线 + 术语库
        disqualification_redlines = ""
        terminology_guide = ""
        response_matrix_context = ""
        if request.project_id:
            try:
                project_uuid = uuid.UUID(request.project_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的项目ID格式")
            chapter_title = str(request.chapter.get("title") or request.chapter.get("id") or "")
            response_matrix_context = await _get_response_matrix_context(
                db,
                project_uuid,
                chapter_id=str(request.chapter.get("id") or ""),
                chapter_title=chapter_title,
            )
            disqualification_redlines = await _get_disqualification_redlines(db, project_uuid)
            terminology_guide = await _get_terminology_guide(
                project_title=str(request.chapter.get("title", "")),
                project_description=request.project_overview or "",
            )

        # 生成单章节内容
        content = ""
        if request.rewrite_suggestions:
            content = await openai_service.rewrite_chapter_with_suggestions(
                chapter_title=str(request.chapter.get("title") or request.chapter.get("id") or "未命名章节"),
                chapter_content=request.source_chapter_content or "",
                suggestions=request.rewrite_suggestions,
            )
        else:
            # 检索知识库
            knowledge_context = ""
            if request.use_knowledge and db:
                try:
                    retrieval_service = KnowledgeRetrievalService(db)
                    chapter_title = str(request.chapter.get("title") or request.chapter.get("id") or "")
                    results = await retrieval_service.retrieve_for_chapter(
                        chapter_title=chapter_title,
                        chapter_description=str(request.chapter.get("description", "")),
                        project_overview=(request.project_overview or "")[:500],
                        user_id=current_user.id if current_user else None,
                        top_k=5,
                    )
                    if results:
                        knowledge_context = "\n\n".join(
                            f"【{r.get('title', '参考文档')}】\n{r.get('content') or r.get('content_preview', '')}"
                            for r in results
                            if r.get("content") or r.get("content_preview")
                        )
                except Exception:
                    pass  # 知识库检索失败不影响正常生成

            async for chunk in openai_service._generate_chapter_content(
                chapter=request.chapter,
                parent_chapters=request.parent_chapters,
                sibling_chapters=request.sibling_chapters,
                project_overview=request.project_overview,
                project_response_matrix=openai_service._build_project_response_matrix(
                    request.rating_response_checklist
                ),
                knowledge_context="\n\n".join(part for part in [knowledge_context, response_matrix_context] if part),
                disqualification_redlines=disqualification_redlines,
                terminology_guide=terminology_guide,
            ):
                content += chunk

        # === 素材/证据自动关联 ===
        chapter_title_for_enrich = str(request.chapter.get("title") or request.chapter.get("id") or "")
        if content and db:
            materials = await _retrieve_materials_for_content(
                chapter_title=chapter_title_for_enrich,
                chapter_content=content,
                db=db,
                current_user=current_user,
            )
            if materials:
                content += _build_material_suggestions_block(materials)

        # === 图表自动生成 ===
        if content:
            charts_block = await _generate_charts_for_content(
                chapter_title=chapter_title_for_enrich,
                chapter_content=content,
                openai_service=openai_service,
            )
            if charts_block:
                content += "\n\n" + charts_block

        return {"success": True, "content": content}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"章节内容生成失败: {e}") from e


@router.post("/generate-chapter-v2", response_model=ChapterGenerationResult)
async def generate_chapter_content_v2(
    request: ChapterContentRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """生成章节内容，并返回证据链与反幻觉检查结果。"""
    try:
        openai_service = OpenAIService(db=db)
        if request.provider_config_id:
            configured = await openai_service.use_config_by_id(request.provider_config_id)
            if not configured:
                raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
        else:
            await openai_service._ensure_initialized()

        if not openai_service.api_key:
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")
        if request.model_name:
            openai_service.set_model(request.model_name)

        project_uuid: uuid.UUID | None = None
        chapter_id = str(request.chapter.get("id") or "")
        chapter_title = str(request.chapter.get("title") or chapter_id or "")
        response_matrix_context = ""
        disqualification_redlines = ""
        terminology_guide = ""
        source_ref_dicts: list[dict] = []

        if request.project_id:
            try:
                project_uuid = uuid.UUID(request.project_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的项目ID格式")
            response_matrix_context = await _get_response_matrix_context(
                db,
                project_uuid,
                chapter_id=chapter_id,
                chapter_title=chapter_title,
            )
            source_ref_dicts.extend(await _get_response_matrix_source_refs(
                db,
                project_uuid,
                chapter_id=chapter_id,
                chapter_title=chapter_title,
            ))
            disqualification_redlines = await _get_disqualification_redlines(db, project_uuid)
            terminology_guide = await _get_terminology_guide(
                project_title=chapter_title,
                project_description=request.project_overview or "",
            )

        content = ""
        if request.rewrite_suggestions:
            content = await openai_service.rewrite_chapter_with_suggestions(
                chapter_title=chapter_title or "未命名章节",
                chapter_content=request.source_chapter_content or "",
                suggestions=request.rewrite_suggestions,
            )
        else:
            knowledge_context = ""
            if request.use_knowledge and db:
                try:
                    retrieval_service = KnowledgeRetrievalService(db)
                    results = await retrieval_service.retrieve_for_chapter(
                        chapter_title=chapter_title,
                        chapter_description=str(request.chapter.get("description", "")),
                        project_overview=(request.project_overview or "")[:500],
                        user_id=current_user.id if current_user else None,
                        top_k=5,
                    )
                    source_ref_dicts.extend(_knowledge_results_to_source_refs(results))
                    if results:
                        knowledge_context = "\n\n".join(
                            f"【{r.get('title', '参考文档')}】\n{r.get('content') or r.get('content_preview', '')}"
                            for r in results
                            if r.get("content") or r.get("content_preview")
                        )
                except Exception:
                    pass

            async for chunk in openai_service._generate_chapter_content(
                chapter=request.chapter,
                parent_chapters=request.parent_chapters,
                sibling_chapters=request.sibling_chapters,
                project_overview=request.project_overview,
                project_response_matrix=openai_service._build_project_response_matrix(
                    request.rating_response_checklist
                ),
                knowledge_context="\n\n".join(part for part in [knowledge_context, response_matrix_context] if part),
                disqualification_redlines=disqualification_redlines,
                terminology_guide=terminology_guide,
            ):
                content += chunk

        if project_uuid:
            await save_evidence_refs(db, project_uuid, chapter_id, source_ref_dicts)

        issues = AntiHallucinationService().scan_text(content, source_ref_dicts)
        return ChapterGenerationResult(
            content=content,
            source_refs=[_source_ref_schema(ref) for ref in source_ref_dicts],
            hallucination_issues=[_issue_to_response(issue) for issue in issues],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"章节内容生成失败: {e}") from e


@router.post("/generate-chapter-stream")
async def generate_chapter_content_stream(
    request: ChapterContentRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """流式为单个章节生成内容"""
    try:
        # 创建OpenAI服务实例，从数据库加载配置
        openai_service = OpenAIService(db=db)
        if request.provider_config_id:
            configured = await openai_service.use_config_by_id(request.provider_config_id)
            if not configured:
                raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
        else:
            await openai_service._ensure_initialized()

        if not openai_service.api_key:
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        if request.model_name:
            openai_service.set_model(request.model_name)

        async def generate():
            try:
                # 发送开始信号
                yield f"data: {json.dumps({'status': 'started', 'message': '开始生成章节内容...'}, ensure_ascii=False)}\n\n"

                # 项目级上下文：废标红线 + 术语库
                disqualification_redlines = ""
                terminology_guide = ""
                response_matrix_context = ""
                if request.project_id:
                    try:
                        project_uuid = uuid.UUID(request.project_id)
                    except ValueError:
                        yield f"data: {json.dumps({'status': 'error', 'message': '无效的项目ID格式'}, ensure_ascii=False)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    chapter_title = str(request.chapter.get("title") or request.chapter.get("id") or "")
                    response_matrix_context = await _get_response_matrix_context(
                        db,
                        project_uuid,
                        chapter_id=str(request.chapter.get("id") or ""),
                        chapter_title=chapter_title,
                    )
                    disqualification_redlines = await _get_disqualification_redlines(db, project_uuid)
                    terminology_guide = await _get_terminology_guide(
                        project_title=str(request.chapter.get("title", "")),
                        project_description=request.project_overview or "",
                    )

                # 流式生成章节内容
                full_content = ""
                if request.rewrite_suggestions:
                    async for chunk in openai_service.rewrite_chapter_with_suggestions_stream(
                        chapter_title=str(request.chapter.get("title") or request.chapter.get("id") or "未命名章节"),
                        chapter_content=request.source_chapter_content or "",
                        suggestions=request.rewrite_suggestions,
                    ):
                        full_content += chunk
                        yield f"data: {json.dumps({'status': 'streaming', 'content': chunk, 'full_content': full_content}, ensure_ascii=False)}\n\n"
                else:
                    # 检索知识库
                    knowledge_context = ""
                    if request.use_knowledge and db:
                        try:
                            retrieval_service = KnowledgeRetrievalService(db)
                            chapter_title = str(request.chapter.get("title") or request.chapter.get("id") or "")
                            results = await retrieval_service.retrieve_for_chapter(
                                chapter_title=chapter_title,
                                chapter_description=str(request.chapter.get("description", "")),
                                project_overview=(request.project_overview or "")[:500],
                                user_id=current_user.id if current_user else None,
                                top_k=5,
                            )
                            if results:
                                knowledge_context = "\n\n".join(
                                    f"【{r.get('title', '参考文档')}】\n{r.get('content') or r.get('content_preview', '')}"
                                    for r in results
                                    if r.get("content") or r.get("content_preview")
                                )
                                yield f"data: {json.dumps({'status': 'knowledge_retrieved', 'count': len(results)}, ensure_ascii=False)}\n\n"
                        except Exception:
                            pass  # 知识库检索失败不影响正常生成

                    async for chunk in openai_service._generate_chapter_content(
                        chapter=request.chapter,
                        parent_chapters=request.parent_chapters,
                        sibling_chapters=request.sibling_chapters,
                        project_overview=request.project_overview,
                        project_response_matrix=openai_service._build_project_response_matrix(
                            request.rating_response_checklist
                        ),
                        knowledge_context="\n\n".join(part for part in [knowledge_context, response_matrix_context] if part),
                        disqualification_redlines=disqualification_redlines,
                        terminology_guide=terminology_guide,
                    ):
                        full_content += chunk
                        # 实时发送内容片段
                        yield f"data: {json.dumps({'status': 'streaming', 'content': chunk, 'full_content': full_content}, ensure_ascii=False)}\n\n"

                # 发送完成信号
                # === 素材/证据自动关联 ===
                chapter_title_for_enrich = str(request.chapter.get("title") or request.chapter.get("id") or "")
                if full_content and db:
                    materials = await _retrieve_materials_for_content(
                        chapter_title=chapter_title_for_enrich,
                        chapter_content=full_content,
                        db=db,
                        current_user=current_user,
                    )
                    if materials:
                        material_block = _build_material_suggestions_block(materials)
                        full_content += material_block
                        yield f"data: {json.dumps({'status': 'material_suggestions', 'block': material_block}, ensure_ascii=False)}\n\n"

                    # === 图表自动生成 ===
                    charts_block = await _generate_charts_for_content(
                        chapter_title=chapter_title_for_enrich,
                        chapter_content=full_content,
                        openai_service=openai_service,
                    )
                    if charts_block:
                        full_content += "\n\n" + charts_block
                        yield f"data: {json.dumps({'status': 'charts_generated', 'block': charts_block}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps({'status': 'completed', 'content': full_content}, ensure_ascii=False)}\n\n"

            except Exception as e:
                # 发送错误信息
                yield f"data: {json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

            # 发送结束信号
            yield "data: [DONE]\n\n"

        return sse_response(generate())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"章节内容生成失败: {e}") from e
