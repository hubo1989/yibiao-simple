"""标书审查业务逻辑服务"""
import asyncio
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.bid_review_task import BidReviewTask, ReviewTaskStatus
from ..models.project import Project
from ..services.openai_service import OpenAIService
from ..services.prompt_service import PromptService
from ..utils.json_util import check_json, repair_truncated_json

# 响应性审查 JSON Schema
RESPONSIVENESS_RESULT_SCHEMA = {
    "items": [
        {
            "rating_item": "评分项名称（含分值）",
            "score": 0,
            "max_score": 0,
            "coverage_status": "covered|partial|missing|risk",
            "evidence": "投标文件中找到的证据描述",
            "source_refs": [
                {
                    "ref_id": "引用ID",
                    "source_type": "tender_document",
                    "location": "招标文件中的位置",
                    "quote": "招标文件原文引用",
                    "relation": "与投标文件的关联说明"
                }
            ],
            "issues": ["问题1", "问题2"],
            "suggestions": ["建议1", "建议2"],
            "rewrite_suggestions": ["参考改写建议"],
            "chapter_targets": ["涉及章节"],
            "confidence": "high|medium|low"
        }
    ]
}

# 合规性审查 JSON Schema
COMPLIANCE_RESULT_SCHEMA = {
    "items": [
        {
            "compliance_category": "格式要求|资质要求|签署要求|排他条款|报价要求",
            "clause_text": "招标条款原文",
            "check_result": "pass|warning|fail",
            "detail": "详细检查说明",
            "bid_location": "投标文件中的位置",
            "severity": "critical|warning|info",
            "suggestion": "修改建议"
        }
    ]
}

# 一致性审查 JSON Schema
CONSISTENCY_RESULT_SCHEMA = {
    "contradictions": [
        {
            "severity": "critical|warning|info",
            "category": "data|terminology|timeline|commitment|scope",
            "description": "矛盾描述",
            "chapter_a": "章节A编号和标题",
            "detail_a": "章节A中的内容",
            "chapter_b": "章节B编号和标题",
            "detail_b": "章节B中的内容",
            "suggestion": "修改建议"
        }
    ]
}


class ReviewService:
    """标书审查服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _create_openai_service(
        self,
        project_id: uuid.UUID,
        model_name: str | None = None,
        provider_config_id: uuid.UUID | None = None,
    ) -> OpenAIService:
        """创建并初始化 OpenAI 服务"""
        svc = OpenAIService(db=self.db, project_id=project_id)
        if provider_config_id:
            configured = await svc.use_config_by_id(str(provider_config_id))
            if not configured:
                raise ValueError("所选 Provider 配置不存在")
        else:
            await svc._ensure_initialized()

        if not svc.api_key:
            raise ValueError("请先配置 API 密钥")

        if model_name:
            svc.set_model(model_name)

        return svc

    async def _prefetch_prompts(
        self, project_id: uuid.UUID, scene_keys: list[str]
    ) -> dict[str, tuple[str, str]]:
        """预加载所有维度的 prompt，避免 asyncio.gather 中共享 AsyncSession"""
        prompt_service = PromptService(self.db)
        result: dict[str, tuple[str, str]] = {}
        for key in scene_keys:
            prompt, _ = await prompt_service.get_prompt(key, project_id)
            result[key] = PromptService.split_prompt(prompt)
        return result

    async def _run_dimension(
        self,
        openai_service: OpenAIService,
        scene_key: str,
        schema: dict,
        user_content: str,
        system_prompt: str,
        user_template: str,
        temperature: float = 0.3,
    ) -> dict | None:
        """执行单维度审查，返回解析后的 JSON 结果"""
        try:
            prompt_service = PromptService(self.db)
            user_prompt = prompt_service.render_prompt(
                user_template, {"content": user_content}
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            full_content = await openai_service._generate_with_json_check(
                messages,
                schema=schema,
                temperature=temperature,
                log_prefix=f"[Review:{scene_key}]",
                raise_on_fail=False,
            )

            if not full_content:
                return None

            parsed = json.loads(full_content)
            return parsed

        except Exception as e:
            print(f"[Review:{scene_key}] 审查失败: {e}")
            return None

    async def _run_responsiveness_check(
        self,
        openai_service: OpenAIService,
        project: Project,
        bid_content: str,
        system_prompt: str,
        user_template: str,
        knowledge_context: str = "",
    ) -> dict:
        """执行响应性审查"""
        sections = []
        if project.tech_requirements:
            sections.append(f"### 技术评分要求\n{project.tech_requirements}")
        if project.project_overview:
            sections.append(f"### 项目概述\n{project.project_overview}")

        sections.append(f"### 投标文件内容\n{bid_content}")
        if knowledge_context:
            sections.append(f"### 参考知识库内容\n{knowledge_context}")

        user_content = "\n\n".join(sections)
        result = await self._run_dimension(
            openai_service,
            "bid_review_responsiveness",
            RESPONSIVENESS_RESULT_SCHEMA,
            user_content,
            system_prompt,
            user_template,
        )
        return result or {"items": []}

    async def _run_compliance_check(
        self,
        openai_service: OpenAIService,
        project: Project,
        bid_content: str,
        system_prompt: str,
        user_template: str,
    ) -> dict:
        """执行合规性审查"""
        sections = []
        if project.file_content:
            sections.append(f"### 招标文件（合规相关）\n{project.file_content}")
        sections.append(f"### 投标文件内容\n{bid_content}")

        user_content = "\n\n".join(sections)
        result = await self._run_dimension(
            openai_service,
            "bid_review_compliance",
            COMPLIANCE_RESULT_SCHEMA,
            user_content,
            system_prompt,
            user_template,
        )
        return result or {"items": []}

    async def _run_consistency_check(
        self,
        openai_service: OpenAIService,
        bid_content: str,
        system_prompt: str,
        user_template: str,
        project_overview: str = "",
    ) -> dict:
        """执行一致性审查"""
        user_content = f"### 投标文件内容\n{bid_content}"
        if project_overview:
            user_content += f"\n\n### 项目概述\n{project_overview}"

        result = await self._run_dimension(
            openai_service,
            "bid_review_consistency",
            CONSISTENCY_RESULT_SCHEMA,
            user_content,
            system_prompt,
            user_template,
        )
        return result or {"contradictions": []}

    @staticmethod
    def generate_summary(
        responsiveness: dict | None,
        compliance: dict | None,
        consistency: dict | None,
        failed_dimensions: list[str] | None = None,
    ) -> dict:
        """根据三维度审查结果生成汇总"""
        failed_dims = set(failed_dimensions or [])

        # 响应性统计
        resp_items = responsiveness.get("items", []) if responsiveness else []
        total_score = sum(item.get("max_score", 0) for item in resp_items)
        earned_score = sum(item.get("score", 0) for item in resp_items)
        covered_count = sum(
            1 for item in resp_items if item.get("coverage_status") in ("covered", "partial")
        )
        coverage_rate = covered_count / len(resp_items) if resp_items else 0.0

        # 问题统计
        issue_distribution = {"critical": 0, "warning": 0, "info": 0}

        # 响应性问题
        for item in resp_items:
            status = item.get("coverage_status", "missing")
            if status == "missing":
                issue_distribution["critical"] += 1
            elif status == "risk":
                issue_distribution["warning"] += 1

        # 合规性问题
        comp_items = compliance.get("items", []) if compliance else []
        for item in comp_items:
            severity = item.get("severity", "info")
            if severity in issue_distribution:
                issue_distribution[severity] += 1

        # 一致性问题
        contradictions = consistency.get("contradictions", []) if consistency else []
        for item in contradictions:
            severity = item.get("severity", "info")
            if severity in issue_distribution:
                issue_distribution[severity] += 1

        total_issues = sum(issue_distribution.values())

        # 风险等级
        critical_count = issue_distribution["critical"]
        if critical_count >= 3 or coverage_rate < 0.5:
            risk_level = "high"
        elif critical_count >= 1 or coverage_rate < 0.8:
            risk_level = "medium"
        else:
            risk_level = "low"

        # 综合得分 — 仅对成功执行的维度计分，按实际维度数归一化
        dim_weights: list[tuple[str, float]] = []
        if "responsiveness" not in failed_dims:
            dim_weights.append(("responsiveness", 0.7))
        if "compliance" not in failed_dims:
            dim_weights.append(("compliance", 0.15))
        if "consistency" not in failed_dims:
            dim_weights.append(("consistency", 0.15))

        if not dim_weights:
            return {
                "overall_score": 0,
                "score_max": 100,
                "coverage_rate": round(coverage_rate, 2),
                "risk_level": risk_level,
                "total_issues": total_issues,
                "issue_distribution": issue_distribution,
            }

        # 归一化权重使总和为 1
        total_weight = sum(w for _, w in dim_weights)
        normalized = [(name, weight / total_weight) for name, weight in dim_weights]

        score_parts = 0.0
        for dim_name, weight in normalized:
            if dim_name == "responsiveness":
                if total_score > 0:
                    score_parts += (earned_score / total_score) * weight
                else:
                    # 无评分项时视为满分
                    score_parts += weight
            elif dim_name == "compliance":
                if comp_items:
                    pass_count = sum(1 for i in comp_items if i.get("check_result") == "pass")
                    score_parts += (pass_count / len(comp_items)) * weight
            elif dim_name == "consistency":
                if contradictions:
                    score_parts += max(0, 1 - len(contradictions) * 0.2) * weight
                else:
                    score_parts += weight

        overall_score = min(100, int(score_parts * 100))

        return {
            "overall_score": overall_score,
            "score_max": 100,
            "coverage_rate": round(coverage_rate, 2),
            "risk_level": risk_level,
            "total_issues": total_issues,
            "issue_distribution": issue_distribution,
        }

    async def execute_review(
        self,
        task_id: uuid.UUID,
        dimensions: list[str],
        scope: str = "full",
        chapter_ids: list[str] | None = None,
        model_name: str | None = None,
        provider_config_id: uuid.UUID | None = None,
        use_knowledge: bool = False,
        knowledge_ids: list[str] | None = None,
    ) -> dict:
        """
        执行审查任务（同步，由 SSE 端点调用）。

        Returns:
            dict with keys: responsiveness, compliance, consistency, summary
        """
        # 加载任务
        task = await self.db.get(BidReviewTask, task_id)
        if not task:
            raise ValueError("审查任务不存在")

        project = await self.db.get(Project, task.project_id)
        if not project:
            raise ValueError("项目不存在")

        # 更新任务状态
        task.status = ReviewTaskStatus.PROCESSING
        await self.db.flush()

        # 创建 OpenAI 服务
        openai_service = await self._create_openai_service(
            project.id, model_name, provider_config_id
        )

        bid_content = task.bid_content or ""

        # 获取知识库上下文
        knowledge_context = ""
        if use_knowledge and knowledge_ids:
            try:
                from ..services.knowledge_retrieval_service import KnowledgeRetrievalService
                retrieval_svc = KnowledgeRetrievalService(self.db)
                results = await retrieval_svc.search(
                    project_id=project.id,
                    query=f"标书审查参考 {project.name}",
                    top_k=len(knowledge_ids),
                )
                # 按 knowledge_ids 过滤
                if results:
                    kid_set = set(knowledge_ids)
                    filtered = [r for r in results if str(r.get('id', '')) in kid_set]
                    if filtered:
                        knowledge_context = "\n\n".join(
                            f"- {r.get('content', '')}" for r in filtered[:10]
                        )
            except Exception as e:
                print(f"[Review] 知识库检索失败，跳过: {e}")

        # 预加载所有维度的 prompt，避免 asyncio.gather 中共享 AsyncSession
        scene_key_map = {
            "responsiveness": "bid_review_responsiveness",
            "compliance": "bid_review_compliance",
            "consistency": "bid_review_consistency",
        }
        needed_keys = [scene_key_map[d] for d in dimensions if d in scene_key_map]
        prompt_cache = await self._prefetch_prompts(project.id, needed_keys)

        # 构建维度执行列表
        dimension_funcs = []
        dimension_names = []

        if "responsiveness" in dimensions:
            sp, ut = prompt_cache["bid_review_responsiveness"]
            dimension_funcs.append(
                self._run_responsiveness_check(
                    openai_service, project, bid_content, sp, ut, knowledge_context
                )
            )
            dimension_names.append("responsiveness")

        if "compliance" in dimensions:
            sp, ut = prompt_cache["bid_review_compliance"]
            dimension_funcs.append(
                self._run_compliance_check(openai_service, project, bid_content, sp, ut)
            )
            dimension_names.append("compliance")

        if "consistency" in dimensions:
            sp, ut = prompt_cache["bid_review_consistency"]
            dimension_funcs.append(
                self._run_consistency_check(
                    openai_service, bid_content, sp, ut,
                    project.project_overview or ""
                )
            )
            dimension_names.append("consistency")

        # 并行执行所有维度
        results = await asyncio.gather(*dimension_funcs, return_exceptions=True)

        # 处理结果
        resp_result = None
        comp_result = None
        cons_result = None
        failed_dimensions: list[str] = []

        for name, result in zip(dimension_names, results, strict=True):
            if isinstance(result, Exception):
                print(f"[Review] {name} 维度执行异常: {result}")
                failed_dimensions.append(name)
                continue
            if result is None:
                failed_dimensions.append(name)
                continue
            if name == "responsiveness":
                resp_result = result
            elif name == "compliance":
                comp_result = result
            elif name == "consistency":
                cons_result = result

        # 全部失败则标记为 FAILED
        if len(failed_dimensions) == len(dimension_names):
            task.status = ReviewTaskStatus.FAILED
            task.error_message = f"全部维度审查失败: {', '.join(failed_dimensions)}"
            await self.db.commit()
            raise ValueError(task.error_message)

        # 部分失败标记 partial 状态信息
        task.error_message = (
            f"部分维度审查失败: {', '.join(failed_dimensions)}"
            if failed_dimensions else None
        )

        # 生成汇总（仅对成功维度计分）
        summary = self.generate_summary(resp_result, comp_result, cons_result, failed_dimensions)

        # 保存结果到数据库
        task.responsiveness_result = resp_result
        task.compliance_result = comp_result
        task.consistency_result = cons_result
        task.summary = summary
        task.status = ReviewTaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(task)

        return {
            "responsiveness": resp_result,
            "compliance": comp_result,
            "consistency": cons_result,
            "summary": summary,
        }
