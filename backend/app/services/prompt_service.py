"""提示词服务

实现三层优先级回退：项目级 > 管理员全局 > 系统内置
"""

import re
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.global_prompt import GlobalPrompt, GlobalPromptVersion, PromptCategory
from ..models.project import Project
from ..utils.builtin_prompts import get_builtin_prompt, get_all_builtin_prompts, get_builtin_scene_keys


class PromptService:
    """提示词服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def split_prompt(prompt: str) -> tuple[str, str]:
        """
        将合并后的 prompt 分割为 system_prompt 和 user_template

        格式：
        # 系统指令
        ...
        ---
        # 用户输入
        ...

        Returns:
            (system_prompt, user_template)
        """
        # 使用 --- 作为分隔符
        parts = prompt.split("\n---\n", 1)

        if len(parts) == 2:
            system_part = parts[0].strip()
            user_part = parts[1].strip()

            # 移除 "# 系统指令" 和 "# 用户输入" 标题
            system_prompt = re.sub(r'^#\s*系统指令\s*\n', '', system_part, flags=re.IGNORECASE)
            user_template = re.sub(r'^#\s*用户输入\s*\n', '', user_part, flags=re.IGNORECASE)

            return (system_prompt.strip(), user_template.strip())
        else:
            # 如果没有分隔符，整个作为 system_prompt，user_template 为空
            system_prompt = re.sub(r'^#\s*系统指令\s*\n', '', prompt.strip(), flags=re.IGNORECASE)
            return (system_prompt.strip(), "")

    async def get_prompt(
        self,
        scene_key: str,
        project_id: Optional[uuid.UUID] = None,
    ) -> tuple[str, str]:
        """
        获取提示词（三层回退）

        Args:
            scene_key: 场景标识
            project_id: 项目ID（可选）

        Returns:
            (prompt, source)
            source 为 "project" | "global" | "builtin"
        """
        # 1. 尝试项目级自定义
        if project_id:
            project_prompt = await self._get_project_prompt(scene_key, project_id)
            if project_prompt:
                return (project_prompt, "project")

        # 2. 尝试全局配置
        global_prompt = await self._get_global_prompt(scene_key)
        if global_prompt:
            return (global_prompt, "global")

        # 3. 内置默认
        builtin = get_builtin_prompt(scene_key)
        if builtin:
            return (builtin["prompt"], "builtin")

        raise ValueError(f"未找到场景 {scene_key} 的提示词配置")

    async def _get_project_prompt(
        self,
        scene_key: str,
        project_id: uuid.UUID,
    ) -> Optional[str]:
        """获取项目级自定义提示词"""
        result = await self.db.execute(
            select(Project.custom_prompts).where(Project.id == project_id)
        )
        custom_prompts = result.scalar_one_or_none()

        if custom_prompts and scene_key in custom_prompts:
            prompt_config = custom_prompts[scene_key]
            if isinstance(prompt_config, dict):
                return prompt_config.get("prompt")
            elif isinstance(prompt_config, str):
                return prompt_config

        return None

    async def _get_global_prompt(
        self,
        scene_key: str,
    ) -> Optional[str]:
        """获取全局提示词配置"""
        result = await self.db.execute(
            select(GlobalPrompt).where(GlobalPrompt.scene_key == scene_key)
        )
        global_prompt = result.scalar_one_or_none()

        if global_prompt:
            return global_prompt.prompt

        return None

    def render_prompt(self, template: str, variables: dict[str, Any]) -> str:
        """
        渲染提示词模板，替换变量

        支持 Handlebars 风格语法：
        - {{variable}} - 简单变量替换
        - {{#if variable}}...{{/if}} - 条件渲染
        - {{#each array}}...{{/each}} - 列表迭代

        Args:
            template: 提示词模板
            variables: 变量字典

        Returns:
            渲染后的文本
        """
        result = template

        # 处理条件块 {{#if var}}...{{/if}}
        if_pattern = r'\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}'
        while True:
            match = re.search(if_pattern, result, re.DOTALL)
            if not match:
                break
            var_name = match.group(1)
            content = match.group(2)
            var_value = variables.get(var_name)
            # 变量存在且非空时保留内容
            if var_value and (not isinstance(var_value, (list, dict)) or var_value):
                result = result[:match.start()] + content + result[match.end():]
            else:
                result = result[:match.start()] + result[match.end():]

        # 处理列表迭代 {{#each var}}...{{/each}}
        each_pattern = r'\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}'
        while True:
            match = re.search(each_pattern, result, re.DOTALL)
            if not match:
                break
            var_name = match.group(1)
            item_template = match.group(2)
            var_value = variables.get(var_name, [])

            if isinstance(var_value, list):
                items = []
                for item in var_value:
                    item_text = item_template
                    if isinstance(item, dict):
                        # 替换 {{this.key}}
                        for key, val in item.items():
                            item_text = item_text.replace(f"{{{{this.{key}}}}}", str(val) if val else "")
                    else:
                        item_text = item_text.replace("{{this}}", str(item))
                    items.append(item_text.strip())
                replacement = "\n".join(items)
            else:
                replacement = ""

            result = result[:match.start()] + replacement + result[match.end():]

        # 处理简单变量 {{variable}}
        var_pattern = r'\{\{(\w+)\}\}'
        for match in re.finditer(var_pattern, result):
            var_name = match.group(1)
            var_value = variables.get(var_name, "")
            if var_value is None:
                var_value = ""
            elif isinstance(var_value, (list, dict)):
                var_value = str(var_value)
            result = result.replace(match.group(0), str(var_value))

        return result

    async def get_prompt_with_source_info(
        self,
        scene_key: str,
        project_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """
        获取提示词及其来源信息

        Returns:
            {
                "prompt": str,
                "source": str,
                "has_project_override": bool,
                "has_global_override": bool,
            }
        """
        # 检查项目级
        if project_id:
            project_prompt = await self._get_project_prompt(scene_key, project_id)
            if project_prompt:
                builtin = get_builtin_prompt(scene_key)
                return {
                    "prompt": project_prompt,
                    "source": "project",
                    "has_project_override": True,
                    "has_global_override": await self._has_global_override(scene_key),
                    "available_vars": builtin.get("available_vars") if builtin else None,
                }

        # 检查全局
        global_prompt = await self._get_global_prompt(scene_key)
        if global_prompt:
            builtin = get_builtin_prompt(scene_key)
            return {
                "prompt": global_prompt,
                "source": "global",
                "has_project_override": False,
                "has_global_override": True,
                "available_vars": builtin.get("available_vars") if builtin else None,
            }

        # 内置
        builtin = get_builtin_prompt(scene_key)
        if builtin:
            return {
                "prompt": builtin["prompt"],
                "source": "builtin",
                "has_project_override": False,
                "has_global_override": False,
                "available_vars": builtin.get("available_vars"),
            }

        raise ValueError(f"未找到场景 {scene_key} 的提示词配置")

    async def _has_global_override(self, scene_key: str) -> bool:
        """检查是否有全局自定义"""
        result = await self.db.execute(
            select(GlobalPrompt.id).where(GlobalPrompt.scene_key == scene_key)
        )
        return result.scalar_one_or_none() is not None

    async def list_all_prompts_for_admin(self) -> list[dict]:
        """
        获取所有提示词配置（管理员视图）

        合并内置定义和数据库中的全局配置
        """
        builtin_prompts = get_all_builtin_prompts()
        result = []

        for scene_key in get_builtin_scene_keys():
            builtin = builtin_prompts[scene_key]

            # 查询全局配置
            global_result = await self.db.execute(
                select(GlobalPrompt).where(GlobalPrompt.scene_key == scene_key)
            )
            global_prompt = global_result.scalar_one_or_none()

            if global_prompt:
                result.append({
                    "scene_key": scene_key,
                    "scene_name": builtin["scene_name"],
                    "category": builtin["category"],
                    "prompt": global_prompt.prompt,
                    "available_vars": builtin.get("available_vars"),
                    "version": global_prompt.version,
                    "is_customized": True,
                    "updated_at": global_prompt.updated_at,
                })
            else:
                result.append({
                    "scene_key": scene_key,
                    "scene_name": builtin["scene_name"],
                    "category": builtin["category"],
                    "prompt": builtin["prompt"],
                    "available_vars": builtin.get("available_vars"),
                    "version": 1,
                    "is_customized": False,
                    "updated_at": None,
                })

        return result

    async def list_project_prompts(self, project_id: uuid.UUID) -> list[dict]:
        """
        获取项目的所有提示词配置

        显示每个场景的最终配置及继承状态
        """
        builtin_prompts = get_all_builtin_prompts()
        result = []

        # 获取项目的自定义配置
        project_result = await self.db.execute(
            select(Project.custom_prompts).where(Project.id == project_id)
        )
        custom_prompts = project_result.scalar_one_or_none() or {}

        for scene_key in get_builtin_scene_keys():
            builtin = builtin_prompts[scene_key]
            config = await self.get_prompt_with_source_info(scene_key, project_id)

            result.append({
                "scene_key": scene_key,
                "scene_name": builtin["scene_name"],
                "category": builtin["category"],
                "prompt": config["prompt"],
                "available_vars": builtin.get("available_vars"),
                "source": config["source"],
                "has_project_override": config["has_project_override"],
                "has_global_override": config["has_global_override"],
            })

        return result

    async def update_global_prompt(
        self,
        scene_key: str,
        prompt: str,
        user_id: uuid.UUID,
    ) -> GlobalPrompt:
        """
        更新全局提示词配置（管理员）

        自动创建版本历史
        """
        # 查询现有配置
        result = await self.db.execute(
            select(GlobalPrompt).where(GlobalPrompt.scene_key == scene_key)
        )
        global_prompt = result.scalar_one_or_none()

        builtin = get_builtin_prompt(scene_key)
        if not builtin:
            raise ValueError(f"无效的场景标识: {scene_key}")

        if global_prompt:
            # 创建版本历史
            version = GlobalPromptVersion(
                global_prompt_id=global_prompt.id,
                version=global_prompt.version,
                prompt=global_prompt.prompt,
                created_by=user_id,
            )
            self.db.add(version)

            # 更新配置
            global_prompt.prompt = prompt
            global_prompt.version += 1
        else:
            # 创建新配置
            global_prompt = GlobalPrompt(
                scene_key=scene_key,
                scene_name=builtin["scene_name"],
                category=PromptCategory(builtin["category"]),
                prompt=prompt,
                available_vars=builtin.get("available_vars"),
                version=1,
            )
            self.db.add(global_prompt)

        await self.db.flush()
        await self.db.refresh(global_prompt)
        return global_prompt

    async def get_global_prompt_versions(
        self,
        scene_key: str,
        limit: int = 20,
    ) -> list[dict]:
        """获取全局提示词的版本历史（包含创建者名称）"""
        from ..models.user import User

        result = await self.db.execute(
            select(GlobalPrompt)
            .where(GlobalPrompt.scene_key == scene_key)
        )
        global_prompt = result.scalar_one_or_none()

        if not global_prompt:
            return []

        # 查询版本并关联用户
        versions_result = await self.db.execute(
            select(GlobalPromptVersion, User.username)
            .outerjoin(User, GlobalPromptVersion.created_by == User.id)
            .where(GlobalPromptVersion.global_prompt_id == global_prompt.id)
            .order_by(GlobalPromptVersion.version.desc())
            .limit(limit)
        )

        versions = []
        for version, username in versions_result.all():
            versions.append({
                "id": version.id,
                "version": version.version,
                "prompt": version.prompt,
                "created_by": version.created_by,
                "created_by_name": username,
                "created_at": version.created_at,
            })

        return versions

    async def rollback_global_prompt(
        self,
        scene_key: str,
        target_version: int,
        user_id: uuid.UUID,
    ) -> GlobalPrompt:
        """回滚全局提示词到指定版本"""
        result = await self.db.execute(
            select(GlobalPrompt).where(GlobalPrompt.scene_key == scene_key)
        )
        global_prompt = result.scalar_one_or_none()

        if not global_prompt:
            raise ValueError(f"场景 {scene_key} 没有全局配置")

        # 查找目标版本
        version_result = await self.db.execute(
            select(GlobalPromptVersion).where(
                GlobalPromptVersion.global_prompt_id == global_prompt.id,
                GlobalPromptVersion.version == target_version,
            )
        )
        target = version_result.scalar_one_or_none()

        if not target:
            raise ValueError(f"版本 {target_version} 不存在")

        # 创建当前版本的历史记录
        current_version = GlobalPromptVersion(
            global_prompt_id=global_prompt.id,
            version=global_prompt.version,
            prompt=global_prompt.prompt,
            created_by=user_id,
        )
        self.db.add(current_version)

        # 回滚到目标版本
        global_prompt.prompt = target.prompt
        global_prompt.version += 1

        await self.db.flush()
        await self.db.refresh(global_prompt)
        return global_prompt

    async def set_project_prompt(
        self,
        project_id: uuid.UUID,
        scene_key: str,
        prompt: str,
    ) -> None:
        """设置项目级提示词覆盖"""
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()

        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        if project.custom_prompts is None:
            project.custom_prompts = {}

        project.custom_prompts[scene_key] = {
            "prompt": prompt,
        }

        # 标记字段已修改（SQLAlchemy 可能不会自动检测 JSONB 变更）
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(project, "custom_prompts")

        await self.db.flush()

    async def delete_project_prompt(
        self,
        project_id: uuid.UUID,
        scene_key: str,
    ) -> bool:
        """删除项目级提示词覆盖"""
        result = await self.db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()

        if not project or not project.custom_prompts:
            return False

        if scene_key in project.custom_prompts:
            del project.custom_prompts[scene_key]
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(project, "custom_prompts")
            await self.db.flush()
            return True

        return False
