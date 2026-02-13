"""OpenAI服务"""
import openai
from typing import Dict, Any, List, AsyncGenerator
import json
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.outline_util import get_random_indexes, calculate_nodes_distribution, generate_one_outline_json_by_level1
from ..utils.json_util import check_json
from ..utils.config_manager import config_manager
from ..utils.encryption import encryption_service
from ..models.api_key_config import ApiKeyConfig
from ..db.database import async_session_factory


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

    def __init__(self, db: AsyncSession | None = None):
        """
        初始化OpenAI服务

        Args:
            db: 可选的数据库会话。如果提供，将从数据库读取默认配置；
                否则使用同步方式从数据库获取配置
        """
        self._db = db
        self.api_key = ''
        self.base_url = ''
        self.model_name = 'gpt-3.5-turbo'
        self._client = None

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

    @property
    def client(self):
        """获取 OpenAI 客户端（向后兼容）"""
        if self._client is None:
            # 同步初始化（仅在无法使用 async 的情况下）
            raise RuntimeError("OpenAIService 需要先调用 async 方法进行初始化")
        return self._client
    
    async def get_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        await self._ensure_initialized()
        try:
            models = await self._client.models.list()
            chat_models = []
            for model in models.data:
                model_id = model.id.lower()
                if any(keyword in model_id for keyword in ['gpt', 'claude', 'chat', 'llama', 'qwen', 'deepseek']):
                    chat_models.append(model.id)
            return sorted(list(set(chat_models)))
        except Exception as e:
            raise Exception(f"获取模型列表失败: {str(e)}")
    
    async def stream_chat_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        response_format: dict = None
    ) -> AsyncGenerator[str, None]:
        """流式聊天完成请求 - 真正的异步实现"""
        await self._ensure_initialized()
        try:
            stream = await self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                stream=True,
                **({"response_format": response_format} if response_format is not None else {})
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"错误: {str(e)}"

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

            # 构建提示词
            system_prompt = """你是一个专业的标书编写专家，负责为投标文件的技术标部分生成具体内容。

要求：
1. 内容要专业、准确，与章节标题和描述保持一致
2. 这是技术方案，不是宣传报告，注意朴实无华，不要假大空
3. 语言要正式、规范，符合标书写作要求，但不要使用奇怪的连接词，不要让人觉得内容像是AI生成的
4. 内容要详细具体，避免空泛的描述
5. 注意避免与同级章节内容重复，保持内容的独特性和互补性
6. 直接返回章节内容，不生成标题，不要任何额外说明或格式标记
7. 如果提供了参考资料，请在相关部分合理引用，但要自然融入你的行文，不要直接大段复制
"""

            # 构建上下文信息
            context_info = ""

            # 上级章节信息
            if parent_chapters:
                context_info += "上级章节信息：\n"
                for parent in parent_chapters:
                    context_info += f"- {parent['id']} {parent['title']}\n  {parent['description']}\n"

            # 同级章节信息（排除当前章节）
            if sibling_chapters:
                context_info += "同级章节信息（请避免内容重复）：\n"
                for sibling in sibling_chapters:
                    if sibling.get('id') != chapter_id:  # 排除当前章节
                        context_info += f"- {sibling.get('id', 'unknown')} {sibling.get('title', '未命名')}\n  {sibling.get('description', '')}\n"

            # 构建用户提示词
            project_info = ""
            if project_overview.strip():
                project_info = f"项目概述信息：\n{project_overview}\n\n"

            # 知识库参考资料
            knowledge_info = ""
            if knowledge_context.strip():
                knowledge_info = f"""参考资料（来自企业知识库）：
{knowledge_context}

请参考以上资料中与当前章节相关的内容，在生成时自然融入，展示企业的技术实力和项目经验。

"""

            user_prompt = f"""请为以下标书章节生成具体内容：

{project_info}{knowledge_info}{context_info if context_info else ''}当前章节信息：
章节ID: {chapter_id}
章节标题: {chapter_title}
章节描述: {chapter_description}

请根据项目概述信息、参考资料和上述章节层级关系，生成详细的专业内容，确保与上级章节的内容逻辑相承，同时避免与同级章节内容重复，突出本章节的独特性和技术方案的优势。"""

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

        system_prompt = f"""
            ### 角色
            你是专业的标书编写专家，擅长根据项目需求编写标书。
            
            ### 人物
            1. 根据得到的项目概述(overview)和评分要求(requirements)，撰写技术标部分的一级提纲
            
            ### 说明
            1. 只设计一级标题，数量要和"评分要求"一一对应
            2. 一级标题名称要进行简单修改，不能完全使用"评分要求"中的文字

            
            ### Output Format in JSON
            {schema_json}

            """
        user_prompt = f"""
            ### 项目信息
            
            <overview>
            {overview}
            </overview>

            <requirements>
            {requirements}
            </requirements>


            直接返回json，不要任何额外说明或格式标记

            """
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

        system_prompt = f"""
    ### 角色
    你是专业的标书编写专家，擅长根据项目需求编写标书。
    
    ### 任务
    1. 根据得到项目概述(overview)、评分要求(requirements)补全标书的提纲的二三级目录
    
    ### 说明
    1. 你将会得到一段json，这是提纲的其中一个章节，你需要再原结构上补全标题(title)和描述(description)
    2. 二级标题根据一级标题撰写,三级标题根据二级标题撰写
    3. 补全的内容要参考项目概述(overview)、评分要求(requirements)等项目信息
    4. 你还会收到其他章节的标题(other_outline)，你需要确保本章节的内容不会包含其他章节的内容
    
    ### 注意事项
    在原json上补全信息，禁止修改json结构，禁止修改一级标题

    ### Output Format in JSON
    {json_outline}

    """
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


    直接返回json，不要任何额外说明或格式标记

    """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 使用通用方法进行 JSON 校验与重试（失败时不抛异常，保持原有“返回最后一次结果”的行为）
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
        schema_json = json.dumps({
            "issues": [
                PROOFREAD_ISSUE_SCHEMA
            ],
            "summary": "整体问题摘要"
        })

        # 构建同级章节信息
        sibling_info = ""
        if sibling_chapter_titles:
            sibling_info = f"""
<同级章节标题>
{chr(10).join(f'- {title}' for title in sibling_chapter_titles)}
</同级章节标题>
"""

        project_info = ""
        if project_overview:
            project_info = f"""
<项目概述>
{project_overview}
</项目概述>
"""

        system_prompt = f"""### 角色
你是专业的标书审核专家，负责检查标书内容的质量问题。

### 任务
对提供的章节内容进行全面校对，识别以下类型的问题：

1. **合规性问题 (compliance)**: 内容是否符合招标文件的评分要求和技术规范
2. **语言质量问题 (language)**: 语法错误、表达不当、用词不准确等
3. **一致性问题 (consistency)**: 内容前后矛盾、数据不一致、逻辑混乱
4. **冗余问题 (redundancy)**: 与同级章节内容重复、不必要的重复表述

### 严重程度定义
- **critical**: 严重问题，可能导致失分或被废标
- **warning**: 一般问题，建议修改以提高质量
- **info**: 轻微问题或优化建议

### 输出格式
返回 JSON 格式，包含 issues 数组和 summary 摘要：
{schema_json}

### 注意事项
- 问题定位要准确，position 描述应能让用户快速定位
- 修改建议要具体可操作
- 如果没有发现问题，返回空数组
"""

        user_prompt = f"""### 项目信息
{project_info}
<招标文件评分要求>
{tech_requirements}
</招标文件评分要求>
{sibling_info}

### 待校对章节
<章节标题>
{chapter_title}
</章节标题>

<章节内容>
{chapter_content}
</章节内容>

请根据招标文件的评分要求对上述内容进行全面校对，输出 JSON 格式的校对结果。
"""

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
        schema_json = json.dumps({
            "contradictions": [
                CONSISTENCY_CONTRADICTION_SCHEMA
            ],
            "summary": "整体一致性评估摘要",
            "overall_consistency": "consistent|minor_issues|major_issues"
        })

        # 构建章节摘要信息
        chapters_info = []
        for chapter in chapter_summaries:
            chapters_info.append(
                f"【{chapter.get('chapter_number', '')} {chapter.get('title', '')}】\n"
                f"{chapter.get('summary', '')}"
            )
        chapters_text = "\n\n".join(chapters_info)

        project_info = ""
        if project_overview:
            project_info = f"""
<项目概述>
{project_overview}
</项目概述>
"""

        requirements_info = ""
        if tech_requirements:
            requirements_info = f"""
<招标文件技术要求>
{tech_requirements}
</招标文件技术要求>
"""

        system_prompt = f"""### 角色
你是专业的标书审核专家，负责检查标书中跨章节的一致性问题。

### 任务
分析提供的章节摘要，检测以下类型的跨章节矛盾：

1. **数据矛盾 (data)**: 同一数据在不同章节中数值不一致
   - 例：A章节承诺"10名工程师"，B章节写"15名工程师"
   - 例：A章节预算"500万"，B章节预算"600万"

2. **术语矛盾 (terminology)**: 同一概念使用不同术语或定义不一致
   - 例：A章节称"项目经理"，B章节称"项目负责人"
   - 例：同一产品名称在不同章节拼写不同

3. **时间线矛盾 (timeline)**: 项目计划时间节点冲突
   - 例：A章节说"第一阶段1个月"，B章节说"第一阶段2周"
   - 例：交付日期不一致

4. **承诺矛盾 (commitment)**: 服务承诺或保证不一致
   - 例：A章节承诺"7×24小时服务"，B章节写"工作日服务"
   - 例：质保期年限不一致

5. **范围矛盾 (scope)**: 工作范围描述不一致
   - 例：A章节说"包含系统A"，B章节说"不包含系统A"

### 严重程度定义
- **critical**: 严重矛盾，可能导致失分或废标，必须修改
- **warning**: 一般不一致，建议统一以提高专业度
- **info**: 轻微差异，可以优化

### 输出格式
返回 JSON 格式，包含 contradictions 数组、summary 摘要和 overall_consistency 评估：
{schema_json}

### 注意事项
- 只报告真实的矛盾，不要过度解读
- 如果没有发现矛盾，返回空数组，overall_consistency 为 "consistent"
- 每个矛盾必须涉及至少两个不同章节
"""

        user_prompt = f"""### 项目信息
{project_info}{requirements_info}
### 章节摘要汇总

{chapters_text}

请分析以上章节摘要，检测跨章节的一致性问题，输出 JSON 格式的检查结果。
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 流式返回一致性检查结果
        async for chunk in self.stream_chat_completion(
            messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        ):
            yield chunk