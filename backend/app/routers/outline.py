"""目录相关API路由"""

import uuid
import json
import asyncio
import logging
from typing import Annotated, Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy import select, delete, and_, exists, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.schemas import (
    OutlineRequest,
    OutlineResponse,
    ProjectOutlineRequest,
    ProjectContentGenerateRequest,
    ProjectOutlineResponse,
    ChapterCreatedResponse,
)
from ..models.user import User
from ..models.project import Project, project_members, ProjectMemberRole
from ..models.chapter import Chapter, ChapterStatus
from ..models.version import ProjectVersion, ChangeType
from ..db.database import get_db
from ..services.openai_service import OpenAIService
from ..services.prompt_service import PromptService
from ..services.knowledge_retrieval_service import KnowledgeRetrievalService
from ..utils import prompt_manager
from ..utils.sse import sse_response
from ..auth.dependencies import require_editor

router = APIRouter(prefix="/api/outline", tags=["目录管理"])


# ============ 旧版接口（保持向后兼容） ============


@router.post("/generate")
async def generate_outline(
    request: OutlineRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """生成标书目录结构（以SSE流式返回）"""
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

        # 如果前端传了模型名称，覆盖默认模型
        if request.model_name:
            openai_service.set_model(request.model_name)

        async def generate():
            try:
                # 后台计算主任务
                compute_task = asyncio.create_task(
                    openai_service.generate_outline_v2(
                        overview=request.overview, requirements=request.requirements
                    )
                )

                # 在等待计算完成期间发送心跳，保持连接（发送空字符串chunk）
                while not compute_task.done():
                    yield f"data: {json.dumps({'chunk': ''}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(1)

                # 计算完成
                result = await compute_task

                # 确保为字符串
                if isinstance(result, dict):
                    result_str = json.dumps(result, ensure_ascii=False)
                else:
                    result_str = str(result)

                # 分片发送实际数据
                chunk_size = 128
                chunk_delay = 0.1  # 每个分片之间增加一点点延迟，增强SSE逐步展示效果
                for i in range(0, len(result_str), chunk_size):
                    piece = result_str[i : i + chunk_size]
                    yield f"data: {json.dumps({'chunk': piece}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(chunk_delay)
                # 发送结束信号
                yield "data: [DONE]\n\n"
            except Exception as e:
                # 捕获后台任务中的异常，通过 SSE 友好返回给前端
                error_message = f"目录生成失败: {str(e)}"
                payload = {
                    "chunk": "",
                    "error": True,
                    "message": error_message,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

        return sse_response(generate())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"目录生成失败: {str(e)}")


@router.post("/generate-stream")
async def generate_outline_stream(
    request: OutlineRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """流式生成标书目录结构"""
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

        # 如果前端传了模型名称，覆盖默认模型
        if request.model_name:
            openai_service.set_model(request.model_name)

        async def generate():
            if request.uploaded_expand:
                system_prompt, user_prompt = (
                    prompt_manager.generate_outline_with_old_prompt(
                        request.overview, request.requirements, request.old_outline
                    )
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]

                full_content = ""
                async for chunk in openai_service.stream_chat_completion(
                    messages, temperature=0.7, response_format={"type": "json_object"}
                ):
                    full_content += chunk

            else:
                system_prompt, user_prompt = prompt_manager.generate_outline_prompt(
                    request.overview, request.requirements
                )

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]

                # 流式返回目录生成结果
                async for chunk in openai_service.stream_chat_completion(
                    messages, temperature=0.7, response_format={"type": "json_object"}
                ):
                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

                # 发送结束信号
                yield "data: [DONE]\n\n"

        return sse_response(generate())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"目录生成失败: {str(e)}")


# ============ 项目上下文版本的接口 ============


async def _verify_project_editor(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[Project, ProjectMemberRole]:
    """
    验证用户是项目成员且具有 editor 或更高权限
    返回项目和用户角色
    """
    # 获取用户在项目中的角色
    result = await db.execute(
        select(project_members.c.role).where(
            and_(
                project_members.c.project_id == project_id,
                project_members.c.user_id == user_id,
            )
        )
    )
    role = result.scalar_one_or_none()

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或您没有访问权限",
        )

    # 验证是否是 editor 或 owner
    allowed_roles = {ProjectMemberRole.EDITOR, ProjectMemberRole.OWNER}
    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要 Editor 或更高权限",
        )

    # 获取项目
    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )

    return project, role


async def _get_next_version_number(db: AsyncSession, project_id: uuid.UUID) -> int:
    """获取项目的下一个版本号"""
    result = await db.execute(
        select(func.max(ProjectVersion.version_number)).where(
            ProjectVersion.project_id == project_id
        )
    )
    max_version = result.scalar_one_or_none()
    return (max_version or 0) + 1


async def _create_chapters_from_outline(
    db: AsyncSession,
    project_id: uuid.UUID,
    outline_items: list[dict[str, Any]],
    parent_id: uuid.UUID | None = None,
    order_start: int = 0,
) -> list[Chapter]:
    """递归从 outline 结构创建章节记录"""
    created_chapters = []

    for idx, item in enumerate(outline_items):
        # 防御：AI 返回的 children 中可能混入非 dict 元素（如嵌套 list）
        if not isinstance(item, dict):
            continue
        chapter = Chapter(
            project_id=project_id,
            parent_id=parent_id,
            chapter_number=item.get("id", str(order_start + idx + 1)),
            title=item.get("title", ""),
            content=item.get(
                "description"
            ),  # 描述暂时存到 content，后续生成内容时会覆盖
            rating_item=item.get("rating_item"),
            chapter_role=item.get("chapter_role"),
            avoid_overlap=item.get("avoid_overlap"),
            status=ChapterStatus.PENDING,
            order_index=order_start + idx,
        )
        db.add(chapter)
        await db.flush()  # 获取生成的 ID
        created_chapters.append(chapter)

        # 递归处理子章节
        children = item.get("children", [])
        if children:
            child_chapters = await _create_chapters_from_outline(
                db, project_id, children, chapter.id, 0
            )
            created_chapters.extend(child_chapters)

    return created_chapters


@router.post("/generate-project-l1-stream")
async def generate_project_outline_l1_stream(
    request: ProjectOutlineRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    流式生成项目一级目录结构，保存到 chapters 表

    - 验证用户是项目的 editor 或 admin
    - 只生成一级目录
    """
    try:
        # 验证 project_id 格式
        try:
            project_uuid = uuid.UUID(request.project_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的项目ID格式",
            )

        # 验证用户权限
        project, _ = await _verify_project_editor(project_uuid, current_user.id, db)

        # 检查项目是否有分析结果
        if not project.project_overview or not project.tech_requirements:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目尚未完成文档分析，请先分析招标文件",
            )

        # 创建OpenAI服务实例，从数据库加载配置
        openai_service = OpenAIService(db=db, project_id=project_uuid)
        if request.provider_config_id:
            configured = await openai_service.use_config_by_id(request.provider_config_id)
            if not configured:
                raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
        else:
            await openai_service._ensure_initialized()

        if not openai_service.api_key:
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        # 如果前端传了模型名称，覆盖默认模型
        if request.model_name:
            openai_service.set_model(request.model_name)

        async def generate():
            # 使用 prompt_manager 生成一级目录
            system_prompt, user_prompt = prompt_manager.generate_outline_prompt(
                project.project_overview,
                project.tech_requirements,
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            collected_result = []
            
            # 流式返回目录生成结果
            async for chunk in openai_service.stream_chat_completion(
                messages, temperature=0.7
            ):
                collected_result.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

            # 发送结束信号
            yield "data: [DONE]\n\n"

            # 解析并保存到数据库
            try:
                full_content = "".join(collected_result)
                
                # 清理 Markdown 代码块格式（贪婪匹配最外层）
                import re
                json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', full_content, re.DOTALL)
                if json_match:
                    full_content = json_match.group(1)
                
                # JSON 解析 + 容错：尝试修复常见的 AI 输出问题
                full_content = full_content.strip()
                try:
                    outline_data = json.loads(full_content)
                except json.JSONDecodeError:
                    # 尝试修复：去除尾部多余逗号、截断到最后一个 ] 或 }
                    cleaned = re.sub(r',\s*([}\]])', r'\1', full_content)
                    # 找到最后一个完整的 JSON 结构
                    last_bracket = max(cleaned.rfind(']'), cleaned.rfind('}'))
                    if last_bracket > 0:
                        cleaned = cleaned[:last_bracket + 1]
                    try:
                        outline_data = json.loads(cleaned)
                    except json.JSONDecodeError as parse_err:
                        print(f"L1 目录 JSON 解析失败: {parse_err}\n原文: {full_content[:500]}")
                        yield f"data: {json.dumps({'error': True, 'message': '目录数据格式异常，请重试'}, ensure_ascii=False)}\n\n"
                        return

                # AI 可能返回 {"outline": [...]} 或直接返回 [...]
                if isinstance(outline_data, list):
                    outline_items = outline_data
                elif isinstance(outline_data, dict):
                    outline_items = outline_data.get("outline", outline_data.get("chapters", []))
                else:
                    print(f"L1 目录返回了非预期类型: {type(outline_data)}")
                    yield f"data: {json.dumps({'error': True, 'message': '目录数据格式异常，请重试'}, ensure_ascii=False)}\n\n"
                    return

                # 过滤掉非 dict 元素，只保留有效的章节项
                outline_items = [item for item in outline_items if isinstance(item, dict)]

                # AI prompt 返回字段名可能是 new_title/chapter_role,
                # 标准化为 _create_chapters_from_outline 期望的 id/title/description
                for idx, item in enumerate(outline_items):
                    if "id" not in item:
                        item["id"] = str(idx + 1)
                    if "title" not in item and "new_title" in item:
                        item["title"] = item["new_title"]
                    if "description" not in item and "chapter_role" in item:
                        item["description"] = item["chapter_role"]

                if outline_items:
                    # 先删除项目现有的所有章节
                    await db.execute(
                        delete(Chapter).where(Chapter.project_id == project_uuid)
                    )

                    # 创建新章节
                    created_chapters = await _create_chapters_from_outline(
                        db, project_uuid, outline_items
                    )

                    # 创建版本快照
                    version_number = await _get_next_version_number(db, project_uuid)
                    snapshot_data = {
                        "outline": outline_items,
                        "total_chapters": len(created_chapters),
                    }
                    version = ProjectVersion(
                        project_id=project_uuid,
                        chapter_id=None,
                        version_number=version_number,
                        snapshot_data=snapshot_data,
                        change_type=ChangeType.AI_GENERATE,
                        change_summary="AI 生成一级目录",
                        created_by=current_user.id,
                    )
                    db.add(version)
                    await db.flush()
                    await db.commit()

            except Exception as e:
                print(f"保存一级目录到数据库失败: {e}")
                await db.rollback()

        return sse_response(generate())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"一级目录生成失败: {str(e)}",
        )


@router.post("/generate-project-l2l3-stream")
async def generate_project_outline_l2l3_stream(
    request: ProjectOutlineRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    流式生成项目二三级目录结构，基于现有的一级目录

    - 验证用户是项目的 editor 或 admin
    - 需要先有一级目录
    """
    try:
        # 验证 project_id 格式
        try:
            project_uuid = uuid.UUID(request.project_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的项目ID格式",
            )

        # 验证用户权限
        project, _ = await _verify_project_editor(project_uuid, current_user.id, db)

        # 检查项目是否有分析结果
        if not project.project_overview or not project.tech_requirements:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目尚未完成文档分析，请先分析招标文件",
            )

        # 检查是否有一级目录
        existing_chapters = await db.execute(
            select(Chapter).where(
                and_(
                    Chapter.project_id == project_uuid,
                    Chapter.parent_id.is_(None)
                )
            )
        )
        l1_chapters = existing_chapters.scalars().all()
        
        # 兜底逻辑：如果数据库没有数据，使用前端传递的数据
        use_frontend_data = False
        if not l1_chapters:
            if request.outline_data and request.outline_data.get("outline"):
                use_frontend_data = True
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="请先生成一级目录",
                )

        # 创建OpenAI服务实例，从数据库加载配置
        openai_service = OpenAIService(db=db, project_id=project_uuid)
        if request.provider_config_id:
            configured = await openai_service.use_config_by_id(request.provider_config_id)
            if not configured:
                raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
        else:
            await openai_service._ensure_initialized()

        if not openai_service.api_key:
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        # 如果前端传了模型名称，覆盖默认模型
        if request.model_name:
            openai_service.set_model(request.model_name)

        async def generate():
            # 构造一级目录数据（优先使用数据库数据，兜底使用前端数据）
            if use_frontend_data and request.outline_data:
                level_l1 = [
                    {
                        "rating_item": item.get("title", ""),
                        "new_title": item.get("title", "")
                    }
                    for item in request.outline_data.get("outline", [])
                ]
            else:
                level_l1 = [
                    {
                        "rating_item": chapter.title,
                        "new_title": chapter.title
                    }
                    for chapter in l1_chapters
                ]
            
            # 使用 generate_outline_v2 的逻辑生成二三级目录
            try:
                from ..services.openai_service import calculate_nodes_distribution, get_random_indexes
                
                expected_word_count = 100000
                leaf_node_count = expected_word_count // 1500
                index1, index2 = get_random_indexes(len(level_l1))
                nodes_distribution = calculate_nodes_distribution(
                    len(level_l1), (index1, index2), leaf_node_count
                )

                # 顺序生成每个一级节点的二三级目录，并流式返回每个章节（避免数据库会话并发问题）
                outline = []
                for i, level1_node in enumerate(level_l1):
                    # 生成一个章节
                    result = await openai_service.process_level1_node(
                        i, level1_node, nodes_distribution, level_l1,
                        project.project_overview, project.tech_requirements
                    )
                    outline.append(result)
                    
                    # 立即流式返回这个章节
                    chapter_json = json.dumps(result, ensure_ascii=False)
                    yield f"data: {json.dumps({'type': 'chapter', 'index': i, 'total': len(level_l1), 'data': result}, ensure_ascii=False)}\n\n"

                # 发送完成信号
                outline_result = {"outline": outline}
                yield f"data: {json.dumps({'type': 'complete', 'data': outline_result}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

                # 保存到数据库
                outline_items = outline_result.get("outline", [])
                if outline_items:
                    # 先删除项目现有的所有章节
                    await db.execute(
                        delete(Chapter).where(Chapter.project_id == project_uuid)
                    )

                    # 创建新章节
                    created_chapters = await _create_chapters_from_outline(
                        db, project_uuid, outline_items
                    )

                    # 创建版本快照
                    version_number = await _get_next_version_number(db, project_uuid)
                    snapshot_data = {
                        "outline": outline_items,
                        "total_chapters": len(created_chapters),
                    }
                    version = ProjectVersion(
                        project_id=project_uuid,
                        chapter_id=None,
                        version_number=version_number,
                        snapshot_data=snapshot_data,
                        change_type=ChangeType.AI_GENERATE,
                        change_summary="AI 生成二三级目录",
                        created_by=current_user.id,
                    )
                    db.add(version)
                    await db.flush()
                    await db.commit()

            except Exception as e:
                await db.rollback()
                error_msg = f"生成二三级目录失败: {str(e)}"
                print(error_msg)
                yield f"data: {json.dumps({'error': True, 'message': error_msg}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

        return sse_response(generate())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"二三级目录生成失败: {str(e)}",
        )


@router.post("/generate-project-stream")
async def generate_project_outline_stream(
    request: ProjectOutlineRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    流式生成项目完整目录结构（一级+二三级），保存到 chapters 表

    - 验证用户是项目的 editor 或 admin
    - 生成完成后创建版本快照
    """
    try:
        # 验证 project_id 格式
        try:
            project_uuid = uuid.UUID(request.project_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的项目ID格式",
            )

        # 验证用户权限
        project, _ = await _verify_project_editor(project_uuid, current_user.id, db)

        # 检查项目是否有分析结果
        if not project.project_overview or not project.tech_requirements:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目尚未完成文档分析，请先分析招标文件",
            )

        # 创建OpenAI服务实例，从数据库加载配置
        openai_service = OpenAIService(db=db, project_id=project_uuid)
        if request.provider_config_id:
            configured = await openai_service.use_config_by_id(request.provider_config_id)
            if not configured:
                raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
        else:
            await openai_service._ensure_initialized()

        if not openai_service.api_key:
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        # 如果前端传了模型名称，覆盖默认模型
        if request.model_name:
            openai_service.set_model(request.model_name)

        async def generate():
            # 使用 generate_outline_v2 生成完整的三级目录结构
            try:
                outline_result = await openai_service.generate_outline_v2(
                    overview=project.project_overview,
                    requirements=project.tech_requirements
                )
                
                # 流式返回完整的目录结构
                outline_json = json.dumps(outline_result, ensure_ascii=False)
                chunk_size = 128
                for i in range(0, len(outline_json), chunk_size):
                    piece = outline_json[i : i + chunk_size]
                    yield f"data: {json.dumps({'chunk': piece}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.01)
                
                # 发送结束信号
                yield "data: [DONE]\n\n"
                
                # 保存到数据库
                outline_items = outline_result.get("outline", [])

                if outline_items:
                    # 先删除项目现有的所有章节
                    await db.execute(
                        delete(Chapter).where(Chapter.project_id == project_uuid)
                    )

                    # 创建新章节
                    created_chapters = await _create_chapters_from_outline(
                        db, project_uuid, outline_items
                    )

                    # 创建版本快照
                    version_number = await _get_next_version_number(db, project_uuid)
                    snapshot_data = {
                        "outline": outline_items,
                        "total_chapters": len(created_chapters),
                    }
                    version = ProjectVersion(
                        project_id=project_uuid,
                        chapter_id=None,  # 全量快照
                        version_number=version_number,
                        snapshot_data=snapshot_data,
                        change_type=ChangeType.AI_GENERATE,
                        change_summary="AI 生成目录结构",
                        created_by=current_user.id,
                    )
                    db.add(version)

                    await db.flush()
                    await db.commit()

            except Exception as e:
                await db.rollback()
                print(f"保存目录到数据库失败: {e}")

        return sse_response(generate())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"目录生成失败: {str(e)}",
        )


@router.get("/project-chapters/{project_id}", response_model=ProjectOutlineResponse)
async def get_project_chapters(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """获取项目的章节列表"""
    # 验证用户是项目成员
    await _verify_project_editor(project_id, current_user.id, db)

    # 查询所有章节
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.order_index, Chapter.chapter_number)
    )
    chapters = result.scalars().all()

    chapter_responses = [
        ChapterCreatedResponse(
            id=str(chapter.id),
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            parent_id=str(chapter.parent_id) if chapter.parent_id else None,
            status=chapter.status.value,
        )
        for chapter in chapters
    ]

    return ProjectOutlineResponse(
        project_id=str(project_id),
        chapters=chapter_responses,
        total_count=len(chapter_responses),
    )


@router.post("/generate-content-stream")
async def generate_project_content_stream(
    request: ProjectContentGenerateRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    流式生成章节内容，保存到 chapter.content 字段

    - 验证用户是项目的 editor 或 admin
    - 生成完成后更新章节状态为 generated
    - 创建版本快照
    """
    try:
        # 验证 ID 格式
        try:
            project_uuid = uuid.UUID(request.project_id)
            chapter_uuid = uuid.UUID(request.chapter_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的ID格式",
            )

        # 验证用户权限
        project, _ = await _verify_project_editor(project_uuid, current_user.id, db)

        # 获取章节
        chapter_result = await db.execute(
            select(Chapter).where(
                and_(
                    Chapter.id == chapter_uuid,
                    Chapter.project_id == project_uuid,
                )
            )
        )
        chapter = chapter_result.scalar_one_or_none()
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在",
            )

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

        # 如果前端传了模型名称，覆盖默认模型
        if request.model_name:
            openai_service.set_model(request.model_name)

        # 获取父章节列表（用于上下文）
        parent_chapters: list[dict[str, Any]] = []
        current_parent_id = chapter.parent_id
        while current_parent_id:
            parent_result = await db.execute(
                select(Chapter).where(Chapter.id == current_parent_id)
            )
            parent_chapter = parent_result.scalar_one_or_none()
            if parent_chapter:
                parent_chapters.insert(
                    0,
                    {
                        "id": str(parent_chapter.id),
                        "chapter_number": parent_chapter.chapter_number,
                        "title": parent_chapter.title,
                    },
                )
                current_parent_id = parent_chapter.parent_id
            else:
                break

        # 获取同级章节列表
        siblings_result = await db.execute(
            select(Chapter)
            .where(
                and_(
                    Chapter.project_id == project_uuid,
                    Chapter.parent_id == chapter.parent_id,
                )
            )
            .order_by(Chapter.order_index)
        )
        sibling_chapters = [
            {
                "id": str(s.id),
                "chapter_number": s.chapter_number,
                "title": s.title,
            }
            for s in siblings_result.scalars().all()
        ]

        # 用于收集完整结果的变量
        collected_result: list[str] = []

        # 知识库检索：获取相关知识库内容
        knowledge_context = ""
        try:
            retrieval_service = KnowledgeRetrievalService(db, openai_service)
            knowledge_results = await retrieval_service.search_relevant_knowledge(
                chapter_title=chapter.title,
                chapter_description=chapter.content or "",
                parent_chapters=[
                    {"title": p["title"], "description": ""}
                    for p in (parent_chapters or [])
                ],
                project_overview=project.project_overview or "",
                user_id=current_user.id,
                top_k=4
            )

            if knowledge_results:
                knowledge_parts = []
                for idx, result in enumerate(knowledge_results, start=1):
                    doc_type = result.get("doc_type") or "unknown"
                    doc_type_label = {
                        "history_bid": "历史标书风格",
                        "company_info": "企业资料/能力",
                    }.get(doc_type, doc_type)
                    content = result.get("content") or result.get("content_preview") or ""
                    reasoning = result.get("reasoning") or ""
                    knowledge_parts.append(
                        f"[{idx}] 类型: {doc_type_label}\n标题: {result['title']}\n相关性: {reasoning}\n内容:\n{content}"
                    )
                knowledge_context = "\n\n---\n\n".join(knowledge_parts)
                logger.info(f"为章节 {chapter.title} 检索到 {len(knowledge_results)} 条知识库内容")
        except Exception as e:
            logger.warning(f"知识库检索失败，跳过: {str(e)}")

        # 使用 PromptService 获取提示词
        prompt_service = PromptService(db)
        prompt, _ = await prompt_service.get_prompt("chapter_content", project_uuid)
        system_prompt, user_template = PromptService.split_prompt(prompt)

        # 构建上级章节和同级章节信息（与模板变量匹配）
        parent_chapters_formatted = [
            {"id": p["chapter_number"], "title": p["title"], "description": ""}
            for p in (parent_chapters or [])
        ]
        sibling_chapters_formatted = [
            {"id": s["chapter_number"], "title": s["title"], "description": ""}
            for s in (sibling_chapters or [])
        ]

        chapter_role = getattr(chapter, "chapter_role", "") or chapter.content or ""
        chapter_rating_focus = getattr(chapter, "rating_item", "") or ""
        adjacent_boundary = getattr(chapter, "avoid_overlap", "") or ""

        if sibling_chapters_formatted and not adjacent_boundary:
            sibling_titles = "；".join([
                f"{item['id']} {item['title']}" for item in sibling_chapters_formatted if item.get("title") != chapter.title
            ])
            if sibling_titles:
                adjacent_boundary = f"避免重复展开以下同级章节已承担或可能承担的内容：{sibling_titles}"

        # 渲染用户提示词模板
        template_vars = {
            "project_overview": project.project_overview or "暂无",
            "tech_requirements": project.tech_requirements or "",
            "chapter_rating_focus": chapter_rating_focus,
            "chapter_role": chapter_role,
            "adjacent_boundary": adjacent_boundary,
            "parent_chapters": parent_chapters_formatted,
            "sibling_chapters": sibling_chapters_formatted,
            "chapter_id": str(chapter.id),
            "chapter_title": chapter.title,
            "chapter_description": chapter.content or "",
        }

        # 如果有知识库上下文，添加到模板变量
        if knowledge_context:
            template_vars["knowledge_context"] = knowledge_context
        
        user_prompt = prompt_service.render_prompt(
            user_template,
            template_vars,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        async def generate():
            nonlocal collected_result

            # 流式返回内容生成结果，同时收集完整结果
            async for chunk in openai_service.stream_chat_completion(
                messages, temperature=0.7
            ):
                collected_result.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

            # 发送结束信号
            yield "data: [DONE]\n\n"

            # 保存内容到章节
            full_content = "".join(collected_result)
            chapter.content = full_content
            chapter.status = ChapterStatus.GENERATED

            # 创建版本快照
            version_number = await _get_next_version_number(db, project_uuid)
            snapshot_data = {
                "chapter_id": str(chapter.id),
                "chapter_number": chapter.chapter_number,
                "title": chapter.title,
                "content": full_content,
            }
            version = ProjectVersion(
                project_id=project_uuid,
                chapter_id=chapter_uuid,
                version_number=version_number,
                snapshot_data=snapshot_data,
                change_type=ChangeType.AI_GENERATE,
                change_summary=f"AI 生成章节内容: {chapter.chapter_number} {chapter.title}",
                created_by=current_user.id,
            )
            db.add(version)

            await db.flush()
            await db.commit()

        return sse_response(generate())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内容生成失败: {str(e)}",
        )
