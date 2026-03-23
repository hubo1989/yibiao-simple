"""OpenAI服务"""
import openai
from typing import Dict, Any, List, AsyncGenerator, Callable
import json
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.outline_util import get_random_indexes, calculate_nodes_distribution, generate_one_outline_json_by_level1
from ..utils.json_util import check_json, repair_truncated_json
from ..utils.config_manager import config_manager
from ..utils.encryption import encryption_service
from ..models.api_key_config import ApiKeyConfig
from ..db.database import async_session_factory
from ..services.prompt_service import PromptService


# 校对结果类型定义
PROOFREAD_ISSUE_SCHEMA = {
    "severity": "critical|warning|info",
    "category": "compliance|language|consistency|redundancy",
    "position": "问题所在位置描述",
    "issue": "问题描述",
    "suggestion": "修改建议"
}

# 跨章节一致性检查矛盾类型定义
CONSISTENCY_CONTRADICTION_SCHEMA = {
    "severity": "critical|warning|info",
    "category": "data|terminology|timeline|commitment|scope",
    "description": "矛盾描述",
    "chapter_a": "涉及章节A的编号和标题",
    "chapter_b": "涉及章节B的编号和标题",
    "detail_a": "章节A中的相关内容",
    "detail_b": "章节B中的相关内容",
    "suggestion": "统一的建议"
}

PROOFREAD_RESULT_SCHEMA = {
    "issues": [PROOFREAD_ISSUE_SCHEMA],
    "summary": "整体问题摘要",
}

CONSISTENCY_RESULT_SCHEMA = {
    "contradictions": [CONSISTENCY_CONTRADICTION_SCHEMA],
    "summary": "简要总结",
    "overall_consistency": "consistent|minor_issues|major_issues",
}

RATING_CHECKLIST_SCHEMA = [
    {
        "rating_item": "评分项名称",
        "score": "分值或权重",
        "response_targets": ["必须覆盖的响应点"],
        "evidence_suggestions": ["建议补充的证据或支撑材料"],
        "writing_focus": "推荐重点写法",
        "risk_points": ["容易失分的点"],
    }
]

CHAPTER_REVERSE_ENHANCE_SCHEMA = {
    "coverage_assessment": "充分|一般|不足",
    "matched_points": ["已覆盖评分点"],
    "missing_points": ["未覆盖评分点"],
    "enhancement_actions": [
        {
            "problem": "问题",
            "action": "建议补强动作",
            "evidence_needed": "建议补充的证据或材料",
            "priority": "high|medium|low",
        }
    ],
    "summary": "简要结论",
}

CHAPTER_RESPONSE_PLAN_SCHEMA = {
    "chapter_goal": "本章需要回答的核心评分问题",
    "response_targets": ["本章必须覆盖的响应点"],
    "evidence_needed": ["建议准备的证据或验证材料"],
    "validation_points": ["评审/验收时可检查的落地点"],
    "boundary_rules": ["与相邻章节的去重边界"],
}

CLAUSE_RESPONSE_SOURCE_REF_SCHEMA = {
    "ref_id": "kb_1",
    "source_type": "knowledge_context",
    "location": "知识库条目 1 / 标题 / 段落",
    "quote": "支撑摘录",
    "relation": "该摘录如何支撑响应判断",
}

CLAUSE_RESPONSE_ITEM_SCHEMA = {
    "clause_text": "原条款或子条款",
    "response_conclusion": "满足|部分满足|待补充|待澄清",
    "response_description": "响应说明",
    "support_measures": ["支撑措施/交付方式/保障方式"],
    "evidence_needed": ["建议补充的证据或验证材料"],
    "validation_points": ["评审或验收可检查点"],
    "risk_points": ["仍需注意的风险点"],
    "source_refs": [CLAUSE_RESPONSE_SOURCE_REF_SCHEMA],
}

CLAUSE_RESPONSE_SCHEMA = {
    "clause_text": "输入的条款原文",
    "summary": "整体响应摘要",
    "items": [CLAUSE_RESPONSE_ITEM_SCHEMA],
}

BID_REVIEW_ITEM_SCHEMA = {
    "rating_item": "评分项名称",
    "score": 0,
    "max_score": 0,
    "coverage_status": "covered|partial|missing|risk",
    "evidence": "支撑证据或定位",
    "source_refs": [
        {
            "ref_id": "tender_p1|bid_h1|kb_1",
            "source_type": "tender_document|bid_content|knowledge_context",
            "location": "第1页/第1章/知识库条目1",
            "quote": "原文摘录",
            "relation": "该摘录如何支撑判断",
        }
    ],
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"],
    "rewrite_suggestions": ["可直接用于改写的建议1"],
    "chapter_targets": ["建议影响的章节标题或编号"],
    "confidence": "high|medium|low",
}

BID_REVIEW_SCHEMA = {
    "summary": "整体复审摘要",
    "overall_score": 0,
    "score_max": 100,
    "coverage_rate": 0,
    "risk_level": "low|medium|high",
    "items": [BID_REVIEW_ITEM_SCHEMA],
}

OUTLINE_EXTRACT_SCHEMA = {
    "outline": [
        {
            "id": "1",
            "title": "一级章节标题",
            "description": "章节简述",
            "children": [
                {
                    "id": "1.1",
                    "title": "二级章节标题",
                    "description": "章节简述",
                    "children": [],
                }
            ],
        }
    ]
}


class OpenAIService:
    """OpenAI服务类"""

    def __init__(self, db: AsyncSession | None = None, project_id: uuid.UUID | None = None):
        """
        初始化OpenAI服务

        Args:
            db: 可选的数据库会话。如果提供，将从数据库读取默认配置；
                否则使用同步方式从数据库获取配置
            project_id: 可选的项目ID，用于获取项目级自定义提示词
        """
        self._db = db
        self._project_id = project_id
        self.api_key = ''
        self.base_url = ''
        self.model_name = 'gpt-3.5-turbo'
        self._client = None
        self._prompt_service = None

    def _set_prompt_service(self) -> None:
        if self._db and self._prompt_service is None:
            self._prompt_service = PromptService(self._db)

    def use_api_key_config(self, config: ApiKeyConfig) -> bool:
        """直接应用指定的 API Key 配置。"""
        self.api_key = encryption_service.decrypt(config.api_key_encrypted)
        self.base_url = config.base_url or ''
        self.model_name = config.get_generation_model_name()
        self._client = (
            openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url if self.base_url else None
            )
            if self.api_key else None
        )
        self._set_prompt_service()
        return bool(self.api_key)

    async def _load_config_from_db(self) -> bool:
        """从数据库加载默认 API Key 配置"""
        if self._db is None:
            # 没有传入 db 会话，创建一个临时的
            async with async_session_factory() as session:
                return await self._fetch_default_config(session)
        return await self._fetch_default_config(self._db)

    async def _fetch_default_config(self, db: AsyncSession) -> bool:
        """从数据库获取默认配置"""
        result = await db.execute(
            select(ApiKeyConfig).where(ApiKeyConfig.is_default == True).limit(1)
        )
        config = result.scalar_one_or_none()

        if config:
            return self.use_api_key_config(config)
        return False

    async def use_config_by_id(self, config_id: str) -> bool:
        """按配置 ID 选择指定 provider 配置。"""
        try:
            config_uuid = uuid.UUID(str(config_id))
        except ValueError:
            return False

        if self._db is None:
            async with async_session_factory() as session:
                return await self._fetch_config_by_id(session, config_uuid)
        return await self._fetch_config_by_id(self._db, config_uuid)

    async def _fetch_config_by_id(self, db: AsyncSession, config_id: uuid.UUID) -> bool:
        result = await db.execute(
            select(ApiKeyConfig).where(ApiKeyConfig.id == config_id).limit(1)
        )
        config = result.scalar_one_or_none()
        if not config:
            return False
        return self.use_api_key_config(config)

    async def _ensure_initialized(self):
        """确保服务已初始化"""
        if self._client is None:
            # 先尝试从数据库加载配置
            loaded = await self._load_config_from_db()

            # 如果数据库中没有配置，回退到本地配置文件
            if not loaded:
                config = config_manager.load_config()
                self.api_key = config.get('api_key', '')
                self.base_url = config.get('base_url', '')
                self.model_name = config.get('model_name', 'gpt-3.5-turbo')
                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url if self.base_url else None
                )

            self._set_prompt_service()

    @property
    def client(self):
        """获取 OpenAI 客户端（向后兼容）"""
        if self._client is None:
            # 同步初始化（仅在无法使用 async 的情况下）
            raise RuntimeError("OpenAIService 需要先调用 async 方法进行初始化")
        return self._client

    def set_model(self, model_name: str):
        """覆盖默认模型"""
        self.model_name = model_name

    @staticmethod
    def _append_json_output_contract(system_prompt: str, schema: str | Dict[str, Any]) -> str:
        """为需要结构化输出的提示词追加稳定的 JSON 返回约束"""
        schema_text = (
            schema
            if isinstance(schema, str)
            else json.dumps(schema, ensure_ascii=False, indent=2)
        )
        if schema_text in system_prompt:
            return system_prompt

        contract = (
            "### 输出格式约束\n"
            "你必须返回合法 JSON，且不要输出任何 JSON 之外的解释、代码块标记或注释。\n"
            "返回结构必须匹配以下示例：\n"
            f"```json\n{schema_text}\n```"
        )
        return f"{system_prompt.rstrip()}\n\n{contract}"

    @staticmethod
    def _build_review_input_profile(
        *,
        tender_document: str,
        tender_overview: str,
        tender_requirements: str,
        rating_checklist: list[dict[str, Any]],
        knowledge_context: str,
        bid_content: str,
        tender_source_registry: str = "",
        bid_source_registry: str = "",
    ) -> str:
        """构建复审输入摘要，明确告知模型哪些材料已经提供。"""
        return (
            "### 输入完整性摘要\n"
            f"- 招标原文件：已提供，长度 {len(tender_document or '')} 字符\n"
            f"- 项目概述：已提供，长度 {len(tender_overview or '')} 字符\n"
            f"- 技术评分要求：已提供，长度 {len(tender_requirements or '')} 字符\n"
            f"- 评分项清单：已提供，{len(rating_checklist or [])} 项\n"
            f"- 招标原文定位索引：{'已提供' if (tender_source_registry or '').strip() else '未提供'}，长度 {len(tender_source_registry or '')} 字符\n"
            f"- 待审标书定位索引：{'已提供' if (bid_source_registry or '').strip() else '未提供'}，长度 {len(bid_source_registry or '')} 字符\n"
            f"- 知识库上下文：{'已提供' if (knowledge_context or '').strip() else '未提供'}，长度 {len(knowledge_context or '')} 字符\n"
            f"- 待审标书：已提供，长度 {len(bid_content or '')} 字符\n"
            "重要：只要上述字段长度大于 0，就不要再输出“未收到/未提供招标原文件、技术评分要求、评分项清单与待审标书”这类结论；"
            "如需指出不足，只能具体说明某些评分点、章节、证据锚点或来源定位不充分。"
        )

    @staticmethod
    def _build_chapter_response_plan(
        *,
        chapter_title: str,
        chapter_description: str,
        chapter_rating_focus: str,
        chapter_role: str,
        adjacent_boundary: str,
        tech_requirements: str = "",
        knowledge_context: str = "",
    ) -> str:
        """构建章节生成前的响应计划摘要，强化评分响应闭环。"""
        return (
            "### 本章响应计划\n"
            f"- 章节标题：{chapter_title or '未命名章节'}\n"
            f"- 章节描述：{chapter_description or '无'}\n"
            f"- 核心评分问题：{chapter_rating_focus or '未指定'}\n"
            f"- 主职责定位：{chapter_role or '未指定'}\n"
            f"- 去重边界：{adjacent_boundary or '未指定'}\n"
            f"- 技术要求上下文长度：{len(tech_requirements or '')}\n"
            f"- 知识库上下文长度：{len(knowledge_context or '')}\n"
            "写作要求：先回答评分项想看什么，再写方案动作、落地机制、验证方式，最后补充边界和保障。"
        )

    @staticmethod
    def _build_project_response_matrix(rating_checklist: list[dict[str, Any]] | None) -> str:
        """把评分清单压缩成章节生成可直接使用的响应矩阵。"""
        items = rating_checklist or []
        if not items:
            return ""

        blocks: list[str] = []
        for index, item in enumerate(items, start=1):
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            if not isinstance(item, dict):
                continue

            rating_item = str(item.get("rating_item") or f"评分项 {index}").strip()
            score = str(item.get("score") or "").strip()
            response_targets = [str(value).strip() for value in (item.get("response_targets") or []) if str(value).strip()]
            evidence_suggestions = [str(value).strip() for value in (item.get("evidence_suggestions") or []) if str(value).strip()]
            writing_focus = str(item.get("writing_focus") or "").strip()
            risk_points = [str(value).strip() for value in (item.get("risk_points") or []) if str(value).strip()]

            lines = [f"[{index}] {rating_item}"]
            if score:
                lines.append(f"分值/权重：{score}")
            if response_targets:
                lines.append(f"必须覆盖：{'；'.join(response_targets)}")
            if evidence_suggestions:
                lines.append(f"建议证据：{'；'.join(evidence_suggestions)}")
            if writing_focus:
                lines.append(f"写作重点：{writing_focus}")
            if risk_points:
                lines.append(f"易失分点：{'；'.join(risk_points)}")
            blocks.append("\n".join(lines))

        if not blocks:
            return ""

        return "### 本项目响应矩阵\n" + "\n\n---\n\n".join(blocks)

    @staticmethod
    def _build_clause_response_input_profile(
        *,
        clause_text: str,
        project_overview: str,
        knowledge_context: str,
        knowledge_source_registry: str,
    ) -> str:
        """构建条款逐条响应输入摘要。"""
        return (
            "### 输入完整性摘要\n"
            f"- 项目概述：已提供，长度 {len(project_overview or '')} 字符\n"
            f"- 条款原文：已提供，长度 {len(clause_text or '')} 字符\n"
            f"- 知识库上下文：{'已提供' if (knowledge_context or '').strip() else '未提供'}，长度 {len(knowledge_context or '')} 字符\n"
            f"- 知识库定位索引：{'已提供' if (knowledge_source_registry or '').strip() else '未提供'}，长度 {len(knowledge_source_registry or '')} 字符\n"
            "重要：如果知识库定位索引已提供，source_refs 必须从索引中回链，不要虚构引用。"
        )

    @staticmethod
    def _validate_clause_response_sources(
        data: Any,
        *,
        knowledge_source_registry: str,
    ) -> tuple[bool, str]:
        """校验条款响应中的证据锚点是否可回链到知识库索引。"""
        if not isinstance(data, dict):
            return False, "条款响应结果必须是对象"

        items = data.get("items", [])
        if not isinstance(items, list) or not items:
            return False, "条款响应结果必须包含 items 数组"

        allowed_ref_ids: set[str] = set()
        for line in (knowledge_source_registry or "").splitlines():
            line = line.strip()
            if line.startswith("- "):
                ref_id = line[2:].split(" | ", 1)[0].strip()
                if ref_id:
                    allowed_ref_ids.add(ref_id)

        require_source_refs = bool(allowed_ref_ids)

        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                return False, f"第 {index} 个响应项不是对象"

            source_refs = item.get("source_refs")
            if require_source_refs and (not isinstance(source_refs, list) or not source_refs):
                return False, f"第 {index} 个响应项缺少 source_refs 证据锚点"

            if not isinstance(source_refs, list):
                continue

            for ref in source_refs:
                if not isinstance(ref, dict):
                    return False, f"第 {index} 个响应项的 source_refs 格式无效"
                ref_id = str(ref.get("ref_id") or "").strip()
                source_type = str(ref.get("source_type") or "").strip()
                location = str(ref.get("location") or "").strip()
                quote = str(ref.get("quote") or "").strip()
                relation = str(ref.get("relation") or "").strip()

                if require_source_refs and (not ref_id or ref_id not in allowed_ref_ids):
                    return False, f"第 {index} 个响应项的证据锚点 {ref_id or '空值'} 不在允许目录中"
                if source_type not in {"knowledge_context"}:
                    return False, f"第 {index} 个响应项的证据锚点来源类型无效"
                if not location:
                    return False, f"第 {index} 个响应项的证据锚点缺少 location"
                if not quote:
                    return False, f"第 {index} 个响应项的证据锚点缺少 quote"
                if not relation:
                    return False, f"第 {index} 个响应项的证据锚点缺少 relation"

        return True, ""

    @staticmethod
    def _render_clause_response_markdown(data: dict[str, Any]) -> str:
        """把结构化条款响应渲染成正式投标文本。"""
        clause_text = str(data.get("clause_text") or "").strip()
        summary = str(data.get("summary") or "").strip()
        items = data.get("items", [])

        lines: list[str] = []
        if clause_text:
            lines.append("## 原条款")
            lines.append(clause_text)
            lines.append("")

        if summary:
            lines.append("## 响应摘要")
            lines.append(summary)
            lines.append("")

        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue

            item_clause_text = str(item.get("clause_text") or clause_text or "").strip()
            response_conclusion = str(item.get("response_conclusion") or "").strip()
            response_description = str(item.get("response_description") or "").strip()
            support_measures = [str(value).strip() for value in (item.get("support_measures") or []) if str(value).strip()]
            evidence_needed = [str(value).strip() for value in (item.get("evidence_needed") or []) if str(value).strip()]
            validation_points = [str(value).strip() for value in (item.get("validation_points") or []) if str(value).strip()]
            risk_points = [str(value).strip() for value in (item.get("risk_points") or []) if str(value).strip()]
            source_refs = item.get("source_refs", [])

            lines.append(f"### {index}. 条款响应")
            if item_clause_text:
                lines.append(f"- 原条款/参数：{item_clause_text}")
            if response_conclusion:
                lines.append(f"- 响应结论：{response_conclusion}")
            if response_description:
                lines.append(f"- 响应说明：{response_description}")
            if support_measures:
                lines.append(f"- 支撑措施：{'；'.join(support_measures)}")
            if validation_points:
                lines.append(f"- 验证要点：{'；'.join(validation_points)}")
            if evidence_needed:
                lines.append(f"- 需补充证据：{'；'.join(evidence_needed)}")
            if risk_points:
                lines.append(f"- 风险提示：{'；'.join(risk_points)}")

            valid_refs = []
            for ref in source_refs if isinstance(source_refs, list) else []:
                if isinstance(ref, dict):
                    ref_id = str(ref.get("ref_id") or "").strip()
                    location = str(ref.get("location") or "").strip()
                    quote = str(ref.get("quote") or "").strip()
                    relation = str(ref.get("relation") or "").strip()
                    if ref_id and location and quote and relation:
                        valid_refs.append(f"{ref_id} | {location} | {quote} | {relation}")

            if valid_refs:
                lines.append(f"- 证据锚点：{'；'.join(valid_refs)}")
            lines.append("")

        return "\n".join(lines).strip()
    
    async def get_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        await self._ensure_initialized()
        try:
            models = await self._client.models.list()
            chat_models = []
            for model in models.data:
                model_id = model.id.lower()
                if any(keyword in model_id for keyword in ['gpt', 'claude', 'chat', 'llama', 'qwen', 'deepseek', 'glm', 'kimi', 'minimax', 'gemini']):
                    chat_models.append(model.id)
            # 如果没有匹配的模型，返回当前配置的模型
            if not chat_models and self.model_name:
                return [self.model_name]
            return sorted(list(set(chat_models)))
        except Exception as e:
            # 如果获取模型列表失败，返回当前配置的模型作为备选
            if self.model_name:
                return [self.model_name]
            raise Exception(f"获取模型列表失败: {str(e)}")
    
    async def stream_chat_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict = None,
        max_tokens: int = 8192
    ) -> AsyncGenerator[str, None]:
        """流式聊天完成请求 - 真正的异步实现"""
        await self._ensure_initialized()
        try:
            stream = await self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                stream=True,
                max_tokens=max_tokens,
                **({"response_format": response_format} if response_format is not None else {})
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            # 不要 yield 错误信息，而是抛出异常让调用方处理
            raise RuntimeError(f"AI 服务调用失败: {str(e)}")

    async def _collect_stream_text(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> str:
        """收集流式返回的文本到一个完整字符串"""
        full_content = ""
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=temperature,
            response_format=response_format,
        ):
            full_content += chunk
        return full_content

    async def _generate_with_json_check(
        self,
        messages: list,
        schema: str | Dict[str, Any],
        max_retries: int = 3,
        temperature: float = 0.7,
        response_format: dict | None = None,
        log_prefix: str = "",
        raise_on_fail: bool = True,
        validator: Callable[[Any], tuple[bool, str]] | None = None,
    ) -> str:
        """
        通用的带 JSON 结构校验与重试的生成函数。

        返回：通过校验的 full_content；如果 raise_on_fail=False，则在多次失败后返回最后一次内容。
        """
        attempt = 0
        last_error_msg = ""

        while True:
            full_content = await self._collect_stream_text(
                messages,
                temperature=temperature,
                response_format=response_format,
            )

            # 定义前缀，用于日志输出
            prefix = f"{log_prefix} " if log_prefix else ""

            # 如果 schema 期望的是对象，但 AI 返回的是 list，尝试取第一个元素
            content_to_check = full_content
            try:
                parsed = json.loads(full_content.strip())
                expected_schema = json.loads(schema) if isinstance(schema, str) else schema
                if (
                    isinstance(parsed, list)
                    and len(parsed) > 0
                    and isinstance(expected_schema, dict)
                ):
                    # AI 返回的是数组，取第一个元素
                    content_to_check = json.dumps(parsed[0], ensure_ascii=False)
                    print(f"{prefix}AI 返回的是数组，自动取第一个元素")
            except:
                pass

            # 首先尝试直接校验
            isok, error_msg = check_json(content_to_check, schema)
            if isok:
                if validator is not None:
                    try:
                        parsed_content = json.loads(content_to_check.strip())
                    except Exception:
                        parsed_content = None

                    if parsed_content is not None:
                        valid, validator_msg = validator(parsed_content)
                        if not valid:
                            last_error_msg = validator_msg
                            if attempt >= max_retries:
                                print(f"{prefix}业务校验失败，已达到最大重试次数({max_retries})：{last_error_msg}")
                                if raise_on_fail:
                                    raise Exception(f"{prefix}业务校验失败: {last_error_msg}")
                                return full_content

                            attempt += 1
                            print(f"{prefix}业务校验失败，进行第 {attempt}/{max_retries} 次重试：{last_error_msg}")
                            messages = messages + [{
                                "role": "user",
                                "content": (
                                    "上一次输出已经通过 JSON 结构校验，但未通过业务校验："
                                    f"{validator_msg}。"
                                    "请严格按系统指令重新生成，只输出合法 JSON，不要添加解释。"
                                ),
                            }]
                            await asyncio.sleep(0.5)
                            continue
                return content_to_check

            # 打印 AI 返回的内容，便于调试
            print(f"{prefix}AI 返回内容前500字符: {str(full_content)[:500]}")

            # 如果校验失败，尝试修复截断的 JSON
            repaired_content = repair_truncated_json(str(full_content))
            if repaired_content != full_content:
                print(f"{prefix}尝试修复截断的 JSON...")
                isok, error_msg = check_json(repaired_content, schema)
                if isok:
                    print(f"{prefix}JSON 修复成功！")
                    return repaired_content

            last_error_msg = error_msg

            if attempt >= max_retries:
                print(f"{prefix}check_json 校验失败，已达到最大重试次数({max_retries})：{last_error_msg}")
                if raise_on_fail:
                    raise Exception(f"{prefix}check_json 校验失败: {last_error_msg}")
                # 不抛异常，返回最后一次内容（保持原有行为）
                return full_content

            attempt += 1
            print(f"{prefix}check_json 校验失败，进行第 {attempt}/{max_retries} 次重试：{last_error_msg}")
            await asyncio.sleep(0.5)

    async def generate_content_for_outline(
        self,
        outline: Dict[str, Any],
        project_overview: str = "",
        knowledge_context: str = "",
        project_response_matrix: str = "",
    ) -> Dict[str, Any]:
        """
        为目录结构生成内容

        Args:
            outline: 目录结构数据
            project_overview: 项目概述信息
            knowledge_context: 知识库检索结果（可选）

        Returns:
            生成内容后的目录结构
        """
        try:
            if not isinstance(outline, dict) or 'outline' not in outline:
                raise Exception("无效的outline数据格式")

            # 深拷贝outline数据
            import copy
            result_outline = copy.deepcopy(outline)

            # 递归处理目录
            await self._process_outline_recursive(
                result_outline['outline'], [], project_overview, knowledge_context, project_response_matrix
            )

            return result_outline

        except Exception as e:
            raise Exception(f"处理过程中发生错误: {str(e)}")

    async def _process_outline_recursive(
        self,
        chapters: list,
        parent_chapters: list = None,
        project_overview: str = "",
        knowledge_context: str = "",
        project_response_matrix: str = "",
    ):
        """递归处理章节列表"""
        for chapter in chapters:
            chapter_id = chapter.get('id', 'unknown')
            chapter_title = chapter.get('title', '未命名章节')

            # 检查是否为叶子节点
            is_leaf = 'children' not in chapter or not chapter.get('children', [])

            # 准备当前章节信息
            current_chapter_info = {
                'id': chapter_id,
                'title': chapter_title,
                'description': chapter.get('description', '')
            }

            # 构建完整的上级章节列表
            current_parent_chapters = []
            if parent_chapters:
                current_parent_chapters.extend(parent_chapters)
            current_parent_chapters.append(current_chapter_info)

            if is_leaf:
                # 为叶子节点生成内容，传递同级章节信息
                content = ""
                async for chunk in self._generate_chapter_content(
                    chapter,
                    current_parent_chapters[:-1],  # 上级章节列表（排除当前章节）
                    chapters,  # 同级章节列表
                    project_overview,
                    knowledge_context,
                    project_response_matrix=project_response_matrix,
                ):
                    content += chunk
                if content:
                    chapter['content'] = content
            else:
                # 递归处理子章节
                await self._process_outline_recursive(
                    chapter['children'],
                    current_parent_chapters,
                    project_overview,
                    knowledge_context,
                    project_response_matrix,
                )
    
    async def _generate_chapter_content(
        self,
        chapter: dict,
        parent_chapters: list = None,
        sibling_chapters: list = None,
        project_overview: str = "",
        knowledge_context: str = "",
        tech_requirements: str = "",
        project_response_matrix: str = "",
        chapter_rating_focus: str = "",
        chapter_role: str = "",
        adjacent_boundary: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        为单个章节流式生成内容

        Args:
            chapter: 章节数据
            parent_chapters: 上级章节列表，每个元素包含章节id、标题和描述
            sibling_chapters: 同级章节列表，避免内容重复
            project_overview: 项目概述信息，提供项目背景和要求
            knowledge_context: 知识库检索结果，提供参考资料
            tech_requirements: 技术评分/响应要求
            chapter_rating_focus: 当前章节绑定的评分点
            chapter_role: 当前章节职责定位
            adjacent_boundary: 当前章节与相邻章节边界

        Yields:
            生成的内容流
        """
        try:
            chapter_id = chapter.get('id', 'unknown')
            chapter_title = chapter.get('title', '未命名章节')
            chapter_description = chapter.get('description', '')
            chapter_rating_focus = chapter_rating_focus or chapter.get('rating_item', '') or chapter.get('chapter_rating_focus', '')
            chapter_role = chapter_role or chapter.get('chapter_role', '')
            adjacent_boundary = adjacent_boundary or chapter.get('avoid_overlap', '') or chapter.get('adjacent_boundary', '')
            project_response_matrix = project_response_matrix or chapter.get('project_response_matrix', '')
            chapter_response_plan = self._build_chapter_response_plan(
                chapter_title=chapter_title,
                chapter_description=chapter_description,
                chapter_rating_focus=chapter_rating_focus,
                chapter_role=chapter_role,
                adjacent_boundary=adjacent_boundary,
                tech_requirements=tech_requirements,
                knowledge_context=knowledge_context,
            )

            # 使用 PromptService 获取提示词
            if self._prompt_service:
                prompt, _ = await self._prompt_service.get_prompt(
                    "chapter_content", self._project_id
                )
                from .prompt_service import PromptService
                system_prompt, user_template = PromptService.split_prompt(prompt)
                # 渲染用户提示词模板
                user_prompt = self._prompt_service.render_prompt(user_template, {
                    "project_overview": project_overview,
                    "tech_requirements": tech_requirements,
                    "chapter_rating_focus": chapter_rating_focus,
                    "chapter_role": chapter_role,
                    "adjacent_boundary": adjacent_boundary,
                    "chapter_response_plan": chapter_response_plan,
                    "project_response_matrix": project_response_matrix,
                    "knowledge_context": knowledge_context,
                    "parent_chapters": parent_chapters or [],
                    "sibling_chapters": [s for s in (sibling_chapters or []) if s.get('id') != chapter_id],
                    "chapter_id": chapter_id,
                    "chapter_title": chapter_title,
                    "chapter_description": chapter_description,
                })
            else:
                # 回退到内置提示词（兼容旧代码）
                from ..utils.builtin_prompts import get_builtin_prompt
                from .prompt_service import PromptService
                builtin = get_builtin_prompt("chapter_content")
                system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
                user_prompt = PromptService.render_prompt(user_template, {
                    "project_overview": project_overview,
                    "tech_requirements": tech_requirements,
                    "chapter_rating_focus": chapter_rating_focus,
                    "chapter_role": chapter_role,
                    "adjacent_boundary": adjacent_boundary,
                    "chapter_response_plan": chapter_response_plan,
                    "project_response_matrix": project_response_matrix,
                    "knowledge_context": knowledge_context,
                    "parent_chapters": parent_chapters or [],
                    "sibling_chapters": [s for s in (sibling_chapters or []) if s.get('id') != chapter_id],
                    "chapter_id": chapter_id,
                    "chapter_title": chapter_title,
                    "chapter_description": chapter_description,
                })

            # 调用AI流式生成内容
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # 流式返回生成的文本
            async for chunk in self.stream_chat_completion(messages, temperature=0.7):
                yield chunk

        except Exception as e:
            print(f"生成章节内容时出错: {str(e)}")
            raise  # 重新抛出异常，而不是 yield 错误字符串

    async def generate_outline_v2(
        self,
        overview: str,
        requirements: str,
        rating_checklist: list[dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        schema_json = json.dumps([
            {
                "rating_item": "原评分项",
                "new_title": "根据评分项修改的标题",
                "chapter_role": "本章主职责",
                "avoid_overlap": "与其他章节应避免重复的内容边界",
            }
        ])
        project_response_matrix = self._build_project_response_matrix(rating_checklist)

        # 使用 PromptService 获取提示词
        if self._prompt_service:
            prompt, _ = await self._prompt_service.get_prompt(
                "outline_l1", self._project_id
            )
            from .prompt_service import PromptService
            system_prompt, user_template = PromptService.split_prompt(prompt)
            system_prompt = self._append_json_output_contract(system_prompt, schema_json)
            user_prompt = PromptService.render_prompt(user_template, {
                "overview": overview,
                "requirements": requirements,
                "project_response_matrix": project_response_matrix,
            })
        else:
            # 回退到内置提示词
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("outline_l1")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = self._append_json_output_contract(system_prompt, schema_json)
            user_prompt = PromptService.render_prompt(user_template, {
                "overview": overview,
                "requirements": requirements,
                "project_response_matrix": project_response_matrix,
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 使用通用方法进行 JSON 校验与重试（失败时抛出异常）
        # 注意：z.ai API 不支持 response_format 参数，移除此参数
        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=schema_json,
            max_retries=3,
            temperature=0.7,
            response_format=None,  # z.ai API 不支持此参数
            log_prefix="一级提纲",
            raise_on_fail=True,
        )

        # 通过校验后再进行 JSON 解析
        level_l1 = json.loads(full_content.strip())

        expected_word_count = 100000
        leaf_node_count = expected_word_count // 1500

        # 随机重点章节
        index1, index2 = get_random_indexes(len(level_l1))

        nodes_distribution = calculate_nodes_distribution(len(level_l1), (index1, index2), leaf_node_count)

        # 并发生成每个一级节点的提纲，保持结果顺序
        tasks = [
            self.process_level1_node(i, level1_node, nodes_distribution, level_l1, overview, requirements)
            for i, level1_node in enumerate(level_l1)
        ]
        outline = await asyncio.gather(*tasks)



        return {"outline": outline}

    async def extract_outline_from_document(self, document_text: str) -> Dict[str, Any]:
        """从原始文档中提取目录结构"""
        if self._prompt_service:
            prompt, _ = await self._prompt_service.get_prompt(
                "outline_extract", self._project_id
            )
            from .prompt_service import PromptService
            system_prompt, user_template = PromptService.split_prompt(prompt)
            system_prompt = self._append_json_output_contract(system_prompt, OUTLINE_EXTRACT_SCHEMA)
            user_prompt = PromptService.render_prompt(user_template, {
                "file_content": document_text,
            })
        else:
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("outline_extract")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = self._append_json_output_contract(system_prompt, OUTLINE_EXTRACT_SCHEMA)
            user_prompt = PromptService.render_prompt(user_template, {
                "file_content": document_text,
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=OUTLINE_EXTRACT_SCHEMA,
            max_retries=3,
            temperature=0.6,
            response_format=None,
            log_prefix="文档目录提取",
            raise_on_fail=True,
        )

        return json.loads(full_content.strip())

    async def process_level1_node(self, i, level1_node, nodes_distribution, level_l1, overview, requirements):
        """处理单个一级节点的函数"""

        # 生成json
        json_outline = generate_one_outline_json_by_level1(level1_node["new_title"], i + 1, nodes_distribution)
        print(f"正在处理第{i+1}章: {level1_node['new_title']}")

        # 其他标题
        other_outline = "\n".join([f"{j+1}. {node['new_title']}"
                            for j, node in enumerate(level_l1)
                            if j!= i])

        # 使用 PromptService 获取提示词
        if self._prompt_service:
            prompt, _ = await self._prompt_service.get_prompt(
                "outline_l2l3", self._project_id
            )
            from .prompt_service import PromptService
            system_prompt, user_template = PromptService.split_prompt(prompt)
            system_prompt = self._append_json_output_contract(system_prompt, json_outline)
            user_prompt = PromptService.render_prompt(user_template, {
                "overview": overview,
                "requirements": requirements,
                "chapter_rating_item": level1_node.get("rating_item", ""),
                "chapter_role": level1_node.get("chapter_role", ""),
                "avoid_overlap": level1_node.get("avoid_overlap", ""),
                "other_outline": other_outline,
                "current_outline_json": json_outline,
            })
        else:
            # 回退到内置提示词
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("outline_l2l3")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = self._append_json_output_contract(system_prompt, json_outline)
            user_prompt = PromptService.render_prompt(user_template, {
                "overview": overview,
                "requirements": requirements,
                "chapter_rating_item": level1_node.get("rating_item", ""),
                "chapter_role": level1_node.get("chapter_role", ""),
                "avoid_overlap": level1_node.get("avoid_overlap", ""),
                "other_outline": other_outline,
                "current_outline_json": json_outline,
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 使用通用方法进行 JSON 校验与重试（失败时不抛异常，保持原有"返回最后一次结果"的行为）
        # 注意：z.ai API 不支持 response_format 参数
        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=json_outline,
            max_retries=3,
            temperature=0.7,
            response_format=None,  # z.ai API 不支持此参数
            log_prefix=f"第{i+1}章",
            raise_on_fail=False,
        )

        # 解析 JSON
        parsed_content = json.loads(full_content.strip())
        
        # 如果 AI 返回的是数组，取第一个元素
        if isinstance(parsed_content, list):
            if len(parsed_content) > 0:
                parsed_content = parsed_content[0]
            else:
                parsed_content = json_outline  # 如果数组为空，使用原始 schema
        
        return parsed_content

    async def proofread_chapter(
        self,
        chapter_title: str,
        chapter_content: str,
        tech_requirements: str,
        sibling_chapter_titles: list[str] | None = None,
        project_overview: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        校对章节内容，检查合规性、语言质量和一致性问题

        Args:
            chapter_title: 章节标题
            chapter_content: 章节内容
            tech_requirements: 招标文件的评分要求
            sibling_chapter_titles: 同级章节标题列表（用于检查重复）
            project_overview: 项目概述信息

        Yields:
            流式返回的校对结果（JSON 格式）
        """
        # 使用 PromptService 获取提示词
        if self._prompt_service:
            prompt, _ = await self._prompt_service.get_prompt(
                "proofread", self._project_id
            )
            from .prompt_service import PromptService
            system_prompt, user_template = PromptService.split_prompt(prompt)
            system_prompt = self._append_json_output_contract(system_prompt, PROOFREAD_RESULT_SCHEMA)
            user_prompt = PromptService.render_prompt(user_template, {
                "chapter_title": chapter_title,
                "chapter_content": chapter_content,
                "tech_requirements": tech_requirements,
                "sibling_chapter_titles": sibling_chapter_titles or [],
                "project_overview": project_overview or "",
            })
        else:
            # 回退到内置提示词
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("proofread")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = self._append_json_output_contract(system_prompt, PROOFREAD_RESULT_SCHEMA)
            user_prompt = PromptService.render_prompt(user_template, {
                "chapter_title": chapter_title,
                "chapter_content": chapter_content,
                "tech_requirements": tech_requirements,
                "sibling_chapter_titles": sibling_chapter_titles or [],
                "project_overview": project_overview or "",
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 流式返回校对结果
        # 注意：z.ai API 不支持 response_format 参数
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=0.3,  # 较低温度以获得更稳定的校对结果
            response_format=None  # z.ai API 不支持此参数
        ):
            yield chunk

    async def check_consistency(
        self,
        chapter_summaries: list[dict[str, str]],
        project_overview: str | None = None,
        tech_requirements: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        检查跨章节一致性，检测并报告跨章节矛盾

        Args:
            chapter_summaries: 章节摘要列表，每个元素包含：
                - chapter_number: 章节编号（如 "1.2.3"）
                - title: 章节标题
                - summary: 章节内容摘要（包含关键承诺、数据、时间线等）
            project_overview: 项目概述信息
            tech_requirements: 招标文件的技术评分要求

        Yields:
            流式返回的一致性检查结果（JSON 格式）
        """
        import logging
        logger = logging.getLogger(__name__)

        # 构建章节摘要信息
        chapters_info = []
        for chapter in chapter_summaries:
            chapters_info.append(
                f"【{chapter.get('chapter_number', '')} {chapter.get('title', '')}】\n"
                f"{chapter.get('summary', '')}"
            )
        chapters_text = "\n\n".join(chapters_info)

        # 使用 PromptService 获取提示词
        if self._prompt_service:
            prompt, _ = await self._prompt_service.get_prompt(
                "consistency_check", self._project_id
            )
            from .prompt_service import PromptService
            system_prompt, user_template = PromptService.split_prompt(prompt)
            system_prompt = self._append_json_output_contract(system_prompt, CONSISTENCY_RESULT_SCHEMA)
            user_prompt = PromptService.render_prompt(user_template, {
                "chapter_summaries": chapters_text,
                "project_overview": project_overview or "",
                "tech_requirements": tech_requirements or "",
            })
        else:
            # 回退到内置提示词
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("consistency_check")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = self._append_json_output_contract(system_prompt, CONSISTENCY_RESULT_SCHEMA)
            user_prompt = PromptService.render_prompt(user_template, {
                "chapter_summaries": chapters_text,
                "project_overview": project_overview or "",
                "tech_requirements": tech_requirements or "",
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        logger.info(f"一致性检查 - system_prompt 长度: {len(system_prompt)}")
        logger.info(f"一致性检查 - user_prompt 长度: {len(user_prompt)}")
        logger.info(f"一致性检查 - user_prompt 前500字符: {user_prompt[:500]}")

        # 流式返回一致性检查结果
        # 注意：不使用 response_format 参数，因为某些 API 提供商（如智谱）不支持
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=0.3,
            max_tokens=4096
        ):
            yield chunk

    async def generate_rating_response_checklist(
        self,
        overview: str,
        requirements: str,
    ) -> str:
        """按评分项生成响应清单（返回 JSON 字符串）"""
        if self._prompt_service:
            prompt, _ = await self._prompt_service.get_prompt(
                "rating_response_checklist", self._project_id
            )
            from .prompt_service import PromptService
            system_prompt, user_template = PromptService.split_prompt(prompt)
            system_prompt = self._append_json_output_contract(system_prompt, RATING_CHECKLIST_SCHEMA)
            user_prompt = PromptService.render_prompt(user_template, {
                "overview": overview,
                "requirements": requirements,
            })
        else:
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("rating_response_checklist")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = self._append_json_output_contract(system_prompt, RATING_CHECKLIST_SCHEMA)
            user_prompt = PromptService.render_prompt(user_template, {
                "overview": overview,
                "requirements": requirements,
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return await self._generate_with_json_check(
            messages=messages,
            schema=RATING_CHECKLIST_SCHEMA,
            max_retries=3,
            temperature=0.4,
            response_format=None,
            log_prefix="评分响应清单",
            raise_on_fail=True,
        )

    async def reverse_enhance_chapter(
        self,
        chapter_title: str,
        chapter_content: str,
        tech_requirements: str,
        project_overview: str | None = None,
    ) -> str:
        """根据评分点反向补强章节（返回 JSON 字符串）"""
        if self._prompt_service:
            prompt, _ = await self._prompt_service.get_prompt(
                "chapter_reverse_enhance", self._project_id
            )
            from .prompt_service import PromptService
            system_prompt, user_template = PromptService.split_prompt(prompt)
            system_prompt = self._append_json_output_contract(system_prompt, CHAPTER_REVERSE_ENHANCE_SCHEMA)
            user_prompt = PromptService.render_prompt(user_template, {
                "chapter_title": chapter_title,
                "chapter_content": chapter_content,
                "tech_requirements": tech_requirements,
                "project_overview": project_overview or "",
            })
        else:
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("chapter_reverse_enhance")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = self._append_json_output_contract(system_prompt, CHAPTER_REVERSE_ENHANCE_SCHEMA)
            user_prompt = PromptService.render_prompt(user_template, {
                "chapter_title": chapter_title,
                "chapter_content": chapter_content,
                "tech_requirements": tech_requirements,
                "project_overview": project_overview or "",
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return await self._generate_with_json_check(
            messages=messages,
            schema=CHAPTER_REVERSE_ENHANCE_SCHEMA,
            max_retries=3,
            temperature=0.3,
            response_format=None,
            log_prefix="章节反向补强",
            raise_on_fail=True,
        )

    async def review_bid_document(
        self,
        tender_document: str,
        tender_overview: str,
        tender_requirements: str,
        rating_checklist: list[dict[str, Any]],
        knowledge_context: str,
        bid_content: str,
        directory_mode: str,
        tender_source_registry: str = "",
        bid_source_registry: str = "",
    ) -> str:
        """对待审标书生成结构化复审报告（返回 JSON 字符串）"""
        if self._prompt_service:
            prompt, _ = await self._prompt_service.get_prompt(
                "bid_review", self._project_id
            )
            from .prompt_service import PromptService
            system_prompt, user_template = PromptService.split_prompt(prompt)
            system_prompt = self._append_json_output_contract(system_prompt, BID_REVIEW_SCHEMA)
            input_profile = self._build_review_input_profile(
                tender_document=tender_document,
                tender_overview=tender_overview,
                tender_requirements=tender_requirements,
                rating_checklist=rating_checklist,
                knowledge_context=knowledge_context,
                bid_content=bid_content,
                tender_source_registry=tender_source_registry,
                bid_source_registry=bid_source_registry,
            )
            rendered_prompt = PromptService.render_prompt(
                user_template,
                {
                    "tender_document": tender_document,
                    "tender_overview": tender_overview,
                    "tender_requirements": tender_requirements,
                    "rating_checklist": json.dumps(rating_checklist, ensure_ascii=False),
                    "knowledge_context": knowledge_context,
                    "bid_content": bid_content,
                    "directory_mode": directory_mode,
                    "tender_source_registry": tender_source_registry,
                    "bid_source_registry": bid_source_registry,
                },
            )
            user_prompt = f"{input_profile}\n\n{rendered_prompt}"
        else:
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("bid_review")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = self._append_json_output_contract(system_prompt, BID_REVIEW_SCHEMA)
            input_profile = self._build_review_input_profile(
                tender_document=tender_document,
                tender_overview=tender_overview,
                tender_requirements=tender_requirements,
                rating_checklist=rating_checklist,
                knowledge_context=knowledge_context,
                bid_content=bid_content,
                tender_source_registry=tender_source_registry,
                bid_source_registry=bid_source_registry,
            )
            rendered_prompt = PromptService.render_prompt(
                user_template,
                {
                    "tender_document": tender_document,
                    "tender_overview": tender_overview,
                    "tender_requirements": tender_requirements,
                    "rating_checklist": json.dumps(rating_checklist, ensure_ascii=False),
                    "knowledge_context": knowledge_context,
                    "bid_content": bid_content,
                    "directory_mode": directory_mode,
                    "tender_source_registry": tender_source_registry,
                    "bid_source_registry": bid_source_registry,
                },
            )
            user_prompt = f"{input_profile}\n\n{rendered_prompt}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return await self._generate_with_json_check(
            messages=messages,
            schema=BID_REVIEW_SCHEMA,
            max_retries=3,
            temperature=0.3,
            response_format=None,
            log_prefix="标书复审",
            raise_on_fail=True,
            validator=lambda data: self._validate_bid_review_sources(
                data,
                tender_source_registry=tender_source_registry,
                bid_source_registry=bid_source_registry,
            ),
        )

    @staticmethod
    def _validate_bid_review_sources(
        data: Any,
        *,
        tender_source_registry: str,
        bid_source_registry: str,
    ) -> tuple[bool, str]:
        """校验复审结果中的证据锚点是否可回链到输入目录。"""
        if not isinstance(data, dict):
            return False, "复审结果必须是对象"

        items = data.get("items", [])
        if not isinstance(items, list) or not items:
            return False, "复审结果必须包含 items 数组"

        allowed_ref_ids: set[str] = set()
        for registry_text in (tender_source_registry, bid_source_registry):
            for line in (registry_text or "").splitlines():
                line = line.strip()
                if line.startswith("- "):
                    ref_id = line[2:].split(" | ", 1)[0].strip()
                    if ref_id:
                        allowed_ref_ids.add(ref_id)

        if not allowed_ref_ids:
            return False, "缺少可用于回链的来源锚点目录"

        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                return False, f"第 {index} 个评分项不是对象"

            source_refs = item.get("source_refs")
            if not isinstance(source_refs, list) or not source_refs:
                return False, f"第 {index} 个评分项缺少 source_refs 证据锚点"

            for ref in source_refs:
                if not isinstance(ref, dict):
                    return False, f"第 {index} 个评分项的 source_refs 格式无效"
                ref_id = str(ref.get("ref_id") or "").strip()
                source_type = str(ref.get("source_type") or "").strip()
                location = str(ref.get("location") or "").strip()
                quote = str(ref.get("quote") or "").strip()
                relation = str(ref.get("relation") or "").strip()

                if not ref_id or ref_id not in allowed_ref_ids:
                    return False, f"第 {index} 个评分项的证据锚点 {ref_id or '空值'} 不在允许目录中"
                if source_type not in {"tender_document", "bid_content", "knowledge_context"}:
                    return False, f"第 {index} 个评分项的证据锚点来源类型无效"
                if not location:
                    return False, f"第 {index} 个评分项的证据锚点缺少 location"
                if not quote:
                    return False, f"第 {index} 个评分项的证据锚点缺少 quote"
                if not relation:
                    return False, f"第 {index} 个评分项的证据锚点缺少 relation"

        return True, ""

    async def generate_clause_response(
        self,
        clause_text: str,
        project_overview: str | None = None,
        knowledge_context: str | None = None,
        knowledge_source_registry: str | None = None,
    ) -> dict[str, Any]:
        """生成技术参数/条款逐条响应结果"""
        knowledge_context_text = knowledge_context or ""
        knowledge_source_registry_text = knowledge_source_registry or ""
        if self._prompt_service:
            prompt, _ = await self._prompt_service.get_prompt(
                "clause_response_generation", self._project_id
            )
            from .prompt_service import PromptService
            system_prompt, user_template = PromptService.split_prompt(prompt)
            system_prompt = self._append_json_output_contract(system_prompt, CLAUSE_RESPONSE_SCHEMA)
            input_profile = self._build_clause_response_input_profile(
                clause_text=clause_text,
                project_overview=project_overview or "",
                knowledge_context=knowledge_context_text,
                knowledge_source_registry=knowledge_source_registry_text,
            )
            user_prompt = PromptService.render_prompt(user_template, {
                "clause_text": clause_text,
                "project_overview": project_overview or "",
                "knowledge_context": knowledge_context_text,
                "knowledge_source_registry": knowledge_source_registry_text,
            })
            user_prompt = f"{input_profile}\n\n{user_prompt}"
        else:
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("clause_response_generation")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = self._append_json_output_contract(system_prompt, CLAUSE_RESPONSE_SCHEMA)
            input_profile = self._build_clause_response_input_profile(
                clause_text=clause_text,
                project_overview=project_overview or "",
                knowledge_context=knowledge_context_text,
                knowledge_source_registry=knowledge_source_registry_text,
            )
            user_prompt = PromptService.render_prompt(user_template, {
                "clause_text": clause_text,
                "project_overview": project_overview or "",
                "knowledge_context": knowledge_context_text,
                "knowledge_source_registry": knowledge_source_registry_text,
            })
            user_prompt = f"{input_profile}\n\n{user_prompt}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=CLAUSE_RESPONSE_SCHEMA,
            max_retries=3,
            temperature=0.4,
            response_format=None,
            log_prefix="条款逐条响应",
            raise_on_fail=True,
            validator=lambda data: self._validate_clause_response_sources(
                data,
                knowledge_source_registry=knowledge_source_registry_text,
            ),
        )

        parsed = json.loads(full_content.strip())
        return {
            "clause_text": str(parsed.get("clause_text") or clause_text).strip(),
            "summary": str(parsed.get("summary") or "").strip(),
            "items": parsed.get("items", []),
            "content": self._render_clause_response_markdown(parsed),
        }

    async def rewrite_chapter_with_suggestions(
        self,
        chapter_title: str,
        chapter_content: str,
        suggestions: List[str],
    ) -> str:
        """
        根据修改建议重写或生成章节内容

        Args:
            chapter_title: 章节标题
            chapter_content: 原始章节内容（可为空）
            suggestions: 修改建议列表

        Returns:
            重写/生成后的章节内容
        """
        import logging
        logger = logging.getLogger(__name__)

        # 构建修改建议文本
        suggestions_text = "\n".join([f"- {s}" for s in suggestions])

        # 判断是重写还是生成
        has_content = chapter_content and chapter_content.strip()

        if has_content:
            system_prompt = """你是一位专业的投标文件编辑专家。你的任务是根据修改建议重写章节内容，使其更贴合招标要求、更利于得分、更专业可信。

### 要求
1. 仔细阅读原始内容和修改建议，优先修正会影响得分、合规性和专业度的问题
2. 保留原有章节主旨和合理结构，但可为提升质量做必要重组
3. 只在修改建议涉及或为解决相关问题所必需的范围内调整内容，避免无关改写
4. 语言应正式、克制、专业，避免宣传腔、套话和明显 AI 痕迹
5. 不要编造未被原文或建议支持的项目事实、案例、数据、人员、设备、承诺
6. 若建议要求补强内容但缺少明确事实依据，应采用稳妥的投标方案式写法，而非写成既成事实

### 输出格式
直接输出修改后的完整章节内容，不要添加任何解释或说明。"""

            user_prompt = f"""### 章节标题
{chapter_title}

### 原始内容
{chapter_content}

### 修改建议
{suggestions_text}

请根据以上修改建议重写章节内容，重点提升针对性、完整性和可得分性。"""
        else:
            system_prompt = """你是一位专业的投标文件编辑专家。你的任务是根据章节标题和修改建议生成章节内容。

### 要求
1. 严格围绕章节标题和修改建议撰写内容，确保内容真正响应该章节应承担的要求
2. 内容要专业、具体、可执行，优先体现方案、方法、流程、保障和成果输出
3. 对修改建议中明确要求补充的点，必须全部覆盖
4. 语言要符合正式投标文本习惯，避免空泛宣传和绝对化承诺
5. 不要编造未被建议支持的项目事实、案例、数据、人员、设备、时间承诺

### 输出格式
直接输出生成的章节内容，不要添加章节标题或任何解释说明。"""

            user_prompt = f"""### 章节标题
{chapter_title}

### 修改建议（必须遵守）
{suggestions_text}

请根据以上章节标题和修改建议生成章节内容，确保内容可直接用于投标文件。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        logger.info(f"重写章节 - 章节标题: {chapter_title}")
        logger.info(f"重写章节 - 修改建议数: {len(suggestions)}")

        # 调用 LLM 生成重写内容（使用流式并收集结果）
        full_content = ""
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=0.3,
            max_tokens=8192
        ):
            full_content += chunk

        return full_content

    async def rewrite_chapter_with_suggestions_stream(
        self,
        chapter_title: str,
        chapter_content: str,
        suggestions: List[str],
    ) -> AsyncGenerator[str, None]:
        """
        根据修改建议重写章节内容（流式返回）

        Args:
            chapter_title: 章节标题
            chapter_content: 原始章节内容
            suggestions: 修改建议列表

        Yields:
            流式返回的重写内容
        """
        import logging
        logger = logging.getLogger(__name__)

        # 构建修改建议文本
        suggestions_text = "\n".join([f"- {s}" for s in suggestions])

        system_prompt = """你是一位专业的投标文件编辑专家。你的任务是根据修改建议重写章节内容，使其更贴合招标要求、更利于得分、更专业可信。

### 要求
1. 仔细阅读原始内容和修改建议，优先修正会影响得分、合规性和专业度的问题
2. 保留原有章节主旨和合理结构，但可为提升质量做必要重组
3. 只在修改建议涉及或为解决相关问题所必需的范围内调整内容，避免无关改写
4. 语言应正式、克制、专业，避免宣传腔、套话和明显 AI 痕迹
5. 不要编造未被原文或建议支持的项目事实、案例、数据、人员、设备、承诺
6. 若建议要求补强内容但缺少明确事实依据，应采用稳妥的投标方案式写法，而非写成既成事实

### 输出格式
直接输出修改后的完整章节内容，不要添加任何解释或说明。"""

        user_prompt = f"""### 章节标题
{chapter_title}

### 原始内容
{chapter_content}

### 修改建议
{suggestions_text}

请根据以上修改建议重写章节内容，重点提升针对性、完整性和可得分性。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        logger.info(f"重写章节(流式) - 章节标题: {chapter_title}")
        logger.info(f"重写章节(流式) - 修改建议数: {len(suggestions)}")

        # 流式返回重写内容
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=0.3,
            max_tokens=8192
        ):
            yield chunk
