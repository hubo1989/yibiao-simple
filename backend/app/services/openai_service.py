"""OpenAI服务"""
import openai
from typing import Dict, Any, List, AsyncGenerator
import json
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.outline_util import get_random_indexes, calculate_nodes_distribution, generate_one_outline_json_by_level1
from ..utils.json_util import check_json
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
            self.api_key = encryption_service.decrypt(config.api_key_encrypted)
            self.base_url = config.base_url or ''
            self.model_name = config.model_name
            return True
        return False

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

            # 初始化 OpenAI 客户端
            self._client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url if self.base_url else None
            )

            # 初始化 PromptService
            if self._db:
                self._prompt_service = PromptService(self._db)

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
        max_tokens: int = 4096
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

            isok, error_msg = check_json(str(full_content), schema)
            if isok:
                return full_content

            last_error_msg = error_msg
            prefix = f"{log_prefix} " if log_prefix else ""

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
                result_outline['outline'], [], project_overview, knowledge_context
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
                ):
                    content += chunk
                if content:
                    chapter['content'] = content
            else:
                # 递归处理子章节
                await self._process_outline_recursive(
                    chapter['children'], current_parent_chapters, project_overview, knowledge_context
                )
    
    async def _generate_chapter_content(
        self,
        chapter: dict,
        parent_chapters: list = None,
        sibling_chapters: list = None,
        project_overview: str = "",
        knowledge_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        为单个章节流式生成内容

        Args:
            chapter: 章节数据
            parent_chapters: 上级章节列表，每个元素包含章节id、标题和描述
            sibling_chapters: 同级章节列表，避免内容重复
            project_overview: 项目概述信息，提供项目背景和要求
            knowledge_context: 知识库检索结果，提供参考资料

        Yields:
            生成的内容流
        """
        try:
            chapter_id = chapter.get('id', 'unknown')
            chapter_title = chapter.get('title', '未命名章节')
            chapter_description = chapter.get('description', '')

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
                # 简单渲染
                user_prompt = user_template.replace("{{chapter_id}}", chapter_id)
                user_prompt = user_prompt.replace("{{chapter_title}}", chapter_title)
                user_prompt = user_prompt.replace("{{chapter_description}}", chapter_description)
                if project_overview:
                    user_prompt = user_prompt.replace("{{project_overview}}", project_overview)
                if knowledge_context:
                    user_prompt = user_prompt.replace("{{knowledge_context}}", knowledge_context)

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
            yield f"错误: {str(e)}"

    async def generate_outline_v2(self, overview: str, requirements: str) -> Dict[str, Any]:
        schema_json = json.dumps([
            {
                "rating_item": "原评分项",
                "new_title": "根据评分项修改的标题",
            }
        ])

        # 使用 PromptService 获取提示词
        if self._prompt_service:
            prompt, _ = await self._prompt_service.get_prompt(
                "outline_l1", self._project_id
            )
            from .prompt_service import PromptService
            system_prompt, user_template = PromptService.split_prompt(prompt)
            user_prompt = self._prompt_service.render_prompt(user_template, {
                "overview": overview,
                "requirements": requirements,
            })
        else:
            # 回退到内置提示词
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("outline_l1")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = system_prompt + f"\n\n### Output Format in JSON\n{schema_json}"
            user_prompt = self._prompt_service.render_prompt(user_template, {
                "overview": overview,
                "requirements": requirements,
            }) if self._prompt_service else user_template.replace("{{overview}}", overview).replace("{{requirements}}", requirements)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 使用通用方法进行 JSON 校验与重试（失败时抛出异常）
        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=schema_json,
            max_retries=3,
            temperature=0.7,
            response_format={"type": "json_object"},
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
            user_prompt = self._prompt_service.render_prompt(user_template, {
                "overview": overview,
                "requirements": requirements,
                "other_outline": other_outline,
                "current_outline_json": json_outline,
            })
        else:
            # 回退到内置提示词
            from ..utils.builtin_prompts import get_builtin_prompt
            from .prompt_service import PromptService
            builtin = get_builtin_prompt("outline_l2l3")
            system_prompt, user_template = PromptService.split_prompt(builtin["prompt"])
            system_prompt = system_prompt + f"\n\n### Output Format in JSON\n{json_outline}"
            user_prompt = f"""
    ### 项目信息

    <overview>
    {overview}
    </overview>

    <requirements>
    {requirements}
    </requirements>

    <other_outline>
    {other_outline}
    </other_outline>

    <current_outline_json>
    {json_outline}
    </current_outline_json>

    直接返回json，不要任何额外说明或格式标记
    """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 使用通用方法进行 JSON 校验与重试（失败时不抛异常，保持原有"返回最后一次结果"的行为）
        full_content = await self._generate_with_json_check(
            messages=messages,
            schema=json_outline,
            max_retries=3,
            temperature=0.7,
            response_format={"type": "json_object"},
            log_prefix=f"第{i+1}章",
            raise_on_fail=False,
        )

        return json.loads(full_content.strip())

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
            user_prompt = self._prompt_service.render_prompt(user_template, {
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
            # 构建章节摘要
            chapters_text = "\n\n".join([
                f"【{ch.get('chapter_number', '')} {ch.get('title', '')}】\n{ch.get('summary', '')}"
                for ch in []
            ])
            user_prompt = user_template.replace("{{chapter_title}}", chapter_title)
            user_prompt = user_prompt.replace("{{chapter_content}}", chapter_content)
            user_prompt = user_prompt.replace("{{tech_requirements}}", tech_requirements)
            if project_overview:
                user_prompt = user_prompt.replace("{{project_overview}}", project_overview)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 流式返回校对结果
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=0.3,  # 较低温度以获得更稳定的校对结果
            response_format={"type": "json_object"}
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
            user_prompt = self._prompt_service.render_prompt(user_template, {
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
            user_prompt = user_template.replace("{{chapter_summaries}}", chapters_text)
            if project_overview:
                user_prompt = user_prompt.replace("{{project_overview}}", project_overview)
            if tech_requirements:
                user_prompt = user_prompt.replace("{{tech_requirements}}", tech_requirements)

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
            system_prompt = """你是一位专业的标书编辑专家。你的任务是根据修改建议重写章节内容。

### 要求
1. 仔细阅读原始内容和修改建议
2. 根据建议修改内容，保持专业性和连贯性
3. 保留原有的结构和格式
4. 只修改与建议相关的部分，不要改动其他内容
5. 修改后的内容应该更加准确、一致、专业

### 输出格式
直接输出修改后的完整章节内容，不要添加任何解释或说明。"""

            user_prompt = f"""### 章节标题
{chapter_title}

### 原始内容
{chapter_content}

### 修改建议
{suggestions_text}

请根据以上修改建议重写章节内容。"""
        else:
            system_prompt = """你是一位专业的标书编辑专家。你的任务是根据章节标题和修改建议生成章节内容。

### 要求
1. 根据章节标题和修改建议，撰写专业、完整的标书章节内容
2. 内容要针对招标文件的要求，具有说服力
3. 确保内容与修改建议完全一致
4. 内容要详实、专业，符合标书规范

### 输出格式
直接输出生成的章节内容，不要添加章节标题或任何解释说明。"""

            user_prompt = f"""### 章节标题
{chapter_title}

### 修改建议（必须遵守）
{suggestions_text}

请根据以上章节标题和修改建议生成章节内容。"""

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

        system_prompt = """你是一位专业的标书编辑专家。你的任务是根据修改建议重写章节内容。

### 要求
1. 仔细阅读原始内容和修改建议
2. 根据建议修改内容，保持专业性和连贯性
3. 保留原有的结构和格式
4. 只修改与建议相关的部分，不要改动其他内容
5. 修改后的内容应该更加准确、一致、专业

### 输出格式
直接输出修改后的完整章节内容，不要添加任何解释或说明。"""

        user_prompt = f"""### 章节标题
{chapter_title}

### 原始内容
{chapter_content}

### 修改建议
{suggestions_text}

请根据以上修改建议重写章节内容。"""

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