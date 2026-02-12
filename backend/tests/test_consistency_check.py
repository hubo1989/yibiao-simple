"""跨章节一致性检查单元测试"""
import uuid

import pytest

from app.schemas.project import (
    ChapterSummaryForConsistency,
    ContradictionItem,
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
)
from app.models.consistency_result import ConsistencySeverity, ConsistencyCategory


class TestChapterSummaryForConsistency:
    """章节摘要 Schema 测试"""

    def test_valid_chapter_summary(self):
        """有效的章节摘要"""
        summary = ChapterSummaryForConsistency(
            chapter_number="1.2.3",
            title="技术方案",
            summary="本项目采用微服务架构，预计投入15名工程师...",
        )
        assert summary.chapter_number == "1.2.3"
        assert summary.title == "技术方案"
        assert "15名工程师" in summary.summary

    def test_all_fields_required(self):
        """所有字段都是必填"""
        with pytest.raises(Exception):
            ChapterSummaryForConsistency(chapter_number="1", title="测试")
        with pytest.raises(Exception):
            ChapterSummaryForConsistency(chapter_number="1", summary="内容")


class TestContradictionItem:
    """矛盾项 Schema 测试"""

    def test_valid_contradiction_item(self):
        """有效的矛盾项"""
        item = ContradictionItem(
            severity=ConsistencySeverity.CRITICAL,
            category=ConsistencyCategory.DATA,
            description="工程师数量不一致",
            chapter_a="1.2 技术方案",
            chapter_b="3.1 项目团队",
            detail_a="15名工程师",
            detail_b="20名工程师",
            suggestion="统一为15名工程师",
        )
        assert item.severity == ConsistencySeverity.CRITICAL
        assert item.category == ConsistencyCategory.DATA
        assert "不一致" in item.description

    def test_all_severity_levels(self):
        """所有严重程度"""
        for severity in ConsistencySeverity:
            item = ContradictionItem(
                severity=severity,
                category=ConsistencyCategory.TERMINOLOGY,
                description="测试",
                chapter_a="A",
                chapter_b="B",
                detail_a="A内容",
                detail_b="B内容",
                suggestion="建议",
            )
            assert item.severity == severity

    def test_all_categories(self):
        """所有矛盾类别"""
        for category in ConsistencyCategory:
            item = ContradictionItem(
                severity=ConsistencySeverity.WARNING,
                category=category,
                description="测试",
                chapter_a="A",
                chapter_b="B",
                detail_a="A内容",
                detail_b="B内容",
                suggestion="建议",
            )
            assert item.category == category


class TestConsistencyCheckRequest:
    """一致性检查请求 Schema 测试"""

    def test_valid_request_with_minimum_chapters(self):
        """最少2个章节的请求"""
        request = ConsistencyCheckRequest(
            chapter_summaries=[
                ChapterSummaryForConsistency(
                    chapter_number="1",
                    title="第一章",
                    summary="内容摘要1",
                ),
                ChapterSummaryForConsistency(
                    chapter_number="2",
                    title="第二章",
                    summary="内容摘要2",
                ),
            ]
        )
        assert len(request.chapter_summaries) == 2

    def test_request_with_many_chapters(self):
        """多个章节的请求"""
        summaries = [
            ChapterSummaryForConsistency(
                chapter_number=str(i),
                title=f"第{i}章",
                summary=f"内容摘要{i}",
            )
            for i in range(1, 11)
        ]
        request = ConsistencyCheckRequest(chapter_summaries=summaries)
        assert len(request.chapter_summaries) == 10

    def test_request_requires_at_least_two_chapters(self):
        """至少需要2个章节"""
        with pytest.raises(Exception):
            ConsistencyCheckRequest(
                chapter_summaries=[
                    ChapterSummaryForConsistency(
                        chapter_number="1",
                        title="第一章",
                        summary="内容摘要",
                    ),
                ]
            )


class TestConsistencyCheckResponse:
    """一致性检查响应 Schema 测试"""

    def test_response_with_no_contradictions(self):
        """无矛盾的响应"""
        from datetime import datetime

        response = ConsistencyCheckResponse(
            contradictions=[],
            summary="所有章节内容一致，未发现矛盾",
            overall_consistency="consistent",
            contradiction_count=0,
            critical_count=0,
            created_at=datetime.now(),
        )
        assert response.overall_consistency == "consistent"
        assert response.contradiction_count == 0
        assert len(response.contradictions) == 0

    def test_response_with_minor_issues(self):
        """有轻微问题的响应"""
        from datetime import datetime

        response = ConsistencyCheckResponse(
            contradictions=[
                ContradictionItem(
                    severity=ConsistencySeverity.INFO,
                    category=ConsistencyCategory.TERMINOLOGY,
                    description="术语略有不同",
                    chapter_a="1.1",
                    chapter_b="2.3",
                    detail_a="项目经理",
                    detail_b="项目负责人",
                    suggestion="统一使用项目经理",
                )
            ],
            summary="发现轻微的术语不一致问题",
            overall_consistency="minor_issues",
            contradiction_count=1,
            critical_count=0,
            created_at=datetime.now(),
        )
        assert response.overall_consistency == "minor_issues"
        assert response.contradiction_count == 1
        assert response.critical_count == 0

    def test_response_with_major_issues(self):
        """有严重问题的响应"""
        from datetime import datetime

        response = ConsistencyCheckResponse(
            contradictions=[
                ContradictionItem(
                    severity=ConsistencySeverity.CRITICAL,
                    category=ConsistencyCategory.DATA,
                    description="数据矛盾",
                    chapter_a="1.2",
                    chapter_b="3.1",
                    detail_a="预算500万",
                    detail_b="预算600万",
                    suggestion="核实并统一预算数据",
                ),
                ContradictionItem(
                    severity=ConsistencySeverity.WARNING,
                    category=ConsistencyCategory.TIMELINE,
                    description="时间线不一致",
                    chapter_a="2.1",
                    chapter_b="4.2",
                    detail_a="第一阶段1个月",
                    detail_b="第一阶段2周",
                    suggestion="统一项目时间线",
                ),
            ],
            summary="发现严重的数据矛盾和时间线不一致问题",
            overall_consistency="major_issues",
            contradiction_count=2,
            critical_count=1,
            created_at=datetime.now(),
        )
        assert response.overall_consistency == "major_issues"
        assert response.contradiction_count == 2
        assert response.critical_count == 1

    def test_response_from_attributes(self):
        """验证 from_attributes 配置"""
        config = ConsistencyCheckResponse.model_config
        assert config.get("from_attributes") is True


class TestConsistencySeverityEnum:
    """一致性严重程度枚举测试"""

    def test_severity_values(self):
        """严重程度值"""
        assert ConsistencySeverity.CRITICAL.value == "critical"
        assert ConsistencySeverity.WARNING.value == "warning"
        assert ConsistencySeverity.INFO.value == "info"

    def test_severity_count(self):
        """严重程度数量"""
        assert len(ConsistencySeverity) == 3


class TestConsistencyCategoryEnum:
    """一致性类别枚举测试"""

    def test_category_values(self):
        """类别值"""
        assert ConsistencyCategory.DATA.value == "data"
        assert ConsistencyCategory.TERMINOLOGY.value == "terminology"
        assert ConsistencyCategory.TIMELINE.value == "timeline"
        assert ConsistencyCategory.COMMITMENT.value == "commitment"
        assert ConsistencyCategory.SCOPE.value == "scope"

    def test_category_count(self):
        """类别数量"""
        assert len(ConsistencyCategory) == 5


class TestConsistencyResultModel:
    """一致性检查结果 ORM 模型测试"""

    def test_model_tablename(self):
        """表名验证"""
        from app.models.consistency_result import ConsistencyResult

        assert ConsistencyResult.__tablename__ == "consistency_results"

    def test_model_has_required_fields(self):
        """模型包含必要字段"""
        from app.models.consistency_result import ConsistencyResult

        # 验证字段存在
        assert hasattr(ConsistencyResult, "id")
        assert hasattr(ConsistencyResult, "project_id")
        assert hasattr(ConsistencyResult, "contradictions")
        assert hasattr(ConsistencyResult, "summary")
        assert hasattr(ConsistencyResult, "overall_consistency")
        assert hasattr(ConsistencyResult, "contradiction_count")
        assert hasattr(ConsistencyResult, "critical_count")
        assert hasattr(ConsistencyResult, "created_at")
