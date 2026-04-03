"""知识库 API 路由 - 支持向量索引"""
import aiofiles
import os
import uuid
import logging
from typing import Annotated, Optional

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
from ..services.knowledge_retrieval_service import KnowledgeRetrievalService
from ..services.openai_service import OpenAIService
from ..services.llamaindex_knowledge_service import LlamaIndexKnowledgeService, build_document_metadata
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
    上传知识库文档并生成向量索引（需要 Editor 或更高角色）

    支持的文档类型：
    - history_bid: 历史标书
    - company_info: 企业资料
    - case_fragment: 案例片段
    - other: 其他

    支持的文件格式：PDF
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
        ]

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的文件类型，请上传 PDF 文档",
            )

        # Magic bytes 校验
        header = await file.read(8)
        await file.seek(0)
        is_pdf = header[:5] == b'%PDF-'

        if not is_pdf:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件内容与类型不匹配，请上传有效的 PDF 文件",
            )

        # 保存文件
        file_ext = "pdf"
        file_name = f"knowledge_{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(settings.upload_dir, file_name)

        os.makedirs(settings.upload_dir, exist_ok=True)

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

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
            pageindex_status=IndexStatus.COMPLETED,  # 跳过 PageIndex
            vector_index_status="pending",
        )
        db.add(new_doc)
        await db.commit()
        await db.refresh(new_doc)

        # 后台任务：只做向量索引
        logger.info(f"添加后台向量索引任务：doc_id={new_doc.id}, file_path={file_path}")
        background_tasks.add_task(
            process_vector_indexing_only,
            str(new_doc.id),
            file_path,
        )

        return {
            "id": str(new_doc.id),
            "title": new_doc.title,
            "doc_type": new_doc.doc_type.value,
            "scope": new_doc.scope.value,
            "file_type": new_doc.file_type,
            "vector_index_status": new_doc.vector_index_status,
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


async def process_vector_indexing_only(doc_id: str, file_path: str):
    """后台任务：使用 LlamaIndex 进行向量索引"""
    from ..db.database import async_session_factory
    from ..services.file_service import FileService

    logger.info(f"开始 LlamaIndex 向量索引：doc_id={doc_id}")

    async with async_session_factory() as session:
        result = await session.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one_or_none()
        if not doc:
            logger.error(f"文档不存在: {doc_id}")
            return

        doc.vector_index_status = "indexing"
        await session.commit()

        try:
            # 提取文本
            content_text = ""
            if file_path.endswith(".pdf"):
                content_text = await FileService.extract_text_from_pdf(file_path)
            elif file_path.endswith(".md"):
                import aiofiles
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content_text = await f.read()

            if not content_text.strip():
                doc.vector_index_status = "failed"
                doc.vector_index_error = "文档内容为空"
                await session.commit()
                return

            # 构建元数据
            metadata = build_document_metadata(
                doc_id=doc.id,
                title=doc.title,
                doc_type=doc.doc_type.value,
                scope=doc.scope.value,
                owner_id=doc.owner_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
                tags=doc.tags or [],
                category=doc.category,
            )

            # 使用 LlamaIndex 索引
            llamaindex_service = LlamaIndexKnowledgeService(session)
            success = await llamaindex_service.index_document(
                doc_id=doc.id,
                text=content_text,
                metadata=metadata,
            )

            if success:
                doc.vector_index_status = "completed"
                doc.index_backend = "llamaindex"
                doc.index_version = 1
                logger.info(f"LlamaIndex 向量索引完成: {doc_id}")
            else:
                doc.vector_index_status = "failed"
                logger.error(f"LlamaIndex 向量索引失败: {doc_id}")

        except Exception as e:
            logger.error(f"向量索引失败: {str(e)}", exc_info=True)
            doc.vector_index_status = "failed"
            doc.vector_index_error = str(e)

        await session.commit()


# ============ 手动创建知识库条目 ============

@router.post("/manual", status_code=status.HTTP_201_CREATED)
async def create_manual_knowledge_doc(
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
    """手动创建知识库条目"""
    try:
        doc_type_enum = DocType(doc_type)
        scope_enum = Scope(scope)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # 保存为 Markdown 文件
    md_filename = f"knowledge_{uuid.uuid4()}.md"
    md_path = os.path.join(settings.upload_dir, md_filename)
    os.makedirs(settings.upload_dir, exist_ok=True)

    async with aiofiles.open(md_path, "w", encoding="utf-8") as f:
        await f.write(f"# {title}\n\n{content}")

    new_doc = KnowledgeDoc(
        name=title,
        title=title,
        doc_type=doc_type_enum,
        scope=scope_enum,
        owner_id=current_user.id,
        content_source=ContentSource.MANUAL,
        content=content,  # 直接存储内容
        file_path=md_path,
        file_type="md",
        tags=tag_list,
        category=category,
        pageindex_status=IndexStatus.COMPLETED,
        vector_index_status="pending",
        index_backend="llamaindex",
        index_version=1,
    )
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)

    # 后台向量索引
    background_tasks.add_task(process_vector_indexing_only, str(new_doc.id), md_path)

    return {
        "id": str(new_doc.id),
        "title": new_doc.title,
        "message": "知识库条目创建成功，正在生成向量索引",
    }


# ============ 查询和搜索 ============

@router.get("/docs")
async def list_knowledge_docs(
    doc_type: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """获取知识库文档列表"""
    query = select(KnowledgeDoc)

    # 权限过滤：非管理员只能看到自己的私有文档和所有公开文档
    if current_user.role != UserRole.ADMIN:
        query = query.where(
            (KnowledgeDoc.scope == Scope.GLOBAL) |
            (KnowledgeDoc.owner_id == current_user.id)
        )

    # 类型过滤
    if doc_type:
        try:
            doc_type_enum = DocType(doc_type)
            query = query.where(KnowledgeDoc.doc_type == doc_type_enum)
        except ValueError:
            pass

    # 范围过滤
    if scope:
        try:
            scope_enum = Scope(scope)
            query = query.where(KnowledgeDoc.scope == scope_enum)
        except ValueError:
            pass

    # 关键词搜索
    if keyword:
        query = query.where(KnowledgeDoc.title.ilike(f"%{keyword}%"))

    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(KnowledgeDoc.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    docs = result.scalars().all()

    # 获取总数
    count_query = select(KnowledgeDoc)
    if current_user.role != UserRole.ADMIN:
        count_query = count_query.where(
            (KnowledgeDoc.scope == Scope.GLOBAL) |
            (KnowledgeDoc.owner_id == current_user.id)
        )
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())

    return {
        "items": [
            {
                "id": str(doc.id),
                "title": doc.title,
                "doc_type": doc.doc_type.value,
                "scope": doc.scope.value,
                "file_type": doc.file_type,
                "tags": doc.tags or [],
                "category": doc.category,
                "vector_index_status": doc.vector_index_status,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            }
            for doc in docs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """向量相似度搜索知识库"""
    retrieval_service = KnowledgeRetrievalService(db)

    results = await retrieval_service.search(
        query=request.query,
        top_k=request.top_k,
        doc_types=request.doc_types,
        scope=request.scope,
        user_id=current_user.id if current_user.role != UserRole.ADMIN else None,
    )

    return KnowledgeSearchResponse(
        results=[
            KnowledgeSearchResult(
                doc_id=r["doc_id"],
                title=r["title"],
                content=r["content"],
                score=r["score"],
                metadata=r.get("metadata", {}),
            )
            for r in results
        ]
    )


@router.get("/docs/{doc_id}")
async def get_knowledge_doc(
    doc_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """获取单个知识库文档详情"""
    result = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

    # 权限检查
    if doc.scope == Scope.USER and doc.owner_id != current_user.id:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问此文档")

    return {
        "id": str(doc.id),
        "title": doc.title,
        "doc_type": doc.doc_type.value,
        "scope": doc.scope.value,
        "content_source": doc.content_source.value,
        "file_type": doc.file_type,
        "tags": doc.tags or [],
        "category": doc.category,
        "vector_index_status": doc.vector_index_status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


# ============ 更新和删除 ============

@router.put("/docs/{doc_id}")
async def update_knowledge_doc(
    doc_id: str,
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """更新知识库文档元数据"""
    result = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

    if not _can_manage_knowledge_doc(doc, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改此文档")

    if title:
        doc.title = title
        doc.name = title  # 兼容旧字段

    if tags is not None:
        doc.tags = [t.strip() for t in tags.split(",") if t.strip()]

    if category is not None:
        doc.category = category

    await db.commit()

    return {"message": "文档更新成功", "id": str(doc.id)}


@router.delete("/docs/{doc_id}")
async def delete_knowledge_doc(
    doc_id: str,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """删除知识库文档"""
    result = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

    if not _can_manage_knowledge_doc(doc, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此文档")

    # 删除文件
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            logger.warning(f"删除文件失败: {doc.file_path}, 错误: {str(e)}")

    # 删除向量索引（使用 LlamaIndex）
    try:
        llamaindex_service = LlamaIndexKnowledgeService(db)
        await llamaindex_service.delete_document(uuid.UUID(doc_id))
    except Exception as e:
        logger.warning(f"删除向量索引失败: {str(e)}")

    # 删除数据库记录
    await db.delete(doc)
    await db.commit()

    return {"message": "文档删除成功"}


# ============ 统计 ============

@router.get("/stats")
async def get_knowledge_stats(
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """获取知识库统计信息"""
    query = select(KnowledgeDoc)

    if current_user.role != UserRole.ADMIN:
        query = query.where(
            (KnowledgeDoc.scope == Scope.GLOBAL) |
            (KnowledgeDoc.owner_id == current_user.id)
        )

    result = await db.execute(query)
    docs = result.scalars().all()

    stats = {
        "total": len(docs),
        "by_type": {},
        "by_scope": {},
    }

    for doc in docs:
        # 按类型统计
        doc_type = doc.doc_type.value
        stats["by_type"][doc_type] = stats["by_type"].get(doc_type, 0) + 1

        # 按范围统计
        scope = doc.scope.value
        stats["by_scope"][scope] = stats["by_scope"].get(scope, 0) + 1

    return stats
