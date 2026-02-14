"""版本快照服务"""

import uuid
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.version import ProjectVersion, ChangeType
from ..models.chapter import Chapter
from ..models.project import Project


class VersionService:
    """版本快照管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_version(
        self,
        project_id: uuid.UUID,
        chapter_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        change_type: ChangeType,
        snapshot_data: dict[str, Any],
        change_summary: str | None = None,
    ) -> ProjectVersion:
        """
        创建版本快照，自动递增版本号

        Args:
            project_id: 所属项目 ID
            chapter_id: 关联章节 ID（全量快照时为 None）
            user_id: 创建此版本的用户 ID
            change_type: 变更类型
            snapshot_data: 章节内容快照
            change_summary: 变更摘要说明

        Returns:
            新创建的版本快照对象
        """
        # 使用 SELECT FOR UPDATE 锁定项目行，防止并发创建重复版本号
        project_result = await self.db.execute(
            select(Project).where(Project.id == project_id).with_for_update()
        )
        project_result.scalar_one_or_none()

        # 获取当前项目的最大版本号
        max_version_result = await self.db.execute(
            select(func.max(ProjectVersion.version_number)).where(
                ProjectVersion.project_id == project_id
            )
        )
        max_version = max_version_result.scalar() or 0
        new_version_number = max_version + 1

        # 创建版本快照
        version = ProjectVersion(
            project_id=project_id,
            chapter_id=chapter_id,
            version_number=new_version_number,
            snapshot_data=snapshot_data,
            change_type=change_type,
            change_summary=change_summary,
            created_by=user_id,
        )
        self.db.add(version)
        await self.db.flush()
        await self.db.refresh(version)

        return version

    async def get_version(
        self,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> ProjectVersion | None:
        """
        获取版本详情

        Args:
            project_id: 项目 ID
            version_id: 版本 ID

        Returns:
            版本快照对象，不存在则返回 None
        """
        result = await self.db.execute(
            select(ProjectVersion).where(
                and_(
                    ProjectVersion.id == version_id,
                    ProjectVersion.project_id == project_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(
        self,
        project_id: uuid.UUID,
        chapter_id: uuid.UUID | None = None,
        change_type: ChangeType | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ProjectVersion], int]:
        """
        获取项目版本列表（分页）

        Args:
            project_id: 项目 ID
            chapter_id: 可选的章节 ID 过滤
            change_type: 可选的变更类型过滤
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            (版本列表, 总数) 元组
        """
        # 基础查询条件
        base_condition = ProjectVersion.project_id == project_id
        if chapter_id is not None:
            base_condition = and_(
                base_condition, ProjectVersion.chapter_id == chapter_id
            )
        if change_type is not None:
            base_condition = and_(
                base_condition, ProjectVersion.change_type == change_type
            )

        # 查询总数
        count_result = await self.db.execute(
            select(func.count()).select_from(ProjectVersion).where(base_condition)
        )
        total = count_result.scalar() or 0

        # 查询列表
        result = await self.db.execute(
            select(ProjectVersion)
            .where(base_condition)
            .order_by(ProjectVersion.version_number.desc())
            .offset(skip)
            .limit(limit)
        )
        versions = list(result.scalars().all())

        return versions, total

    async def diff_versions(
        self,
        project_id: uuid.UUID,
        version_id_1: uuid.UUID,
        version_id_2: uuid.UUID,
    ) -> dict[str, Any]:
        """
        对比两个版本间的差异（章节级别）

        Args:
            project_id: 项目 ID
            version_id_1: 第一个版本 ID
            version_id_2: 第二个版本 ID

        Returns:
            包含差异信息的字典
        """
        # 获取两个版本
        v1 = await self.get_version(project_id, version_id_1)
        v2 = await self.get_version(project_id, version_id_2)

        if not v1 or not v2:
            return {
                "error": "版本不存在",
                "v1_found": v1 is not None,
                "v2_found": v2 is not None,
            }

        # 提取快照数据
        data1 = v1.snapshot_data
        data2 = v2.snapshot_data

        # 计算差异
        diff_result = self._compute_diff(
            data1, data2, v1.version_number, v2.version_number
        )

        return {
            "v1": {
                "id": str(v1.id),
                "version_number": v1.version_number,
                "created_at": v1.created_at.isoformat(),
                "change_type": v1.change_type.value,
            },
            "v2": {
                "id": str(v2.id),
                "version_number": v2.version_number,
                "created_at": v2.created_at.isoformat(),
                "change_type": v2.change_type.value,
            },
            "diff": diff_result,
        }

    def _compute_diff(
        self,
        data1: dict[str, Any],
        data2: dict[str, Any],
        v1_number: int,
        v2_number: int,
    ) -> dict[str, Any]:
        """
        计算两个快照数据之间的差异

        Args:
            data1: 第一个版本的快照数据
            data2: 第二个版本的快照数据
            v1_number: 第一个版本号
            v2_number: 第二个版本号

        Returns:
            差异结果字典
        """
        changes: list[dict[str, Any]] = []

        # 处理章节级别的差异
        chapters1 = data1.get("chapters", [])
        chapters2 = data2.get("chapters", [])

        # 转换为以 ID 或 chapter_number 为 key 的字典
        def chapters_by_key(chapters: list) -> dict[str, dict]:
            result = {}
            for ch in chapters:
                key = ch.get("id") or ch.get("chapter_number", str(id(ch)))
                result[str(key)] = ch
            return result

        ch_dict1 = chapters_by_key(chapters1)
        ch_dict2 = chapters_by_key(chapters2)

        all_keys = set(ch_dict1.keys()) | set(ch_dict2.keys())

        for key in all_keys:
            ch1 = ch_dict1.get(key)
            ch2 = ch_dict2.get(key)

            if ch1 and not ch2:
                changes.append(
                    {
                        "type": "deleted",
                        "chapter_id": key,
                        "chapter_number": ch1.get("chapter_number"),
                        "title": ch1.get("title"),
                        "old_content": ch1.get("content"),
                        "new_content": None,
                    }
                )
            elif not ch1 and ch2:
                changes.append(
                    {
                        "type": "added",
                        "chapter_id": key,
                        "chapter_number": ch2.get("chapter_number"),
                        "title": ch2.get("title"),
                        "old_content": None,
                        "new_content": ch2.get("content"),
                    }
                )
            elif ch1 and ch2:
                # 检查内容变化
                content1 = ch1.get("content")
                content2 = ch2.get("content")
                title1 = ch1.get("title")
                title2 = ch2.get("title")

                if content1 != content2 or title1 != title2:
                    changes.append(
                        {
                            "type": "modified",
                            "chapter_id": key,
                            "chapter_number": ch2.get("chapter_number"),
                            "title": title2,
                            "old_title": title1 if title1 != title2 else None,
                            "new_title": title2 if title1 != title2 else None,
                            "old_content": content1,
                            "new_content": content2,
                            "content_changed": content1 != content2,
                            "title_changed": title1 != title2,
                        }
                    )

        return {
            "total_changes": len(changes),
            "added": len([c for c in changes if c["type"] == "added"]),
            "deleted": len([c for c in changes if c["type"] == "deleted"]),
            "modified": len([c for c in changes if c["type"] == "modified"]),
            "changes": changes,
        }

    async def rollback_to_version(
        self,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
        user_id: uuid.UUID,
        create_pre_snapshot: bool = True,
    ) -> dict[str, Any]:
        """
        回滚到指定版本，自动创建新版本记录

        Args:
            project_id: 项目 ID
            version_id: 目标版本 ID
            user_id: 执行回滚的用户 ID
            create_pre_snapshot: 是否在回滚前创建当前状态快照

        Returns:
            包含回滚结果的字典
        """
        # 获取目标版本
        target_version = await self.get_version(project_id, version_id)
        if not target_version:
            return {
                "success": False,
                "error": "目标版本不存在",
            }

        # 可选：创建当前状态的快照
        pre_snapshot_id = None
        if create_pre_snapshot:
            # 获取当前所有章节状态
            chapters_result = await self.db.execute(
                select(Chapter).where(Chapter.project_id == project_id)
            )
            current_chapters = list(chapters_result.scalars().all())

            # 构建当前快照数据
            current_snapshot = {
                "chapters": [
                    {
                        "id": str(ch.id),
                        "chapter_number": ch.chapter_number,
                        "title": ch.title,
                        "content": ch.content,
                        "status": ch.status.value if ch.status else None,
                        "parent_id": str(ch.parent_id) if ch.parent_id else None,
                    }
                    for ch in current_chapters
                ]
            }

            pre_snapshot = await self.create_version(
                project_id=project_id,
                chapter_id=None,
                user_id=user_id,
                change_type=ChangeType.ROLLBACK,
                snapshot_data=current_snapshot,
                change_summary=f"回滚到版本 {target_version.version_number} 前的自动快照",
            )
            pre_snapshot_id = str(pre_snapshot.id)

        # 从目标版本恢复章节内容
        snapshot_data = target_version.snapshot_data
        restored_chapters: list[dict[str, Any]] = []

        for ch_data in snapshot_data.get("chapters", []):
            ch_id_str = ch_data.get("id")
            if not ch_id_str:
                continue

            try:
                ch_id = uuid.UUID(ch_id_str)
            except ValueError:
                continue

            # 查找现有章节
            result = await self.db.execute(select(Chapter).where(Chapter.id == ch_id))
            chapter = result.scalar_one_or_none()

            if chapter:
                # 更新现有章节
                chapter.title = ch_data.get("title", chapter.title)
                chapter.content = ch_data.get("content")
                restored_chapters.append(
                    {
                        "id": str(chapter.id),
                        "chapter_number": chapter.chapter_number,
                        "action": "updated",
                    }
                )

        # 创建回滚后的新版本记录
        rollback_version = await self.create_version(
            project_id=project_id,
            chapter_id=None,
            user_id=user_id,
            change_type=ChangeType.ROLLBACK,
            snapshot_data=snapshot_data,
            change_summary=f"回滚到版本 {target_version.version_number}",
        )

        return {
            "success": True,
            "target_version_number": target_version.version_number,
            "new_version_id": str(rollback_version.id),
            "new_version_number": rollback_version.version_number,
            "pre_snapshot_id": pre_snapshot_id,
            "restored_chapters": restored_chapters,
        }

    async def create_project_snapshot(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID | None,
        change_type: ChangeType = ChangeType.MANUAL_EDIT,
        change_summary: str | None = None,
    ) -> ProjectVersion:
        """
        创建项目的完整快照（包含所有章节）

        Args:
            project_id: 项目 ID
            user_id: 创建快照的用户 ID
            change_type: 变更类型
            change_summary: 变更摘要

        Returns:
            新创建的版本快照
        """
        # 获取项目所有章节
        chapters_result = await self.db.execute(
            select(Chapter)
            .where(Chapter.project_id == project_id)
            .order_by(Chapter.order_index)
        )
        chapters = list(chapters_result.scalars().all())

        # 构建快照数据
        snapshot_data = {
            "chapters": [
                {
                    "id": str(ch.id),
                    "chapter_number": ch.chapter_number,
                    "title": ch.title,
                    "content": ch.content,
                    "status": ch.status.value if ch.status else None,
                    "parent_id": str(ch.parent_id) if ch.parent_id else None,
                    "order_index": ch.order_index,
                }
                for ch in chapters
            ]
        }

        return await self.create_version(
            project_id=project_id,
            chapter_id=None,
            user_id=user_id,
            change_type=change_type,
            snapshot_data=snapshot_data,
            change_summary=change_summary,
        )
