"""内容相关API路由"""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.schemas import ContentGenerationRequest, ChapterContentRequest
from ..models.user import User
from ..services.openai_service import OpenAIService
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
        async for chunk in openai_service._generate_chapter_content(
            chapter=request.chapter,
            parent_chapters=request.parent_chapters,
            sibling_chapters=request.sibling_chapters,
            project_overview=request.project_overview
        ):
            content += chunk

        return {"success": True, "content": content}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"章节内容生成失败: {str(e)}")


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
                async for chunk in openai_service._generate_chapter_content(
                    chapter=request.chapter,
                    parent_chapters=request.parent_chapters,
                    sibling_chapters=request.sibling_chapters,
                    project_overview=request.project_overview
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"章节内容生成失败: {str(e)}")
