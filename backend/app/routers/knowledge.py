"""知识库 CRUD API 路由"""
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..models.user import User
from ..models.knowledge import KnowledgeDoc, DocType, EmbeddingStatus
from ..schemas.knowledge import (
    KnowledgeDocCreate,
    KnowledgeDocUpdate,
    KnowledgeDocResponse,
    KnowledgeDocDetail,
    KnowledgeDocSummary,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from ..services.knowledge_service import KnowledgeService
from ..services.file_service import FileService
from ..auth.dependencies import get_current_active_user, require_editor

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


@router.post("/upload", response_model=KnowledgeDocResponse, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_doc(
    file: UploadFile = File(...),
    name: Annotated[str, Form(...)] = None,
    doc_type: Annotated[str, Form(...)] = "other",
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    上传知识库文档（需要 Editor 或更高角色）

    支持的文档类型：
    - qualification: 企业资质
    - case: 成功案例
    - technical: 技术方案
    - other: 其他

    支持的文件格式：PDF、Word
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

        # 检查文件类型
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的文件类型，请上传 PDF 或 Word 文档",
            )

        # Magic bytes 校验
        header = await file.read(8)
        await file.seek(0)
        is_pdf = header[:5] == b'%PDF-'
        is_docx = header[:4] == b'PK\x03\x04'
        if not (is_pdf or is_docx):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件内容与类型不匹配，请上传有效的 PDF 或 Word 文档",
            )

        # 提取文本内容
        text_content = await FileService.process_uploaded_file(file)

        if not text_content or not text_content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法从文档中提取文本内容，请确保文档包含可读文本",
            )

        # 创建数据库记录
        new_doc = KnowledgeDoc(
            name=name,
            doc_type=doc_type_enum,
            original_file_name=file.filename,
            uploaded_by=current_user.id,
            embedding_status=EmbeddingStatus.PENDING,
        )
        db.add(new_doc)
        await db.flush()
        await db.refresh(new_doc)

        # 处理文档（分块和 TF-IDF 计算）
        knowledge_service = KnowledgeService(db)
        await knowledge_service.process_document(new_doc.id, text_content)

        await db.refresh(new_doc)
        return new_doc

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档上传处理失败: {str(e)}",
        )


@router.get("", response_model=list[KnowledgeDocSummary])
async def list_knowledge_docs(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    doc_type: str | None = Query(None, description="按文档类型过滤"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取知识库文档列表"""
    stmt = select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc())

    if doc_type:
        try:
            doc_type_enum = DocType(doc_type)
            stmt = stmt.where(KnowledgeDoc.doc_type == doc_type_enum)
        except ValueError:
            pass  # 忽略无效的文档类型

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return docs


@router.get("/{doc_id}", response_model=KnowledgeDocDetail)
async def get_knowledge_doc(
    doc_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """获取知识库文档详情（包含分块内容）"""
    result = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在",
        )
    return doc


@router.put("/{doc_id}", response_model=KnowledgeDocResponse)
async def update_knowledge_doc(
    doc_id: uuid.UUID,
    data: KnowledgeDocUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """更新知识库文档（名称和类型）"""
    result = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在",
        )

    # 更新字段
    if data.name is not None:
        doc.name = data.name
    if data.doc_type is not None:
        doc.doc_type = DocType(data.doc_type)

    await db.flush()
    await db.refresh(doc)
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_doc(
    doc_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """删除知识库文档"""
    result = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在",
        )

    await db.delete(doc)


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    搜索知识库

    使用 TF-IDF 算法检索与查询关键词最相关的文档片段
    """
    knowledge_service = KnowledgeService(db)

    # 转换文档类型
    doc_types = None
    if request.doc_types:
        doc_types = [DocType(dt) for dt in request.doc_types]

    # 执行搜索
    results = await knowledge_service.search(
        query=request.query,
        doc_types=doc_types,
        limit=request.limit,
    )

    # 转换结果格式
    search_results = [
        SearchResult(
            doc_id=r["doc_id"],
            doc_name=r["doc_name"],
            doc_type=r["doc_type"],
            chunk_id=r["chunk_id"],
            text=r["text"],
            score=r["score"],
        )
        for r in results
    ]

    return SearchResponse(
        results=search_results,
        total=len(search_results),
    )
