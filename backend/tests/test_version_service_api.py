"""版本服务和 API 单元测试"""
import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.version import ChangeType
from app.services.version_service import VersionService
from app.schemas.version import (
    VersionDiffInfo,
    ChapterChange,
    VersionDiffSummary,
    VersionDiffResponse,
    RestoredChapter,
    VersionRollbackResponse,
)


class TestVersionServiceHelpers:
    """版本服务辅助方法测试"""

    def test_compute_diff_no_changes(self):
        """测试无变化的快照对比"""
        # 由于 VersionService 需要 db session，我们只测试 _compute_diff 方法逻辑
        data = {
            "chapters": [
                {"id": "ch1", "chapter_number": "1", "title": "Chapter 1", "content": "Content 1"},
            ]
        }

        # 直接使用静态方法风格的逻辑测试
        # 实际测试中会通过服务实例调用
        from app.services.version_service import VersionService

        # 创建一个模拟的 db session
        class MockDB:
            pass

        service = VersionService(MockDB())  # type: ignore
        result = service._compute_diff(data, data, 1, 1)

        assert result["total_changes"] == 0
        assert result["added"] == 0
        assert result["deleted"] == 0
        assert result["modified"] == 0

    def test_compute_diff_added_chapter(self):
        """测试新增章节的差异检测"""
        data1 = {"chapters": []}
        data2 = {
            "chapters": [
                {"id": "ch1", "chapter_number": "1", "title": "New Chapter", "content": "New Content"},
            ]
        }

        class MockDB:
            pass

        service = VersionService(MockDB())  # type: ignore
        result = service._compute_diff(data1, data2, 1, 2)

        assert result["total_changes"] == 1
        assert result["added"] == 1
        assert result["deleted"] == 0
        assert result["modified"] == 0
        assert len(result["changes"]) == 1
        assert result["changes"][0]["type"] == "added"

    def test_compute_diff_deleted_chapter(self):
        """测试删除章节的差异检测"""
        data1 = {
            "chapters": [
                {"id": "ch1", "chapter_number": "1", "title": "Old Chapter", "content": "Old Content"},
            ]
        }
        data2 = {"chapters": []}

        class MockDB:
            pass

        service = VersionService(MockDB())  # type: ignore
        result = service._compute_diff(data1, data2, 1, 2)

        assert result["total_changes"] == 1
        assert result["added"] == 0
        assert result["deleted"] == 1
        assert result["modified"] == 0
        assert result["changes"][0]["type"] == "deleted"

    def test_compute_diff_modified_chapter(self):
        """测试修改章节的差异检测"""
        data1 = {
            "chapters": [
                {"id": "ch1", "chapter_number": "1", "title": "Old Title", "content": "Old Content"},
            ]
        }
        data2 = {
            "chapters": [
                {"id": "ch1", "chapter_number": "1", "title": "New Title", "content": "New Content"},
            ]
        }

        class MockDB:
            pass

        service = VersionService(MockDB())  # type: ignore
        result = service._compute_diff(data1, data2, 1, 2)

        assert result["total_changes"] == 1
        assert result["added"] == 0
        assert result["deleted"] == 0
        assert result["modified"] == 1
        assert result["changes"][0]["type"] == "modified"
        assert result["changes"][0]["content_changed"] is True
        assert result["changes"][0]["title_changed"] is True

    def test_compute_diff_multiple_changes(self):
        """测试多个变更的差异检测"""
        data1 = {
            "chapters": [
                {"id": "ch1", "chapter_number": "1", "title": "Chapter 1", "content": "Content 1"},
                {"id": "ch2", "chapter_number": "2", "title": "Chapter 2", "content": "Content 2"},
            ]
        }
        data2 = {
            "chapters": [
                {"id": "ch1", "chapter_number": "1", "title": "Chapter 1 Modified", "content": "Content 1"},
                {"id": "ch3", "chapter_number": "3", "title": "New Chapter 3", "content": "Content 3"},
            ]
        }

        class MockDB:
            pass

        service = VersionService(MockDB())  # type: ignore
        result = service._compute_diff(data1, data2, 1, 2)

        assert result["total_changes"] == 3  # 1 modified, 1 deleted, 1 added
        assert result["added"] == 1
        assert result["deleted"] == 1
        assert result["modified"] == 1


class TestNewVersionSchemas:
    """新增版本 Schema 测试"""

    def test_version_diff_info(self):
        """测试版本差异信息 schema"""
        data = {
            "id": str(uuid.uuid4()),
            "version_number": 5,
            "created_at": "2026-02-12T10:00:00",
            "change_type": "manual_edit",
        }
        diff_info = VersionDiffInfo(**data)
        assert diff_info.version_number == 5
        assert diff_info.change_type == "manual_edit"

    def test_chapter_change_added(self):
        """测试章节变更（新增）schema"""
        data = {
            "type": "added",
            "chapter_id": str(uuid.uuid4()),
            "chapter_number": "1.1",
            "title": "New Chapter",
            "old_content": None,
            "new_content": "New content here",
        }
        change = ChapterChange(**data)
        assert change.type == "added"
        assert change.old_content is None
        assert change.new_content == "New content here"

    def test_chapter_change_modified(self):
        """测试章节变更（修改）schema"""
        data = {
            "type": "modified",
            "chapter_id": str(uuid.uuid4()),
            "chapter_number": "2.1",
            "title": "Updated Title",
            "old_content": "Old content",
            "new_content": "New content",
            "content_changed": True,
            "title_changed": False,
        }
        change = ChapterChange(**data)
        assert change.type == "modified"
        assert change.content_changed is True
        assert change.title_changed is False

    def test_version_diff_summary(self):
        """测试版本差异摘要 schema"""
        data = {
            "total_changes": 5,
            "added": 2,
            "deleted": 1,
            "modified": 2,
            "changes": [
                {"type": "added", "chapter_id": "ch1", "chapter_number": "1", "title": "A"},
                {"type": "modified", "chapter_id": "ch2", "chapter_number": "2", "title": "B"},
            ],
        }
        summary = VersionDiffSummary(**data)
        assert summary.total_changes == 5
        assert len(summary.changes) == 2

    def test_version_diff_response(self):
        """测试版本差异响应 schema"""
        v1_id = str(uuid.uuid4())
        v2_id = str(uuid.uuid4())

        data = {
            "v1": {
                "id": v1_id,
                "version_number": 1,
                "created_at": "2026-02-12T10:00:00",
                "change_type": "manual_edit",
            },
            "v2": {
                "id": v2_id,
                "version_number": 2,
                "created_at": "2026-02-12T11:00:00",
                "change_type": "ai_generate",
            },
            "diff": {
                "total_changes": 1,
                "added": 0,
                "deleted": 0,
                "modified": 1,
                "changes": [],
            },
        }
        response = VersionDiffResponse(**data)
        assert response.v1.version_number == 1
        assert response.v2.version_number == 2

    def test_restored_chapter(self):
        """测试恢复章节信息 schema"""
        data = {
            "id": str(uuid.uuid4()),
            "chapter_number": "1.2.3",
            "action": "updated",
        }
        restored = RestoredChapter(**data)
        assert restored.action == "updated"
        assert restored.chapter_number == "1.2.3"

    def test_version_rollback_response_success(self):
        """测试版本回滚响应（成功）schema"""
        data = {
            "success": True,
            "target_version_number": 5,
            "new_version_id": str(uuid.uuid4()),
            "new_version_number": 10,
            "pre_snapshot_id": str(uuid.uuid4()),
            "restored_chapters": [
                {"id": str(uuid.uuid4()), "chapter_number": "1", "action": "updated"},
            ],
        }
        response = VersionRollbackResponse(**data)
        assert response.success is True
        assert response.target_version_number == 5
        assert response.new_version_number == 10
        assert len(response.restored_chapters) == 1

    def test_version_rollback_response_failure(self):
        """测试版本回滚响应（失败）schema"""
        data = {
            "success": False,
            "error": "目标版本不存在",
        }
        response = VersionRollbackResponse(**data)
        assert response.success is False
        assert response.error == "目标版本不存在"

    def test_version_diff_response_with_dict_diff(self):
        """测试版本差异响应（diff 为字典，如错误情况）"""
        v1_id = str(uuid.uuid4())
        v2_id = str(uuid.uuid4())

        data = {
            "v1": {
                "id": v1_id,
                "version_number": 1,
                "created_at": "2026-02-12T10:00:00",
                "change_type": "manual_edit",
            },
            "v2": {
                "id": v2_id,
                "version_number": 2,
                "created_at": "2026-02-12T11:00:00",
                "change_type": "ai_generate",
            },
            "diff": {
                "error": "版本不存在",
                "v1_found": True,
                "v2_found": False,
            },
        }
        response = VersionDiffResponse(**data)
        assert response.v1.version_number == 1
        # diff 可以是 VersionDiffSummary 或 dict
        assert isinstance(response.diff, dict)


class TestChangeTypeUsage:
    """变更类型使用场景测试"""

    def test_ai_generate_type(self):
        """测试 AI 生成变更类型"""
        assert ChangeType.AI_GENERATE.value == "ai_generate"
        assert ChangeType.AI_GENERATE == "ai_generate"

    def test_manual_edit_type(self):
        """测试手动编辑变更类型"""
        assert ChangeType.MANUAL_EDIT.value == "manual_edit"

    def test_proofread_type(self):
        """测试校对变更类型"""
        assert ChangeType.PROOFREAD.value == "proofread"

    def test_rollback_type(self):
        """测试回滚变更类型"""
        assert ChangeType.ROLLBACK.value == "rollback"

    def test_all_change_types_defined(self):
        """测试所有变更类型都已定义"""
        expected_types = {"ai_generate", "manual_edit", "proofread", "rollback"}
        actual_types = {ct.value for ct in ChangeType}
        assert expected_types == actual_types
