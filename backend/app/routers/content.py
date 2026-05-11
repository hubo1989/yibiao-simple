"""内容相关API路由"""
from typing import Annotated
import uuid

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.schemas import ContentGenerationRequest, ChapterContentRequest
from ..models.user import User
from ..models.disqualification import DisqualificationCheck
from ..services.openai_service import OpenAIService
from ..services.knowledge_retrieval_service import KnowledgeRetrievalService
from ..services.chart_service import ChartService
from ..services.terminology_service import TerminologyService
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
        if request.project_id:
            try:
                project_uuid = uuid.UUID(request.project_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="无效的项目ID格式")
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
                knowledge_context=knowledge_context,
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
                if request.project_id:
                    try:
                        project_uuid = uuid.UUID(request.project_id)
                    except ValueError:
                        yield f"data: {json.dumps({'status': 'error', 'message': '无效的项目ID格式'}, ensure_ascii=False)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
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
                        knowledge_context=knowledge_context,
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
