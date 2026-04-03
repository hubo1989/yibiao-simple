"""知识库检索服务 - 基于 LlamaIndex 向量索引"""
import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.knowledge import KnowledgeDoc, ProjectKnowledgeUsage
from .llamaindex_knowledge_service import LlamaIndexKnowledgeService

logger = logging.getLogger(__name__)


class KnowledgeRetrievalService:
    """知识库检索服务 - 使用 LlamaIndex 向量搜索"""

    def __init__(self, db: AsyncSession, openai_service=None):
        self.db = db
        self.openai_service = openai_service

    async def search_relevant_knowledge(
        self,
        chapter_title: str,
        chapter_description: str,
        parent_chapters: List[Dict[str, Any]],
        project_overview: str,
        user_id: Optional[uuid.UUID] = None,
        enterprise_id: Optional[uuid.UUID] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """检索相关知识库内容 - 使用 LlamaIndex 向量搜索"""
        # 构建查询文本
        query_text = f"{chapter_title}\n{chapter_description}"
        if project_overview:
            query_text = f"{project_overview}\n\n{query_text}"

        # 使用 LlamaIndex 向量搜索
        try:
            return await self.search_with_vector(
                query=query_text,
                top_k=top_k,
                user_id=user_id,
                enterprise_id=enterprise_id,
            )
        except Exception as e:
            logger.warning(f"向量搜索失败: {str(e)}，尝试关键词搜索")
            return await self._search_by_keywords(
                chapter_title, chapter_description, user_id, enterprise_id, top_k
            )

    async def search_with_vector(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[uuid.UUID] = None,
        enterprise_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """LlamaIndex 向量相似度搜索

        Args:
            query: 查询文本
            top_k: 返回数量
            user_id: 用户 ID
            enterprise_id: 企业 ID

        Returns:
            搜索结果列表
        """
        llamaindex_service = LlamaIndexKnowledgeService(self.db)

        vector_results = await llamaindex_service.search(
            query=query,
            top_k=top_k,
            user_id=str(user_id) if user_id else None,
            enterprise_id=str(enterprise_id) if enterprise_id else None,
        )

        if not vector_results:
            return []

        # 聚合为文档级别结果
        return await self._aggregate_vector_results(vector_results)

    async def _aggregate_vector_results(
        self,
        vector_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """聚合并返回文档级别的结果"""
        # 按 doc_id 分组，取最高分
        doc_scores: Dict[str, Dict[str, Any]] = {}
        for result in vector_results:
            doc_id = result.get("doc_id", "")
            if not doc_id:
                continue
            if doc_id not in doc_scores or result.get("score", 0) > doc_scores[doc_id].get("score", 0):
                doc_scores[doc_id] = result

        # 获取文档详情并丰富结果
        results = []
        for doc_id, data in doc_scores.items():
            try:
                doc_result = await self.db.execute(
                    select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
                )
                doc_obj = doc_result.scalar_one_or_none()
            except (ValueError, Exception):
                doc_obj = None

            if doc_obj:
                results.append({
                    "id": str(doc_obj.id),
                    "doc_id": str(doc_obj.id),
                    "title": doc_obj.title,
                    "doc_type": doc_obj.doc_type.value if hasattr(doc_obj.doc_type, "value") else doc_obj.doc_type,
                    "relevance_score": data.get("score", 0.0),
                    "matched_nodes": [],
                    "content_preview": data.get("content", "")[:200],
                    "reasoning": "向量相似度匹配",
                })
            else:
                # 没有文档记录但向量搜索命中的，直接用节点数据
                results.append({
                    "id": doc_id,
                    "doc_id": doc_id,
                    "title": data.get("title", ""),
                    "doc_type": data.get("doc_type", ""),
                    "relevance_score": data.get("score", 0.0),
                    "matched_nodes": [],
                    "content_preview": data.get("content", "")[:200],
                    "reasoning": "向量相似度匹配",
                })

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results

    async def _search_by_keywords(
        self,
        chapter_title: str,
        chapter_description: str,
        user_id: Optional[uuid.UUID],
        enterprise_id: Optional[uuid.UUID],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """关键词搜索作为备用方案"""
        conditions = [KnowledgeDoc.scope == "global"]
        if user_id:
            conditions.append(KnowledgeDoc.owner_id == user_id)
        if enterprise_id:
            conditions.append(KnowledgeDoc.owner_id == enterprise_id)

        query = select(KnowledgeDoc).where(
            KnowledgeDoc.vector_index_status == "completed",
            or_(*conditions)
        ).order_by(KnowledgeDoc.usage_count.desc()).limit(top_k * 2)

        result = await self.db.execute(query)
        docs = result.scalars().all()

        keywords = set(chapter_title.lower().split())
        if chapter_description:
            keywords.update(chapter_description.lower().split())

        scored_docs = []
        for doc in docs:
            score = 0
            doc_text = f"{doc.title} {doc.content or ''}".lower()
            for kw in keywords:
                if kw in doc_text and len(kw) > 1:
                    score += 1

            if score > 0:
                scored_docs.append({
                    "id": str(doc.id),
                    "doc_id": str(doc.id),
                    "title": doc.title,
                    "doc_type": doc.doc_type.value if hasattr(doc.doc_type, "value") else doc.doc_type,
                    "relevance_score": score / max(len(keywords), 1),
                    "matched_nodes": [],
                    "content_preview": (doc.content or "")[:200],
                    "reasoning": "关键词匹配",
                })

        scored_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored_docs[:top_k]

    async def search(
        self,
        query: str,
        top_k: int = 5,
        doc_types: Optional[List[str]] = None,
        scope: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """通用搜索接口（供 /api/knowledge/search 使用）"""
        try:
            llamaindex_service = LlamaIndexKnowledgeService(self.db)
            vector_results = await llamaindex_service.search(
                query=query,
                top_k=top_k,
                user_id=str(user_id) if user_id else None,
            )

            if vector_results:
                return [
                    {
                        "doc_id": r.get("doc_id", ""),
                        "title": r.get("title", ""),
                        "content": r.get("content", ""),
                        "score": r.get("score", 0.0),
                        "metadata": r.get("metadata", {}),
                    }
                    for r in vector_results
                ]

        except Exception as e:
            logger.warning(f"LlamaIndex 搜索失败: {str(e)}")

        # 回退到关键词搜索
        return await self._search_by_keywords(
            chapter_title=query,
            chapter_description="",
            user_id=user_id,
            enterprise_id=None,
            top_k=top_k,
        )

    async def get_knowledge_content(self, knowledge_id: uuid.UUID) -> str:
        """获取知识库条目的完整内容"""
        result = await self.db.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == knowledge_id)
        )
        doc = result.scalar_one_or_none()

        if not doc:
            raise ValueError(f"知识库条目不存在: {knowledge_id}")

        if doc.content:
            return doc.content

        return ""

    async def record_usage(
        self,
        project_id: uuid.UUID,
        knowledge_id: uuid.UUID,
        chapter_id: str,
    ) -> None:
        """记录知识库使用情况"""
        usage = ProjectKnowledgeUsage(
            project_id=project_id,
            knowledge_doc_id=knowledge_id,
            chapter_id=chapter_id,
        )
        self.db.add(usage)

        result = await self.db.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == knowledge_id)
        )
        doc = result.scalar_one_or_none()
        if doc:
            doc.usage_count += 1
            doc.last_used_at = datetime.utcnow()

        await self.db.flush()

    async def get_popular_knowledge(
        self,
        limit: int = 10,
        user_id: Optional[uuid.UUID] = None,
        enterprise_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """获取热门知识库条目"""
        query = select(KnowledgeDoc).where(
            KnowledgeDoc.vector_index_status == "completed"
        )

        conditions = [KnowledgeDoc.scope == "global"]
        if user_id:
            conditions.append(KnowledgeDoc.owner_id == user_id)
        if enterprise_id:
            conditions.append(KnowledgeDoc.owner_id == enterprise_id)

        query = query.where(or_(*conditions))
        query = query.order_by(KnowledgeDoc.usage_count.desc())
        query = query.limit(limit)

        result = await self.db.execute(query)
        docs = result.scalars().all()

        return [
            {
                "id": str(doc.id),
                "title": doc.title,
                "doc_type": doc.doc_type.value if hasattr(doc.doc_type, "value") else doc.doc_type,
                "usage_count": doc.usage_count,
                "tags": doc.tags or [],
                "category": doc.category,
            }
            for doc in docs
        ]
