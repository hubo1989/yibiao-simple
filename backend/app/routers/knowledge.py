"""知识库 API 路由 - 支持 PageIndex"""
import aiofiles
import os
import uuid
import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File, Form, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.user import UserRole
from ..models.user import User
from ..models.knowledge import KnowledgeDoc, DocType, IndexStatus, Scope, ContentSource
from ..models.schemas import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
)
from ..services.pageindex_service import PageIndexService
from ..services.knowledge_retrieval_service import KnowledgeRetrievalService
from ..services.openai_service import OpenAIService
from ..services.vector_index_service import VectorIndexService
from ..services.embedding_service import EmbeddingService
from ..auth.dependencies import get_current_active_user, require_editor
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


def _can_manage_knowledge_doc(doc: KnowledgeDoc, current_user: User) -> bool:
    """仅允许管理员或文档所有者管理私有知识库条目。"""
    return current_user.role == UserRole.ADMIN or doc.owner_id == current_user.id


# ============ 文件上传和索引 ============

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_knowledge_doc(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form("other"),
    scope: str = Form("user"),
    tags: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    上传知识库文档并生成 PageIndex 索引（需要 Editor 或更高角色）
    
    支持的文档类型：
    - history_bid: 历史标书
    - company_info: 企业资料
    - case_fragment: 案例片段
    - other: 其他
    
    支持的文件格式：PDF、DOCX
    """
    try:
        # 验证文档类型
        try:
            doc_type_enum = DocType(doc_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的文档类型: {doc_type}",
            )
        
        # 验证范围
        try:
            scope_enum = Scope(scope)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的范围: {scope}",
            )
        
        # 检查文件类型
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",  # .doc
        ]
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的文件类型，请上传 PDF、DOC 或 DOCX 文档",
            )
        
        # Magic bytes 校验
        header = await file.read(8)
        await file.seek(0)
        is_pdf = header[:5] == b'%PDF-'
        is_docx = header[:4] == b'PK\x03\x04'
        is_doc = header[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'  # .doc (OLE)
        
        if not (is_pdf or is_docx or is_doc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件内容与类型不匹配",
            )
        
        # 保存文件
        if is_pdf:
            file_ext = "pdf"
        elif is_docx:
            file_ext = "docx"
        else:
            file_ext = "doc"
        file_name = f"knowledge_{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(settings.upload_dir, file_name)
        
        os.makedirs(settings.upload_dir, exist_ok=True)
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 如果是 DOCX 或 DOC，需要转换为 PDF
        pageindex_service = PageIndexService()
        if is_docx or is_doc:
            try:
                file_path = await pageindex_service.convert_docx_to_pdf(file_path)
                file_ext = "pdf"
            except Exception as e:
                logger.error(f"Word 文档转换失败: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Word 文档转换失败: {str(e)}",
                )
        
        # 解析标签
        tag_list = []
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        
        # 创建数据库记录
        new_doc = KnowledgeDoc(
            name=title,  # 兼容旧字段
            title=title,
            doc_type=doc_type_enum,
            scope=scope_enum,
            owner_id=current_user.id,
            content_source=ContentSource.FILE,
            file_path=file_path,
            file_type=file_ext,
            tags=tag_list,
            category=category,
            pageindex_status=IndexStatus.PENDING,
        )
        db.add(new_doc)
        await db.flush()
        await db.refresh(new_doc)

        # 跳过 PageIndex，直接标记为完成
        new_doc.pageindex_status = IndexStatus.COMPLETED
        await db.commit()

        # 后台任务：只做向量索引
        logger.info(f"添加后台向量索引任务：doc_id={new_doc.id}, file_path={file_path}")
        background_tasks.add_task(
            process_vector_indexing_only,
            str(new_doc.id),
            file_path,
        )
        logger.info(f"后台任务已添加")

        return {
            "id": str(new_doc.id),
            "title": new_doc.title,
            "doc_type": new_doc.doc_type.value,
            "scope": new_doc.scope.value,
            "file_type": new_doc.file_type,
            "pageindex_status": new_doc.pageindex_status.value,
            "message": "文档上传成功，正在后台生成向量索引",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文档上传失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档上传失败: {str(e)}",
        )


async def process_pageindex_indexing(doc_id: str, file_path: str):
    """后台任务：处理 PageIndex 索引"""
    from ..db.database import async_session_factory
    logger.info(f"开始执行后台索引任务：doc_id={doc_id}, file_path={file_path}")

    # 更新状态为索引中
    async with async_session_factory() as session:
        result = await session.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one_or_none()
        if not doc:
            logger.error(f"文档不存在: {doc_id}")
            return

        doc.pageindex_status = IndexStatus.INDEXING
        await session.commit()  # 提交状态更新，让前端能看到"索引中"

    # 调用 PageIndex 处理 - 使用独立的 session 避免长时间事务
    pageindex_tree = None
    try:
        async with async_session_factory() as index_session:
            pageindex_service = PageIndexService(db=index_session)
            pageindex_tree = await pageindex_service.process_pdf(file_path)
    except Exception as e:
        logger.error(f"PageIndex 处理失败: {str(e)}", exc_info=True)
        # 更新失败状态
        async with async_session_factory() as fail_session:
            result = await fail_session.execute(
                select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.pageindex_status = IndexStatus.FAILED
                doc.pageindex_error = str(e)
                await fail_session.commit()
        return

    # 更新成功状态
    async with async_session_factory() as success_session:
        result = await success_session.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one_or_none()
        if doc:
            doc.pageindex_tree = pageindex_tree
            doc.pageindex_status = IndexStatus.COMPLETED
            doc.pageindex_error = None
            await success_session.commit()
            logger.info(f"PageIndex 索引完成: {doc_id}")

    # 触发向量索引
    await process_vector_indexing(doc_id, "")


async def process_vector_indexing(doc_id: str, content: str):
    """后台任务：处理向量索引"""
    from ..db.database import async_session_factory

    logger.info(f"开始向量索引：doc_id={doc_id}")

    # 更新向量索引状态为索引中
    async with async_session_factory() as session:
        result = await session.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return

        doc.vector_index_status = "indexing"
        await session.commit()

    try:
        async with async_session_factory() as index_session:
            # 重新获取 doc 对象
            result = await index_session.execute(
                select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return

            # 从 PageIndex 树提取内容
            content_text = ""
            if doc.pageindex_tree:
                content_text = _extract_content_from_tree(doc.pageindex_tree)
            elif doc.content:
                content_text = doc.content

            if content_text:
                vector_service = VectorIndexService(index_session)
                success = await vector_service.process_document(
                    uuid.UUID(doc_id),
                    content_text
                )

                async with async_session_factory() as update_session:
                    result = await update_session.execute(
                        select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
                    )
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.vector_index_status = "completed" if success else "failed"
                        if not success:
                            doc.vector_index_error = "向量索引处理失败"
                        await update_session.commit()
                        logger.info(f"向量索引完成: {doc_id}")
    except Exception as e:
        logger.error(f"向量索引失败: {str(e)}", exc_info=True)
        async with async_session_factory() as fail_session:
            result = await fail_session.execute(
                select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.vector_index_status = "failed"
                doc.vector_index_error = str(e)
                await fail_session.commit()


def _extract_content_from_tree(tree: dict) -> str:
    """从 PageIndex 树中提取所有内容"""
    def extract_recursive(node):
        parts = []
        if 'title' in node:
            parts.append(f"# {node['title']}")
        if 'summary' in node:
            parts.append(node['summary'])

        if 'nodes' in node:
            for child in node['nodes']:
                child_content = extract_recursive(child)
                if child_content:
                    parts.append(child_content)

        return "\n\n".join(parts) if parts else ""

    return extract_recursive(tree)


async def process_vector_indexing_only(doc_id: str, file_path: str):
    """后台任务：只处理向量索引（跳过 PageIndex）"""
    from ..db.database import async_session_factory
    from ..services.file_service import FileService

    logger.info(f"开始向量索引（跳过 PageIndex）：doc_id={doc_id}")

    # 更新向量索引状态为索引中
    async with async_session_factory() as session:
        result = await session.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return

        doc.vector_index_status = "indexing"
        await session.commit()

    try:
        # 从文件提取文本内容
        content_text = ""
        if file_path.endswith('.pdf'):
            file_service = FileService()
            content_text = await file_service.extract_text_from_pdf(file_path)
        elif file_path.endswith('.md'):
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content_text = await f.read()

        if content_text:
            async with async_session_factory() as index_session:
                vector_service = VectorIndexService(index_session)
                success = await vector_service.process_document(
                    uuid.UUID(doc_id),
                    content_text
                )

                async with async_session_factory() as update_session:
                    result = await update_session.execute(
                        select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
                    )
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.vector_index_status = "completed" if success else "failed"
                        if not success:
                            doc.vector_index_error = "向量索引处理失败"
                        await update_session.commit()
                        logger.info(f"向量索引完成: {doc_id}")
    except Exception as e:
        logger.error(f"向量索引失败: {str(e)}", exc_info=True)
        async with async_session_factory() as fail_session:
            result = await fail_session.execute(
                select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.vector_index_status = "failed"
                doc.vector_index_error = str(e)
                await fail_session.commit()


# ============ 手动创建 ============

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_knowledge_doc(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    content: str = Form(...),
    doc_type: str = Form("other"),
    scope: str = Form("user"),
    tags: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """手动创建知识库内容"""
    try:
        # 验证
        doc_type_enum = DocType(doc_type)
        scope_enum = Scope(scope)
        
        # 保存为 Markdown 文件
        pageindex_service = PageIndexService()
        md_path = os.path.join(
            settings.upload_dir,
            f"knowledge_{uuid.uuid4()}.md"
        )
        
        await pageindex_service.save_as_markdown(content, title, md_path)
        
        # 解析标签
        tag_list = []
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        
        # 创建数据库记录
        new_doc = KnowledgeDoc(
            name=title,  # 兼容旧字段
            title=title,
            doc_type=doc_type_enum,
            scope=scope_enum,
            owner_id=current_user.id,
            content_source=ContentSource.MANUAL,
            content=content,
            file_path=md_path,
            file_type="md",
            tags=tag_list,
            category=category,
            pageindex_status=IndexStatus.COMPLETED,  # 跳过 PageIndex
        )
        db.add(new_doc)
        await db.flush()
        await db.refresh(new_doc)

        # 后台任务：只做向量索引
        background_tasks.add_task(
            process_vector_indexing_only,
            str(new_doc.id),
            md_path,
        )

        return {
            "id": str(new_doc.id),
            "title": new_doc.title,
            "message": "知识库条目创建成功，正在生成向量索引",
        }
        
    except Exception as e:
        logger.error(f"创建知识库条目失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建失败: {str(e)}",
        )


async def process_pageindex_indexing_markdown(doc_id: str, md_path: str):
    """后台任务：处理 Markdown 的 PageIndex 索引"""
    from ..db.database import async_session_factory

    # 更新状态为索引中
    async with async_session_factory() as session:
        result = await session.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return

        doc.pageindex_status = IndexStatus.INDEXING
        await session.commit()  # 提交状态更新，让前端能看到"索引中"

    # 调用 PageIndex 处理
    pageindex_tree = None
    try:
        async with async_session_factory() as index_session:
            pageindex_service = PageIndexService(db=index_session)
            pageindex_tree = await pageindex_service.process_markdown(md_path)
    except Exception as e:
        logger.error(f"Markdown 索引失败: {str(e)}", exc_info=True)
        # 更新失败状态
        async with async_session_factory() as fail_session:
            result = await fail_session.execute(
                select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.pageindex_status = IndexStatus.FAILED
                doc.pageindex_error = str(e)
                await fail_session.commit()
        return

    # 更新成功状态
    async with async_session_factory() as success_session:
        result = await success_session.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one_or_none()
        if doc:
            doc.pageindex_tree = pageindex_tree
            doc.pageindex_status = IndexStatus.COMPLETED
            doc.pageindex_error = None
            await success_session.commit()
            logger.info(f"Markdown 索引完成: {doc_id}")

    # 触发向量索引
    await process_vector_indexing(doc_id, "")


# ============ 检索推荐 ============

@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    use_vector: bool = Query(False, description="是否使用向量搜索"),
):
    """
    检索相关知识库内容

    支持两种模式：
    - PageIndex 树搜索 + LLM 推理（默认）
    - 向量相似度搜索（use_vector=true）
    """
    try:
        openai_service = OpenAIService()
        retrieval_service = KnowledgeRetrievalService(db, openai_service)

        if use_vector:
            # 使用向量搜索
            query = f"{request.chapter_title}\n{request.chapter_description or ''}"
            results = await retrieval_service.search_with_vector(
                query=query,
                top_k=request.top_k,
                user_id=current_user.id
            )
        else:
            # 使用 PageIndex 搜索
            results = await retrieval_service.search_relevant_knowledge(
                chapter_title=request.chapter_title,
                chapter_description=request.chapter_description or "",
                parent_chapters=request.parent_chapters or [],
                project_overview=request.project_overview,
                user_id=current_user.id,
                top_k=request.top_k
            )

        return KnowledgeSearchResponse(
            results=[KnowledgeSearchResult(**r) for r in results],
            total=len(results)
        )
        
    except Exception as e:
        logger.error(f"检索失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检索失败: {str(e)}",
        )


# ============ CRUD 操作 ============

@router.get("")
async def list_knowledge_docs(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    doc_type: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取知识库列表"""
    query = select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc())
    
    if doc_type:
        try:
            query = query.where(KnowledgeDoc.doc_type == DocType(doc_type))
        except ValueError:
            pass
    
    if scope:
        try:
            query = query.where(KnowledgeDoc.scope == Scope(scope))
        except ValueError:
            pass
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    docs = result.scalars().all()
    
    return [
        {
            "id": str(doc.id),
            "title": doc.title,
            "doc_type": doc.doc_type.value,
            "scope": doc.scope.value,
            "file_type": doc.file_type,
            "pageindex_status": doc.pageindex_status.value,
            "vector_index_status": doc.vector_index_status,
            "tags": doc.tags or [],
            "usage_count": doc.usage_count,
            "created_at": doc.created_at.isoformat(),
        }
        for doc in docs
    ]


@router.post("/{doc_id}/reindex")
async def reindex_knowledge_doc(
    doc_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    重新生成知识库文档的向量索引（需要 Editor 或更高角色）
    """
    result = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在",
        )

    if not _can_manage_knowledge_doc(doc, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权重新索引该文档",
        )

    # 检查文件是否存在
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源文件不存在，无法重新索引",
        )

    # 重置向量索引状态
    doc.vector_index_status = "pending"
    doc.vector_index_error = None
    await db.commit()

    # 只做向量索引，跳过 PageIndex
    background_tasks.add_task(
        process_vector_indexing_only,
        str(doc.id),
        doc.file_path,
    )

    return {
        "id": str(doc.id),
        "message": "已发送重新索引请求",
    }


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_doc(
    doc_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """删除知识库文档"""
    import glob
    
    result = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在",
        )

    if not _can_manage_knowledge_doc(doc, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该文档",
        )

    # 删除文件（包括 PDF 和 DOC 文件）
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)
        # 同时删除同名的其他格式文件（.pdf, .doc, .docx）
        base_path = os.path.splitext(doc.file_path)[0]
        for ext in ['.pdf', '.doc', '.docx']:
            other_file = base_path + ext
            if other_file != doc.file_path and os.path.exists(other_file):
                os.remove(other_file)

    await db.delete(doc)
    await db.commit()
