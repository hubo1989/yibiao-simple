"""内容相关API路由"""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.schemas import ContentGenerationRequest, ChapterContentRequest
from ..models.user import User
from ..services.openai_service import OpenAIService
from ..services.knowledge_retrieval_service import KnowledgeRetrievalService
from ..db.database import get_db
from ..utils.sse import sse_response
from ..auth.dependencies import require_editor

import json

router = APIRouter(prefix="/api/content", tags=["内容管理"])


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
                    query = f"{chapter_title} {(request.project_overview or '')[:200]}"
                    results = await retrieval_service.search(
                        query=query,
                        top_k=5,
                        user_id=current_user.id if current_user else None,
                    )
                    if results:
                        knowledge_context = "\n\n".join(
                            f"【{r.get('title', '参考文档')}】\n{r.get('content', '')}"
                            for r in results
                            if r.get("content")
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
            ):
                content += chunk

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
                            query = f"{chapter_title} {(request.project_overview or '')[:200]}"
                            results = await retrieval_service.search(
                                query=query,
                                top_k=5,
                                user_id=current_user.id if current_user else None,
                            )
                            if results:
                                knowledge_context = "\n\n".join(
                                    f"【{r.get('title', '参考文档')}】\n{r.get('content', '')}"
                                    for r in results
                                    if r.get("content")
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
                    ):
                        full_content += chunk
                        # 实时发送内容片段
                        yield f"data: {json.dumps({'status': 'streaming', 'content': chunk, 'full_content': full_content}, ensure_ascii=False)}\n\n"

                # 发送完成信号
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
