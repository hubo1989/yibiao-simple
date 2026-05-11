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


def _suggest_material_placement(
    chapter_content: str,
    material: Any,
    mapped_category: str,
) -> str:
    """根据章节内容和素材类型建议插入位置"""
    if not chapter_content:
        return "章节末尾"

    paragraphs = [p.strip() for p in chapter_content.split("\n\n") if p.strip()]

    # 为不同类型寻找最匹配的段落
    placement_hints = {
        "资质证书": ["资质", "认证", "许可证", "资格", "证书", "标准"],
        "项目案例": ["案例", "经验", "项目", "业绩", "类似"],
        "产品规格": ["产品", "规格", "技术参数", "性能", "配置"],
        "组织架构": ["团队", "组织", "人员", "架构", "管理"],
    }

    hints = placement_hints.get(mapped_category, [])

    for i, para in enumerate(paragraphs):
        if any(hint in para for hint in hints):
            return f"第{i + 1}段「{material.name}」之后"

    return "章节末尾"


class KnowledgeRetrievalService:
    """知识库检索服务 - 使用 LlamaIndex 向量搜索"""

    def __init__(self, db: AsyncSession, openai_service=None):
        self.db = db
        self.openai_service = openai_service

    async def retrieve_for_chapter(
        self,
        chapter_title: str,
        chapter_description: str = "",
        parent_chapters: Optional[List[Dict[str, Any]]] = None,
        project_overview: str = "",
        user_id: Optional[uuid.UUID] = None,
        enterprise_id: Optional[uuid.UUID] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """统一的章节知识库检索入口

        供 content.py 和 outline.py 共同调用，确保检索逻辑一致。

        Args:
            chapter_title: 章节标题
            chapter_description: 章节描述
            parent_chapters: 上级章节列表
            project_overview: 项目概述（可选，用于增强查询）
            user_id: 用户 ID（权限过滤）
            enterprise_id: 企业 ID（权限过滤）
            top_k: 返回数量

        Returns:
            搜索结果列表
        """
        return await self.search_relevant_knowledge(
            chapter_title=chapter_title,
            chapter_description=chapter_description,
            parent_chapters=parent_chapters or [],
            project_overview=project_overview,
            user_id=user_id,
            enterprise_id=enterprise_id,
            top_k=top_k,
        )

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

    async def retrieve_materials_for_chapter(
        self,
        chapter_title: str,
        chapter_content: str,
        top_k: int = 3,
        user_id: Optional[uuid.UUID] = None,
        enterprise_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """检索素材库中匹配的资质证书和项目案例

        基于章节标题和已生成内容的摘要，使用向量搜索匹配素材库。
        素材类别映射：
        - certificate 类：qualification_cert, award_cert, iso_cert, business_license
        - case_study 类：project_case, contract_sample
        - product_spec 类：equipment_photo
        - org_chart 类：team_photo

        Args:
            chapter_title: 章节标题
            chapter_content: 已生成章节内容
            top_k: 返回数量
            user_id: 用户 ID
            enterprise_id: 企业 ID

        Returns:
            匹配的素材列表，每项包含：
            {id, name, category, mapped_category, relevance_score, suggested_placement}
        """
        from ..models.material import MaterialAsset, MaterialCategory

        # 类别映射：MaterialCategory → 简化类别名
        CATEGORY_MAP = {
            "qualification_cert": "资质证书",
            "award_cert": "资质证书",
            "iso_cert": "资质证书",
            "business_license": "资质证书",
            "project_case": "项目案例",
            "contract_sample": "项目案例",
            "equipment_photo": "产品规格",
            "team_photo": "组织架构",
            "financial_report": "其他",
            "bank_credit": "其他",
            "social_security": "其他",
            "legal_person_id": "资质证书",
            "other": "其他",
        }

        # 构建查询文本：章节标题 + 内容摘要（前 1000 字符）
        content_summary = chapter_content[:1000] if chapter_content else ""
        query_text = f"{chapter_title}\n{content_summary}"

        results = []

        try:
            # 使用 LlamaIndex 向量搜索
            llamaindex_service = LlamaIndexKnowledgeService(self.db)
            vector_results = await llamaindex_service.search(
                query=query_text,
                top_k=top_k * 2,  # 多取一些，后续过滤
                user_id=str(user_id) if user_id else None,
                enterprise_id=str(enterprise_id) if enterprise_id else None,
            )

            if vector_results:
                # 从向量搜索结果中提取文档 ID，精准关联素材
                doc_ids = set()
                for vr in vector_results:
                    did = vr.get("doc_id", "")
                    if did:
                        doc_ids.add(did)

                if doc_ids:
                    # 用 source_document_id 精准查询，而非加载全部素材
                    doc_uuids = []
                    for did in doc_ids:
                        try:
                            doc_uuids.append(uuid.UUID(did))
                        except ValueError:
                            continue

                    if doc_uuids:
                        mat_result = await self.db.execute(
                            select(MaterialAsset).where(
                                MaterialAsset.is_disabled == False,
                                MaterialAsset.is_expired == False,
                                MaterialAsset.source_document_id.in_(doc_uuids),
                            )
                        )
                        matched_materials = mat_result.scalars().all()

                        for mat in matched_materials:
                            category_value = mat.category.value if hasattr(mat.category, "value") else str(mat.category)
                            mapped = CATEGORY_MAP.get(category_value, "其他")
                            placement = _suggest_material_placement(chapter_content, mat, mapped)

                            results.append({
                                "id": str(mat.id),
                                "name": mat.name,
                                "category": category_value,
                                "mapped_category": mapped,
                                "relevance_score": 0.8,  # 向量命中为高相关度
                                "suggested_placement": placement,
                            })

        except Exception as e:
            logger.warning(f"素材向量搜索失败: {e}，使用关键词回退")

        # 如果向量搜索没有结果，使用关键词回退
        if not results:
            results = await self._search_materials_by_keywords(
                query_text, top_k, user_id, enterprise_id, chapter_content, CATEGORY_MAP
            )

        # 去重（按 id）
        seen = set()
        unique_results = []
        for r in results:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique_results.append(r)

        return unique_results[:top_k]

    async def _search_materials_by_keywords(
        self,
        query_text: str,
        top_k: int,
        user_id: Optional[uuid.UUID],
        enterprise_id: Optional[uuid.UUID],
        chapter_content: str,
        category_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """关键词回退搜索素材"""
        from ..models.material import MaterialAsset

        query = select(MaterialAsset).where(
            MaterialAsset.is_disabled == False,
            MaterialAsset.is_expired == False,
        )
        result = await self.db.execute(query)
        materials = result.scalars().all()

        keywords = set(query_text.lower().split())
        scored = []
        for mat in materials:
            mat_text = f"{mat.name} {mat.description or ''} {mat.ai_description or ''}".lower()
            mat_tags = " ".join(mat.tags or []).lower()
            mat_keywords = " ".join(mat.keywords or []).lower()
            combined = f"{mat_text} {mat_tags} {mat_keywords}"

            score = 0
            for kw in keywords:
                if len(kw) > 1 and kw in combined:
                    score += 1

            if score > 0:
                scored.append((mat, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for mat, score in scored[:top_k]:
            category_value = mat.category.value if hasattr(mat.category, "value") else str(mat.category)
            mapped = category_map.get(category_value, "其他")
            placement = _suggest_material_placement(chapter_content, mat, mapped)
            results.append({
                "id": str(mat.id),
                "name": mat.name,
                "category": category_value,
                "mapped_category": mapped,
                "relevance_score": round(score / max(len(keywords), 1), 2),
                "suggested_placement": placement,
            })

        return results

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
