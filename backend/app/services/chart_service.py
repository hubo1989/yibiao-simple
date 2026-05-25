"""图表自动生成服务 - 识别章节内容中的图表需求并生成 Mermaid 代码"""
import logging
import re
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .openai_service import OpenAIService

logger = logging.getLogger(__name__)

# 图表类型检测模式：(关键词列表, Mermaid图表类型, 图表方向)
CHART_DETECTION_PATTERNS = [
    # 系统架构 / 技术架构 / 网络拓扑 → flowchart TB
    (
        ["系统架构", "技术架构", "网络拓扑", "总体架构", "部署架构",
         "系统结构", "平台架构", "云架构", "微服务架构"],
        "flowchart",
        "TB",
    ),
    # 组织架构 / 项目团队 → flowchart TB
    (
        ["组织架构", "项目团队", "团队结构", "人员配置", "管理架构",
         "项目组织", "团队组成", "人员组织"],
        "flowchart",
        "TB",
    ),
    # 流程图 / 业务流程 → flowchart LR
    (
        ["流程图", "业务流程", "工作流程", "处理流程", "操作流程",
         "审批流程", "数据流程", "业务逻辑", "执行流程"],
        "flowchart",
        "LR",
    ),
    # 实施计划 / 进度安排 / 甘特图 → gantt
    (
        ["实施计划", "进度安排", "甘特图", "项目计划", "工期安排",
         "时间计划", "里程碑", "进度表", "施工计划", "交付计划"],
        "gantt",
        "",
    ),
    # 时序图 / 交互流程 → sequenceDiagram
    (
        ["时序图", "交互流程", "消息流程", "调用流程", "接口调用",
         "请求响应", "数据交互"],
        "sequenceDiagram",
        "",
    ),
]

# 图表生成 Prompt 模板
CHART_PROMPT_TEMPLATES = {
    "flowchart": (
        """请根据以下章节内容，生成一个 Mermaid.js flowchart 图表，方向为{direction}。

要求：
1. 使用中文节点标签
2. 节点数量 5-15 个，层级清晰
3. 使用不同的节点形状：矩形(方框[])、圆角(())、菱形{{}}表示判断
4. 有明确的层级和连接关系
5. 只输出 Mermaid 代码块，不要输出任何其他内容

章节内容：
{content}

请输出 mermaid 代码块："""
    ),
    "gantt": (
        """请根据以下章节内容，生成一个 Mermaid.js gantt 甘特图。

要求：
1. 使用中文任务名称
2. 包含 5-10 个主要任务/阶段
3. 每个任务有合理的时间范围（使用日期格式 YYYY-MM-DD）
4. 标注关键里程碑
5. 只输出 Mermaid 代码块，不要输出任何其他内容

章节内容：
{content}

请输出 mermaid 代码块："""
    ),
    "sequenceDiagram": (
        """请根据以下章节内容，生成一个 Mermaid.js sequenceDiagram 时序图。

要求：
1. 使用中文参与者名称
2. 包含 3-6 个参与者
3. 展示核心交互流程，5-10 步
4. 可以使用 Note 标注关键步骤
5. 只输出 Mermaid 代码块，不要输出任何其他内容

章节内容：
{content}

请输出 mermaid 代码块："""
    ),
}

# Mermaid 代码块提取正则
MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


class ChartService:
    """图表自动生成服务

    识别 Markdown 内容中的图表需求，使用 LLM 生成 Mermaid 代码，
    并支持将 Mermaid 渲染为图片（通过 Kroki API）。
    """

    def __init__(self, openai_service: Optional[OpenAIService] = None):
        self._openai_service = openai_service
        self._kroki_base_url = "https://kroki.io"

    @classmethod
    def detect_chart_needs(
        cls,
        chapter_title: str,
        chapter_content: str,
    ) -> List[Dict[str, Any]]:
        """扫描章节内容，检测需要生成的图表类型

        Args:
            chapter_title: 章节标题
            chapter_content: 章节 Markdown 内容

        Returns:
            图表需求列表，每项包含 {chart_type, mermaid_type, direction, trigger_keyword}
        """
        combined_text = f"{chapter_title}\n{chapter_content[:3000]}"
        detected = []

        for keywords, mermaid_type, direction in CHART_DETECTION_PATTERNS:
            for kw in keywords:
                if kw in combined_text:
                    detected.append({
                        "chart_type": mermaid_type,
                        "mermaid_type": mermaid_type,
                        "direction": direction,
                        "trigger_keyword": kw,
                        "section_context": cls._extract_section_context(
                            combined_text, kw
                        ),
                    })
                    break  # 每个类别只触发一次

        return detected

    @staticmethod
    def _extract_section_context(text: str, keyword: str) -> str:
        """提取包含关键词的上下文段落（前后各 300 字符）"""
        idx = text.find(keyword)
        if idx < 0:
            return text[:600]
        start = max(0, idx - 300)
        end = min(len(text), idx + len(keyword) + 300)
        return text[start:end]

    async def generate_mermaid_code(
        self,
        chart_type: str,
        direction: str,
        section_context: str,
    ) -> Optional[str]:
        """使用 LLM 生成 Mermaid 代码

        Args:
            chart_type: 图表类型 (flowchart/gantt/sequenceDiagram)
            direction: 图表方向 (TB/LR/)
            section_context: 上下文内容

        Returns:
            Mermaid 代码字符串，或 None
        """
        if not self._openai_service:
            logger.warning("ChartService: no OpenAIService available, skipping chart generation")
            return None

        prompt_template = CHART_PROMPT_TEMPLATES.get(chart_type)
        if not prompt_template:
            logger.warning(f"ChartService: unknown chart type '{chart_type}'")
            return None

        prompt = prompt_template.format(
            direction=direction or "TB",
            content=section_context[:3000],
        )

        try:
            messages = [
                {
                    "role": "system",
                    "content": "你是一个 Mermaid.js 图表生成专家。只输出 Mermaid 代码块，不输出任何解释。",
                },
                {"role": "user", "content": prompt},
            ]

            full_response = ""
            async for chunk in self._openai_service.stream_chat_completion(
                messages, temperature=0.2
            ):
                full_response += chunk

            # 提取 Mermaid 代码
            mermaid_code = self._extract_mermaid_code(full_response)
            if mermaid_code:
                logger.info(
                    f"ChartService: generated {chart_type} chart "
                    f"({len(mermaid_code)} chars)"
                )
                return mermaid_code
            else:
                logger.warning("ChartService: LLM response contained no mermaid block")
                return None

        except Exception as e:
            logger.error(f"ChartService: generation failed: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _extract_mermaid_code(text: str) -> Optional[str]:
        """从 LLM 返回中提取 Mermaid 代码块"""
        # 优先匹配 ```mermaid ... ```
        match = MERMAID_BLOCK_RE.search(text)
        if match:
            return match.group(1).strip()

        # 尝试匹配 ``` ... ``` （四个及以上反引号包裹）
        block_re = re.compile(r"```(?:mermaid)?\s*\n(.*?)```", re.DOTALL)
        match = block_re.search(text)
        if match:
            return match.group(1).strip()

        # 如果看起来已经是 Mermaid 代码（以 graph/flowchart/gantt 等开头）
        stripped = text.strip()
        mermaid_starts = ("graph ", "flowchart ", "gantt", "sequenceDiagram", "classDiagram",
                          "stateDiagram", "erDiagram", "pie", "mindmap", "timeline")
        for start in mermaid_starts:
            if stripped.startswith(start):
                return stripped

        return None

    def render_mermaid_block(self, mermaid_code: str) -> str:
        """将 Mermaid 代码包装为 Markdown 代码块

        Args:
            mermaid_code: Mermaid 代码

        Returns:
            格式化的 Markdown 代码块
        """
        return f"\n\n```mermaid\n{mermaid_code}\n```\n\n"

    @staticmethod
    def get_kroki_url(mermaid_code: str) -> str:
        """生成 Kroki API URL 用于将 Mermaid 渲染为 SVG

        Args:
            mermaid_code: Mermaid 代码

        Returns:
            Kroki API URL
        """
        import base64
        import zlib

        # 使用 deflate + base64 编码（Kroki 标准）
        compressed = zlib.compress(mermaid_code.encode("utf-8"), 9)
        encoded = base64.urlsafe_b64encode(compressed).decode("utf-8")
        return f"https://kroki.io/mermaid/svg/{encoded}"

    async def generate_charts_for_content(
        self,
        chapter_title: str,
        chapter_content: str,
    ) -> List[Dict[str, Any]]:
        """为章节内容生成所有需要的图表

        Args:
            chapter_title: 章节标题
            chapter_content: 章节 Markdown 内容

        Returns:
            图表列表，每项包含 {chart_type, mermaid_code, markdown_block, kroki_url}
        """
        needs = self.detect_chart_needs(chapter_title, chapter_content)
        if not needs:
            return []

        charts = []
        for need in needs:
            mermaid_code = await self.generate_mermaid_code(
                chart_type=need["chart_type"],
                direction=need["direction"],
                section_context=need.get("section_context", chapter_content[:2000]),
            )
            if mermaid_code:
                markdown_block = self.render_mermaid_block(mermaid_code)
                charts.append({
                    "chart_type": need["chart_type"],
                    "mermaid_type": need["mermaid_type"],
                    "trigger_keyword": need.get("trigger_keyword", ""),
                    "mermaid_code": mermaid_code,
                    "markdown_block": markdown_block,
                    "kroki_url": self.get_kroki_url(mermaid_code),
                })

        return charts
