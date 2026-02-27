"""提示词管理器（兼容层）

此模块保持向后兼容性，内部使用 builtin_prompts 模块。
新代码应直接使用 PromptService。

使用方式：
- 同步代码：直接调用此模块的函数
- 异步代码：使用 PromptService 获取可配置的提示词
"""

import re
from .builtin_prompts import get_builtin_prompt


def split_prompt(prompt: str) -> tuple[str, str]:
    """将合并后的 prompt 分割为 system_prompt 和 user_template"""
    parts = prompt.split("\n---\n", 1)
    if len(parts) == 2:
        system_part = parts[0].strip()
        user_part = parts[1].strip()
        # 移除 "# 系统指令" 和 "# 用户输入" 标题
        system_prompt = re.sub(r'^#\s*系统指令\s*\n', '', system_part, flags=re.IGNORECASE)
        user_template = re.sub(r'^#\s*用户输入\s*\n', '', user_part, flags=re.IGNORECASE)
        return (system_prompt.strip(), user_template.strip())
    else:
        system_prompt = re.sub(r'^#\s*系统指令\s*\n', '', prompt.strip(), flags=re.IGNORECASE)
        return (system_prompt.strip(), "")


def read_expand_outline_prompt():
    """从简版技术方案中提取目录的提示词（兼容函数）

    Returns:
        system_prompt: 系统提示词
    """
    builtin = get_builtin_prompt("outline_extract")
    if builtin:
        system_prompt, _ = split_prompt(builtin["prompt"])
        return system_prompt
    # 回退到硬编码（不应该发生）
    return """你是一个专业的标书编写专家。需要从用户提交的标书技术方案中，提取出目录结构。

要求：
1. 目录结构要全面覆盖技术标的所有必要目录，包含多级目录
2. 如果技术方案中有章节名称，则直接使用技术方案中的章节名称
3. 如果技术方案中没有章节名称，则结合全文，总结出章节名称
5. 返回标准JSON格式，包含章节编号、标题、描述和子章节，注意编号要连贯
6. 除了JSON结果外，不要输出任何其他内容

JSON格式要求：
{
  "outline": [
    {
      "id": "1",
      "title": "",
      "description": "",
      "children": []
    }
  ]
}
"""


def generate_outline_prompt(overview: str, requirements: str):
    """生成目录提示词（兼容函数）

    注意：此函数已废弃，新代码应使用 OpenAIService.generate_outline_v2

    Args:
        overview: 项目概述
        requirements: 技术评分要求

    Returns:
        (system_prompt, user_prompt)
    """
    builtin = get_builtin_prompt("outline_l1")
    if builtin:
        system_prompt, user_template = split_prompt(builtin["prompt"])
        # 简单变量替换
        user_prompt = user_template.replace("{{overview}}", overview)
        user_prompt = user_prompt.replace("{{requirements}}", requirements)
        return system_prompt, user_prompt

    # 回退到硬编码
    system_prompt = """你是一个专业的标书编写专家。根据提供的项目概述和技术评分要求，生成投标文件中技术标部分的目录结构。

要求：
1. 目录结构要全面覆盖技术标的所有必要章节
2. 章节名称要专业、准确，符合投标文件规范
3. 一级目录名称要与技术评分要求中的章节名称一致
4. 一共包括三级目录
5. 返回标准JSON格式
"""

    user_prompt = f"""请基于以下项目信息生成标书目录结构：

项目概述：
{overview}

技术评分要求：
{requirements}

请生成完整的技术标目录结构，确保覆盖所有技术评分要点。"""

    return system_prompt, user_prompt


def generate_outline_with_old_prompt(overview: str, requirements: str, old_outline: str):
    """结合旧目录生成新目录提示词（兼容函数）

    Args:
        overview: 项目概述
        requirements: 技术评分要求
        old_outline: 用户编写的旧目录

    Returns:
        (system_prompt, user_prompt)
    """
    # 使用 outline_l2l3 的系统提示词作为基础
    builtin = get_builtin_prompt("outline_l2l3")
    if builtin:
        system_prompt, _ = split_prompt(builtin["prompt"])
        # 构建用户提示词
        user_prompt = f"""### 项目信息

<overview>
{overview}
</overview>

<requirements>
{requirements}
</requirements>

<old_outline>
{old_outline}
</old_outline>

请结合用户编写的目录，生成完整的技术标目录结构，确保覆盖所有技术评分要点。"""
        return system_prompt, user_prompt

    # 回退到硬编码
    system_prompt = """你是一个专业的标书编写专家。根据提供的项目概述和技术评分要求，生成投标文件中技术标部分的目录结构。
用户会提供一个自己编写的目录，你要保证目录满足技术评分要求，并充分结合用户自己编写的目录。
"""

    user_prompt = f"""请基于以下项目信息生成标书目录结构：
用户自己编写的目录：
{old_outline}

项目概述：
{overview}

技术评分要求：
{requirements}

请生成完整的技术标目录结构，确保覆盖所有技术评分要点。"""

    return system_prompt, user_prompt


# 导出兼容函数
__all__ = [
    "read_expand_outline_prompt",
    "generate_outline_prompt",
    "generate_outline_with_old_prompt",
]
