"""目录相关API路由"""
import uuid
import json
import asyncio
from typing import Annotated, Any

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
from ..utils.config_manager import config_manager
from ..utils import prompt_manager
from ..utils.sse import sse_response
from ..auth.dependencies import require_editor

router = APIRouter(prefix="/api/outline", tags=["目录管理"])


# ============ 旧版接口（保持向后兼容） ============

@router.post("/generate")
async def generate_outline(
    request: OutlineRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
):
    """生成标书目录结构（以SSE流式返回）"""
    try:
        # 加载配置
        config = config_manager.load_config()

        if not config.get('api_key'):
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        # 创建OpenAI服务实例
        openai_service = OpenAIService()

        async def generate():
            try:
                # 后台计算主任务
                compute_task = asyncio.create_task(openai_service.generate_outline_v2(
                    overview=request.overview,
                    requirements=request.requirements
                ))

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
                    piece = result_str[i:i+chunk_size]
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
):
    """流式生成标书目录结构"""
    try:
        # 加载配置
        config = config_manager.load_config()

        if not config.get('api_key'):
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        # 创建OpenAI服务实例
        openai_service = OpenAIService()

        async def generate():
            if request.uploaded_expand:
                system_prompt, user_prompt = prompt_manager.generate_outline_with_old_prompt(
                    request.overview, request.requirements, request.old_outline
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
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
                    {"role": "user", "content": user_prompt}
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
        chapter = Chapter(
            project_id=project_id,
            parent_id=parent_id,
            chapter_number=item.get("id", str(order_start + idx + 1)),
            title=item.get("title", ""),
            content=item.get("description"),  # 描述暂时存到 content，后续生成内容时会覆盖
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


@router.post("/generate-project-stream")
async def generate_project_outline_stream(
    request: ProjectOutlineRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    流式生成项目目录结构，保存到 chapters 表

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

        # 加载配置
        config = config_manager.load_config()

        if not config.get('api_key'):
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        # 创建OpenAI服务实例
        openai_service = OpenAIService()

        # 用于收集完整结果的变量
        collected_result: list[str] = []

        async def generate():
            nonlocal collected_result

            system_prompt, user_prompt = prompt_manager.generate_outline_prompt(
                project.project_overview,
                project.tech_requirements,
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 流式返回目录生成结果，同时收集完整结果
            async for chunk in openai_service.stream_chat_completion(
                messages, temperature=0.7, response_format={"type": "json_object"}
            ):
                collected_result.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

            # 发送结束信号
            yield "data: [DONE]\n\n"

            # 解析完整结果并保存到数据库
            try:
                full_content = "".join(collected_result)
                outline_data = json.loads(full_content)
                outline_items = outline_data.get("outline", [])

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

            except (json.JSONDecodeError, KeyError) as e:
                # 解析失败但不影响已返回的流式结果
                print(f"解析目录结果失败: {e}")

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

        # 加载配置
        config = config_manager.load_config()

        if not config.get('api_key'):
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        # 获取父章节列表（用于上下文）
        parent_chapters: list[dict[str, Any]] = []
        current_parent_id = chapter.parent_id
        while current_parent_id:
            parent_result = await db.execute(
                select(Chapter).where(Chapter.id == current_parent_id)
            )
            parent_chapter = parent_result.scalar_one_or_none()
            if parent_chapter:
                parent_chapters.insert(0, {
                    "id": str(parent_chapter.id),
                    "chapter_number": parent_chapter.chapter_number,
                    "title": parent_chapter.title,
                })
                current_parent_id = parent_chapter.parent_id
            else:
                break

        # 获取同级章节列表
        siblings_result = await db.execute(
            select(Chapter).where(
                and_(
                    Chapter.project_id == project_uuid,
                    Chapter.parent_id == chapter.parent_id,
                )
            ).order_by(Chapter.order_index)
        )
        sibling_chapters = [
            {
                "id": str(s.id),
                "chapter_number": s.chapter_number,
                "title": s.title,
            }
            for s in siblings_result.scalars().all()
        ]

        # 创建OpenAI服务实例
        openai_service = OpenAIService()

        # 用于收集完整结果的变量
        collected_result: list[str] = []

        # 构建内容生成提示词
        system_prompt = """你是一个专业的标书撰写专家。请根据提供的章节信息和项目背景，为指定章节生成详细、专业的内容。

要求：
1. 内容要详实、专业，符合投标文件规范
2. 使用 Markdown 格式编写
3. 内容要有针对性，紧扣项目概述和技术要求
4. 适当使用表格、列表等格式增强可读性
5. 如果章节有子章节，则只需生成概述性内容
6. 直接输出内容，不要添加额外的说明"""

        parent_context = ""
        if parent_chapters:
            parent_context = "\n上级章节：\n" + "\n".join([
                f"- {p['chapter_number']} {p['title']}" for p in parent_chapters
            ])

        sibling_context = ""
        if sibling_chapters:
            sibling_context = "\n同级章节：\n" + "\n".join([
                f"- {s['chapter_number']} {s['title']}" for s in sibling_chapters
            ])

        user_prompt = f"""请为以下章节生成内容：

项目概述：
{project.project_overview or '暂无'}

技术评分要求：
{project.tech_requirements or '暂无'}

{parent_context}
{sibling_context}

当前章节：
- 编号：{chapter.chapter_number}
- 标题：{chapter.title}
{f'- 描述：{chapter.content}' if chapter.content else ''}

请生成该章节的详细内容。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
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

        return sse_response(generate())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内容生成失败: {str(e)}",
        )
