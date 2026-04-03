"""LlamaIndex 知识库服务 - 基于 LlamaIndex + pgvector 的统一知识管理"""
import logging
import uuid
from typing import List, Dict, Any, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.knowledge import KnowledgeDoc

logger = logging.getLogger(__name__)


def build_document_metadata(
    doc_id: uuid.UUID,
    title: str,
    doc_type: str,
    scope: str,
    owner_id: uuid.UUID,
    tags: Optional[List[str]] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """构建 LlamaIndex 文档元数据

    Args:
        doc_id: 文档 ID
        title: 文档标题
        doc_type: 文档类型
        scope: 数据范围 (global/enterprise/user)
        owner_id: 所有者 ID
        tags: 标签列表
        category: 分类

    Returns:
        标准化的元数据字典
    """
    return {
        "doc_id": str(doc_id),
        "title": title,
        "doc_type": doc_type,
        "scope": scope,
        "owner_id": str(owner_id),
        "category": category or "",
        "tags": tags or [],
    }


def build_access_filters(
    user_id: Optional[str] = None,
    enterprise_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """构建权限过滤条件

    规则：
    - 始终包含 scope == global
    - 包含当前用户拥有的文档
    - 包含企业拥有的文档

    Args:
        user_id: 用户 ID
        enterprise_id: 企业 ID

    Returns:
        LlamaIndex MetadataFilter 条件列表
    """
    filters = []

    # global 文档对所有用户可见
    filters.append({"key": "scope", "value": "global"})

    if user_id:
        filters.append({"key": "owner_id", "value": user_id})

    if enterprise_id:
        filters.append({"key": "owner_id", "value": enterprise_id})

    return filters


def split_knowledge_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> List[str]:
    """使用 LlamaIndex SentenceSplitter 分割文本

    Args:
        text: 原始文本
        chunk_size: 分块大小
        chunk_overlap: 分块重叠

    Returns:
        分块列表
    """
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core import Document

    if not text or not text.strip():
        return []

    splitter = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    nodes = splitter.get_nodes_from_documents(
        [Document(text=text)],
        show_progress=False,
    )
    return [node.get_content() for node in nodes if node.get_content().strip()]


class LlamaIndexKnowledgeService:
    """LlamaIndex 知识库服务

    封装 LlamaIndex 的索引、检索、删除能力，
    使用 PostgreSQL + pgvector 作为向量后端。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _get_connection_params() -> Dict[str, Any]:
        """从 database_url 提取 PostgreSQL 连接参数用于 PGVectorStore"""
        url = settings.database_url
        # postgresql+asyncpg://user[:pass]@host:port/dbname
        without_scheme = url.split("://", 1)[1]
        credentials, rest = without_scheme.rsplit("@", 1)
        try:
            user_pass = credentials.split(":", 1)
            user = user_pass[0]
            password = user_pass[1] if len(user_pass) > 1 else ""
        except Exception:
            user = credentials
            password = ""
        host_db = rest.split("/", 1)
        host_port = host_db[0].split(":", 1)
        return {
            "host": host_port[0],
            "port": int(host_port[1]) if len(host_port) > 1 else 5432,
            "user": user,
            "password": password,
            "database": host_db[1] if len(host_db) > 1 else "yibiao",
        }

    async def index_document(
        self,
        doc_id: uuid.UUID,
        text: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """索引文档到 LlamaIndex PostgreSQL 向量存储

        Args:
            doc_id: 文档 ID
            text: 文档全文
            metadata: 文档元数据

        Returns:
            是否成功
        """
        try:
            from llama_index.core import VectorStoreIndex, StorageContext, Document
            from llama_index.embeddings.ollama import OllamaEmbedding
            from llama_index.vector_stores.postgres import PGVectorStore

            # 创建嵌入模型
            embed_model = OllamaEmbedding(
                model_name=settings.embedding_model,
                base_url=settings.ollama_base_url,
            )

            # 创建 PostgreSQL 向量存储
            conn_params = self._get_connection_params()
            vector_store = PGVectorStore.from_params(
                **conn_params,
                table_name=settings.knowledge_vector_table,
                embed_dim=settings.embedding_dimension,
            )

            # 创建 LlamaIndex Document
            doc = Document(
                text=text,
                metadata=metadata,
                doc_id=str(doc_id),
            )

            # 分块并索引
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            index = VectorStoreIndex.from_documents(
                [doc],
                storage_context=storage_context,
                embed_model=embed_model,
                show_progress=False,
            )

            logger.info(f"LlamaIndex 索引完成: doc_id={doc_id}")
            return True

        except Exception as e:
            logger.error(f"LlamaIndex 索引失败: doc_id={doc_id}, error={str(e)}", exc_info=True)
            return False

    async def search(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = None,
        enterprise_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索

        Args:
            query: 查询文本
            top_k: 返回数量
            user_id: 用户 ID
            enterprise_id: 企业 ID

        Returns:
            搜索结果列表
        """
        try:
            from llama_index.core import VectorStoreIndex
            from llama_index.embeddings.ollama import OllamaEmbedding
            from llama_index.vector_stores.postgres import PGVectorStore

            # 创建嵌入模型
            embed_model = OllamaEmbedding(
                model_name=settings.embedding_model,
                base_url=settings.ollama_base_url,
            )

            # 创建向量存储并加载已有索引
            conn_params = self._get_connection_params()
            vector_store = PGVectorStore.from_params(
                **conn_params,
                table_name=settings.knowledge_vector_table,
                embed_dim=settings.embedding_dimension,
            )

            index = VectorStoreIndex.from_vector_store(
                vector_store,
                embed_model=embed_model,
            )

            # 使用 retriever 进行纯向量检索（不需要 LLM）
            retriever = index.as_retriever(similarity_top_k=top_k)
            nodes = await retriever.aretrieve(query)

            # 解析结果
            results = []
            for node_with_score in nodes:
                node_metadata = node_with_score.node.metadata or {}
                results.append({
                    "doc_id": node_metadata.get("doc_id", ""),
                    "content": node_with_score.node.get_content(),
                    "score": node_with_score.score or 0.0,
                    "title": node_metadata.get("title", ""),
                    "doc_type": node_metadata.get("doc_type", ""),
                    "metadata": node_metadata,
                })

            return results

        except Exception as e:
            logger.error(f"LlamaIndex 搜索失败: {str(e)}", exc_info=True)
            return []

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """删除文档的所有向量索引

        Args:
            doc_id: 文档 ID
        """
        try:
            # PGVectorStore 创建的表名为 data_{table_name}，doc_id 存储在 metadata_ ->> 'ref_doc_id'
            from sqlalchemy import text

            table = f"data_{settings.knowledge_vector_table}"
            await self.db.execute(
                text(f"DELETE FROM {table} WHERE metadata_ ->> 'doc_id' = :doc_id"),
                {"doc_id": str(doc_id)},
            )
            await self.db.commit()
            logger.info(f"LlamaIndex 删除完成: doc_id={doc_id}")

        except Exception as e:
            logger.error(f"LlamaIndex 删除失败: doc_id={doc_id}, error={str(e)}", exc_info=True)
