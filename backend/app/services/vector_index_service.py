"""向量索引服务 - 基于 LlamaIndex + pgvector"""
import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.knowledge import KnowledgeDoc, KnowledgeDocChunk, IndexStatus
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

# 分块配置
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50


class VectorIndexService:
    """向量索引服务

    使用 LlamaIndex 分块 + Ollama 嵌入 + pgvector 存储
    """

    def __init__(self, db: AsyncSession, embedding_service: Optional[EmbeddingService] = None):
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()

    async def process_document(self, doc_id: uuid.UUID, content: str) -> bool:
        """处理文档：分块 -> 生成嵌入 -> 存储

        Args:
            doc_id: 文档ID
            content: 文档内容

        Returns:
            是否成功
        """
        try:
            # 1. 分块
            chunks = self._split_text(content)
            logger.info(f"文档 {doc_id} 分块完成，共 {len(chunks)} 个分块")

            # 2. 生成嵌入
            embeddings = await self.embedding_service.get_embeddings(chunks)

            # 3. 存储到数据库
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                if embedding is None:
                    logger.warning(f"分块 {i} 嵌入生成失败，跳过")
                    continue

                chunk_record = KnowledgeDocChunk(
                    doc_id=doc_id,
                    chunk_index=i,
                    content=chunk,
                    embedding=json.dumps(embedding),  # 存储为 JSON 字符串
                    chunk_metadata={"chunk_size": len(chunk)}
                )
                self.db.add(chunk_record)

            await self.db.commit()
            logger.info(f"文档 {doc_id} 向量索引完成")
            return True

        except Exception as e:
            logger.error(f"向量索引失败: {str(e)}", exc_info=True)
            await self.db.rollback()
            return False

    def _split_text(self, text: str) -> List[str]:
        """简单分块实现（可替换为 LlamaIndex SentenceSplitter）

        Args:
            text: 原始文本

        Returns:
            分块列表
        """
        # 简单按段落和长度分块
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) < CHUNK_SIZE:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def search_similar(
        self,
        query: str,
        top_k: int = 5,
        doc_ids: Optional[List[uuid.UUID]] = None
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索

        Args:
            query: 查询文本
            top_k: 返回数量
            doc_ids: 限制搜索的文档ID列表

        Returns:
            相似分块列表，包含 doc_id, content, score
        """
        try:
            # 1. 获取查询嵌入
            query_embedding = await self.embedding_service.get_embedding(query)
            if query_embedding is None:
                logger.error("查询嵌入生成失败")
                return []

            # 2. 数据库向量搜索
            # 使用原始 SQL 进行向量相似度搜索
            query_embedding_json = json.dumps(query_embedding)

            sql = """
                SELECT
                    doc_id,
                    content,
                    metadata,
                    1 - (embedding::jsonb::text::vector <=> :query_embedding::text::vector) as score
                FROM knowledge_doc_chunks
                WHERE 1=1
            """
            params = {"query_embedding": query_embedding_json}

            if doc_ids:
                placeholders = ", ".join([f":doc_id_{i}" for i in range(len(doc_ids))])
                sql += f" AND doc_id IN ({placeholders})"
                for i, doc_id in enumerate(doc_ids):
                    params[f"doc_id_{i}"] = str(doc_id)

            sql += " ORDER BY score DESC LIMIT :limit"
            params["limit"] = top_k

            result = await self.db.execute(text(sql), params)
            rows = result.fetchall()

            return [
                {
                    "doc_id": str(row[0]),
                    "content": row[1],
                    "chunk_metadata": row[2],
                    "score": float(row[3])
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}", exc_info=True)
            return []

    async def delete_document_chunks(self, doc_id: uuid.UUID) -> None:
        """删除文档的所有分块"""
        await self.db.execute(
            delete(KnowledgeDocChunk).where(KnowledgeDocChunk.doc_id == doc_id)
        )
        await self.db.commit()
        logger.info(f"已删除文档 {doc_id} 的所有分块")
