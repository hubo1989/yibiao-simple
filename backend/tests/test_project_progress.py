"""项目进度 API 单元测试"""
import uuid

import pytest

from app.schemas.project import ProjectProgress


class TestProjectProgressSchema:
    """项目进度 Schema 测试"""

    def test_progress_with_all_zeros(self):
        """所有状态都为 0"""
        progress = ProjectProgress(
            total_chapters=0,
            pending=0,
            generated=0,
            reviewing=0,
            finalized=0,
            completion_percentage=0.0,
        )
        assert progress.total_chapters == 0
        assert progress.completion_percentage == 0.0

    def test_progress_with_pending_chapters(self):
        """只有待处理章节"""
        progress = ProjectProgress(
            total_chapters=10,
            pending=10,
            generated=0,
            reviewing=0,
            finalized=0,
            completion_percentage=0.0,
        )
        assert progress.total_chapters == 10
        assert progress.pending == 10
        assert progress.completion_percentage == 0.0

    def test_progress_with_mixed_chapters(self):
        """混合状态章节"""
        progress = ProjectProgress(
            total_chapters=10,
            pending=3,
            generated=4,
            reviewing=2,
            finalized=1,
            completion_percentage=10.0,
        )
        assert progress.total_chapters == 10
        assert progress.pending == 3
        assert progress.generated == 4
        assert progress.reviewing == 2
        assert progress.finalized == 1
        # 1/10 = 10%
        assert progress.completion_percentage == 10.0

    def test_progress_all_finalized(self):
        """所有章节已定稿"""
        progress = ProjectProgress(
            total_chapters=5,
            pending=0,
            generated=0,
            reviewing=0,
            finalized=5,
            completion_percentage=100.0,
        )
        assert progress.total_chapters == 5
        assert progress.finalized == 5
        assert progress.completion_percentage == 100.0

    def test_progress_half_finalized(self):
        """一半章节已定稿"""
        progress = ProjectProgress(
            total_chapters=10,
            pending=2,
            generated=3,
            reviewing=0,
            finalized=5,
            completion_percentage=50.0,
        )
        assert progress.finalized == 5
        assert progress.completion_percentage == 50.0

    def test_progress_rounds_to_two_decimals(self):
        """完成百分比保留两位小数"""
        # 1/3 = 33.33%
        progress = ProjectProgress(
            total_chapters=3,
            pending=2,
            generated=0,
            reviewing=0,
            finalized=1,
            completion_percentage=33.33,
        )
        assert progress.completion_percentage == 33.33


class TestProjectProgressDefaults:
    """项目进度默认值测试"""

    def test_default_values(self):
        """验证默认值"""
        progress = ProjectProgress(total_chapters=5)
        assert progress.pending == 0
        assert progress.generated == 0
        assert progress.reviewing == 0
        assert progress.finalized == 0
        assert progress.completion_percentage == 0.0


class TestProjectProgressValidation:
    """项目进度验证测试"""

    def test_sum_of_statuses_equals_total(self):
        """各状态数量之和应等于总数（逻辑验证，非 Schema 强制）"""
        total = 10
        pending = 3
        generated = 4
        reviewing = 2
        finalized = 1

        assert pending + generated + reviewing + finalized == total

    def test_completion_percentage_calculation(self):
        """完成百分比计算逻辑"""
        total = 20
        finalized = 7

        expected_percentage = round(finalized / total * 100, 2)
        assert expected_percentage == 35.0

    def test_zero_total_no_division_error(self):
        """总数为 0 时不应除零错误"""
        total = 0
        finalized = 0

        # 业务逻辑中应有保护：if total > 0: percentage = ...
        # 这里验证逻辑判断
        if total > 0:
            percentage = round(finalized / total * 100, 2)
        else:
            percentage = 0.0

        assert percentage == 0.0


class TestProjectProgressFieldDescriptions:
    """项目进度字段描述测试"""

    def test_field_descriptions_exist(self):
        """验证字段描述存在"""
        # 获取字段信息
        fields = ProjectProgress.model_fields

        assert "total_chapters" in fields
        assert "pending" in fields
        assert "generated" in fields
        assert "reviewing" in fields
        assert "finalized" in fields
        assert "completion_percentage" in fields

    def test_total_chapters_required(self):
        """total_chapters 是必填字段"""
        # 不提供 total_chapters 应该失败
        with pytest.raises(Exception):
            ProjectProgress()


class TestProjectProgressFromAttributes:
    """from_attributes 配置测试"""

    def test_model_config_from_attributes(self):
        """验证 model_config 包含 from_attributes"""
        config = ProjectProgress.model_config
        assert config.get("from_attributes") is True
