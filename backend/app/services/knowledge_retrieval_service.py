"""知识库检索服务 - 基于 PageIndex 的智能检索"""
import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.knowledge import KnowledgeDoc, ProjectKnowledgeUsage, IndexStatus
from .openai_service import OpenAIService
from .vector_index_service import VectorIndexService

logger = logging.getLogger(__name__)


class KnowledgeRetrievalService:
    """知识库检索服务 - 使用 PageIndex 树搜索和 LLM 推理"""

    def __init__(self, db: AsyncSession, openai_service: OpenAIService):
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
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        检索相关知识库内容 - 优先使用向量搜索

        Args:
            chapter_title: 章节标题
            chapter_description: 章节描述
            parent_chapters: 上级章节信息
            project_overview: 项目概述
            user_id: 用户ID
            enterprise_id: 企业ID（可选）
            top_k: 返回前K个最相关的结果

        Returns:
            推荐的知识库条目列表
        """
        # 构建查询文本
        query_text = f"{chapter_title}\n{chapter_description}"
        if project_overview:
            query_text = f"{project_overview}\n\n{query_text}"

        # 优先使用向量搜索
        try:
            return await self.search_with_vector(
                query=query_text,
                top_k=top_k,
                user_id=user_id,
                enterprise_id=enterprise_id,
                use_pageindex_fallback=False  # 不回退到 PageIndex
            )
        except Exception as e:
            logger.warning(f"向量搜索失败: {str(e)}，尝试关键词搜索")
            # 回退到简单的关键词匹配
            return await self._search_by_keywords(
                chapter_title, chapter_description, user_id, enterprise_id, top_k
            )

    async def _search_by_keywords(
        self,
        chapter_title: str,
        chapter_description: str,
        user_id: Optional[uuid.UUID],
        enterprise_id: Optional[uuid.UUID],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """关键词搜索作为备用方案"""
        # 获取可访问的文档
        conditions = [KnowledgeDoc.scope == 'global']
        if user_id:
            conditions.append(KnowledgeDoc.owner_id == user_id)
        if enterprise_id:
            conditions.append(KnowledgeDoc.owner_id == enterprise_id)

        query = select(KnowledgeDoc).where(
            KnowledgeDoc.vector_index_status == 'completed',
            or_(*conditions)
        ).order_by(KnowledgeDoc.usage_count.desc()).limit(top_k * 2)

        result = await self.db.execute(query)
        docs = result.scalars().all()

        # 简单的关键词匹配
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
                    'id': str(doc.id),
                    'title': doc.title,
                    'doc_type': doc.doc_type.value if hasattr(doc.doc_type, 'value') else doc.doc_type,
                    'relevance_score': score / max(len(keywords), 1),
                    'matched_nodes': [],
                    'content_preview': (doc.content or '')[:200],
                    'reasoning': '关键词匹配'
                })

        scored_docs.sort(key=lambda x: x['relevance_score'], reverse=True)
        return scored_docs[:top_k]

    async def _search_in_pageindex_tree(
        self,
        pageindex_tree: dict,
        chapter_title: str,
        chapter_description: str,
        parent_chapters: List[Dict[str, Any]],
        project_overview: str
    ) -> dict:
        """
        在 PageIndex 树中进行推理搜索

        使用 LLM 模拟人类专家浏览文档的方式：
        1. 查看根节点的标题和摘要
        2. 推理哪些子节点可能包含相关信息
        3. 递归搜索，直到找到最相关的内容
        """

        # 构建搜索提示词
        prompt = f"""你是一位专业的标书编写专家。请根据以下章节信息，判断知识库内容是否相关。

## 目标章节信息
- 标题: {chapter_title}
- 描述: {chapter_description or '无'}
- 上级章节: {json.dumps(parent_chapters, ensure_ascii=False) if parent_chapters else '无'}
- 项目概述: {project_overview}

## 知识库树状索引
{json.dumps(pageindex_tree, ensure_ascii=False, indent=2)}

## 任务
1. 分析目标章节需要什么样的知识库内容
2. 在上面的树状索引中搜索最相关的节点
3. 返回以下信息（JSON格式，不要有其他说明）：
{{
  "score": 0.0-1.0,
  "reasoning": "判断理由",
  "matched_nodes": [
    {{
      "node_id": "节点ID",
      "title": "节点标题",
      "relevance": "为什么这个节点相关"
    }}
  ],
  "content_preview": "最相关内容的预览（前200字）"
}}

只返回JSON，不要有其他说明文字。"""

        # 调用 LLM
        messages = [
            {"role": "system", "content": "你是一位专业的标书知识库检索专家。"},
            {"role": "user", "content": prompt}
        ]

        try:
            response = await self.openai_service._collect_stream_text(
                messages,
                temperature=0.3
            )

            # 解析 JSON 结果
            # 尝试提取 JSON（可能包含在 markdown 代码块中）
            json_str = response.strip()
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0].strip()

            result = json.loads(json_str)
            return result

        except json.JSONDecodeError as e:
            logger.error(f"解析 LLM 响应失败: {str(e)}\n响应内容: {response[:500]}")
            return {
                "score": 0.0,
                "reasoning": "解析失败",
                "matched_nodes": [],
                "content_preview": ""
            }
        except Exception as e:
            logger.error(f"调用 LLM 失败: {str(e)}", exc_info=True)
            return {
                "score": 0.0,
                "reasoning": f"错误: {str(e)}",
                "matched_nodes": [],
                "content_preview": ""
            }

    async def get_knowledge_content(self, knowledge_id: uuid.UUID) -> str:
        """
        获取知识库条目的完整内容

        Args:
            knowledge_id: 知识库条目ID

        Returns:
            完整内容文本
        """
        result = await self.db.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == knowledge_id)
        )
        doc = result.scalar_one_or_none()

        if not doc:
            raise ValueError(f"知识库条目不存在: {knowledge_id}")

        # 对于手动输入的内容，直接返回
        if doc.content:
            return doc.content

        # 对于文件来源，从 PageIndex 树中提取所有内容
        if doc.pageindex_tree:
            return self._extract_content_from_tree(doc.pageindex_tree)

        return ""

    def _extract_content_from_tree(self, tree: dict) -> str:
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

    async def record_usage(
        self,
        project_id: uuid.UUID,
        knowledge_id: uuid.UUID,
        chapter_id: str
    ) -> None:
        """
        记录知识库使用情况

        Args:
            project_id: 项目ID
            knowledge_id: 知识库条目ID
            chapter_id: 章节ID
        """
        # 创建使用记录
        usage = ProjectKnowledgeUsage(
            project_id=project_id,
            knowledge_doc_id=knowledge_id,
            chapter_id=chapter_id
        )
        self.db.add(usage)

        # 更新知识库条目的统计信息
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
        enterprise_id: Optional[uuid.UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        获取热门知识库条目

        Args:
            limit: 返回数量限制
            user_id: 用户ID
            enterprise_id: 企业ID

        Returns:
            热门知识库条目列表
        """
        query = select(KnowledgeDoc).where(
            KnowledgeDoc.vector_index_status == 'completed'
        )

        # 权限过滤
        conditions = [KnowledgeDoc.scope == 'global']
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
                'id': str(doc.id),
                'title': doc.title,
                'doc_type': doc.doc_type.value if hasattr(doc.doc_type, 'value') else doc.doc_type,
                'usage_count': doc.usage_count,
                'tags': doc.tags or [],
                'category': doc.category
            }
            for doc in docs
        ]

    async def search_with_vector(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[uuid.UUID] = None,
        enterprise_id: Optional[uuid.UUID] = None,
        use_pageindex_fallback: bool = True
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索，失败时回退到 PageIndex

        Args:
            query: 查询文本
            top_k: 返回数量
            user_id: 用户ID
            enterprise_id: 企业ID
            use_pageindex_fallback: 是否在向量搜索失败时回退到 PageIndex

        Returns:
            搜索结果列表
        """
        from .vector_index_service import VectorIndexService

        try:
            # 1. 获取可访问的文档ID列表
            accessible_doc_ids = await self._get_accessible_doc_ids(user_id, enterprise_id)

            if not accessible_doc_ids:
                return []

            # 2. 向量搜索
            vector_service = VectorIndexService(self.db)
            vector_results = await vector_service.search_similar(
                query=query,
                top_k=top_k,
                doc_ids=accessible_doc_ids
            )

            if vector_results:
                # 聚合结果，返回文档级别
                return await self._aggregate_vector_results(vector_results)

            # 3. 向量搜索无结果，回退到 PageIndex
            if use_pageindex_fallback:
                logger.info("向量搜索无结果，回退到 PageIndex")
                return await self.search_relevant_knowledge(
                    chapter_title=query,
                    chapter_description="",
                    parent_chapters=[],
                    project_overview="",
                    user_id=user_id,
                    enterprise_id=enterprise_id,
                    top_k=top_k
                )

            return []

        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}", exc_info=True)

            # 回退到 PageIndex
            if use_pageindex_fallback:
                logger.info("向量搜索异常，回退到 PageIndex")
                return await self.search_relevant_knowledge(
                    chapter_title=query,
                    chapter_description="",
                    parent_chapters=[],
                    project_overview="",
                    user_id=user_id,
                    enterprise_id=enterprise_id,
                    top_k=top_k
                )

            return []

    async def _get_accessible_doc_ids(
        self,
        user_id: Optional[uuid.UUID],
        enterprise_id: Optional[uuid.UUID]
    ) -> List[uuid.UUID]:
        """获取用户可访问的文档ID列表（基于向量索引状态）"""
        conditions = [KnowledgeDoc.scope == 'global']
        if user_id:
            conditions.append(KnowledgeDoc.owner_id == user_id)
        if enterprise_id:
            conditions.append(KnowledgeDoc.owner_id == enterprise_id)

        query = select(KnowledgeDoc.id).where(
            KnowledgeDoc.vector_index_status == 'completed',
            or_(*conditions)
        )

        result = await self.db.execute(query)
        return [row[0] for row in result.fetchall()]

    async def _aggregate_vector_results(
        self,
        vector_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """聚合并返回文档级别的结果"""
        # 按 doc_id 分组，取最高分
        doc_scores = {}
        for result in vector_results:
            doc_id = result['doc_id']
            if doc_id not in doc_scores or result['score'] > doc_scores[doc_id]['score']:
                doc_scores[doc_id] = result

        # 获取文档详情
        results = []
        for doc_id, data in doc_scores.items():
            doc = await self.db.execute(
                select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
            )
            doc_obj = doc.scalar_one_or_none()
            if doc_obj:
                results.append({
                    'id': str(doc_obj.id),
                    'title': doc_obj.title,
                    'doc_type': doc_obj.doc_type.value if hasattr(doc_obj.doc_type, 'value') else doc_obj.doc_type,
                    'relevance_score': data['score'],
                    'matched_nodes': [],
                    'content_preview': data['content'][:200] if data.get('content') else '',
                    'reasoning': '向量相似度匹配'
                })

        # 按分数排序
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results
