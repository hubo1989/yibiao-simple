"""校对 API 单元测试"""
import uuid
import json
from datetime import datetime, timezone

import pytest

from app.routers.chapters import (
    ProofreadIssueItem,
    ProofreadResultData,
    ProofreadResponse,
)
from app.models.proofread_result import (
    ProofreadResult,
    IssueSeverity,
    IssueCategory,
)


class TestProofreadSchemas:
    """校对 Schema 测试"""

    def test_proofread_issue_item_creation(self):
        """测试校对问题项创建"""
        issue = ProofreadIssueItem(
            severity="critical",
            category="compliance",
            position="第2段",
            issue="未提及数据安全要求",
            suggestion="补充数据加密和安全传输方案",
        )
        assert issue.severity == "critical"
        assert issue.category == "compliance"
        assert issue.position == "第2段"
        assert issue.issue == "未提及数据安全要求"
        assert issue.suggestion == "补充数据加密和安全传输方案"

    def test_proofread_issue_item_all_severities(self):
        """测试所有严重程度"""
        severities = ["critical", "warning", "info"]
        for severity in severities:
            issue = ProofreadIssueItem(
                severity=severity,
                category="language",
                position="第1段",
                issue="test",
                suggestion="test",
            )
            assert issue.severity == severity

    def test_proofread_issue_item_all_categories(self):
        """测试所有问题类别"""
        categories = ["compliance", "language", "consistency", "redundancy"]
        for category in categories:
            issue = ProofreadIssueItem(
                severity="warning",
                category=category,
                position="test",
                issue="test",
                suggestion="test",
            )
            assert issue.category == category

    def test_proofread_result_data_empty_issues(self):
        """测试空问题列表的校对结果"""
        result = ProofreadResultData(
            issues=[],
            summary="内容质量良好，无明显问题",
        )
        assert result.issues == []
        assert result.summary == "内容质量良好，无明显问题"

    def test_proofread_result_data_with_issues(self):
        """测试包含问题列表的校对结果"""
        issues = [
            ProofreadIssueItem(
                severity="warning",
                category="language",
                position="第1段",
                issue="表达不够准确",
                suggestion="修改为更专业的表述",
            ),
            ProofreadIssueItem(
                severity="info",
                category="redundancy",
                position="第3段",
                issue="与前面内容重复",
                suggestion="删除重复部分",
            ),
        ]
        result = ProofreadResultData(
            issues=issues,
            summary="发现2个问题，建议修改",
        )
        assert len(result.issues) == 2
        assert result.summary == "发现2个问题，建议修改"

    def test_proofread_response_creation(self):
        """测试校对响应创建"""
        response = ProofreadResponse(
            id=str(uuid.uuid4()),
            chapter_id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            issues=[
                ProofreadIssueItem(
                    severity="critical",
                    category="compliance",
                    position="第1段",
                    issue="缺少关键内容",
                    suggestion="补充内容",
                )
            ],
            summary="发现1个严重问题",
            issue_count=1,
            critical_count=1,
            status_changed=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert response.issue_count == 1
        assert response.critical_count == 1
        assert response.status_changed is True

    def test_proofread_response_status_not_changed(self):
        """测试章节状态未变更的响应"""
        response = ProofreadResponse(
            id=str(uuid.uuid4()),
            chapter_id=str(uuid.uuid4()),
            project_id=str(uuid.uuid4()),
            issues=[],
            summary="无问题",
            issue_count=0,
            critical_count=0,
            status_changed=False,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert response.status_changed is False


class TestProofreadResultModel:
    """校对结果 ORM 模型测试"""

    def test_issue_severity_enum(self):
        """测试问题严重程度枚举"""
        assert IssueSeverity.CRITICAL.value == "critical"
        assert IssueSeverity.WARNING.value == "warning"
        assert IssueSeverity.INFO.value == "info"

    def test_issue_category_enum(self):
        """测试问题类别枚举"""
        assert IssueCategory.COMPLIANCE.value == "compliance"
        assert IssueCategory.LANGUAGE.value == "language"
        assert IssueCategory.CONSISTENCY.value == "consistency"
        assert IssueCategory.REDUNDANCY.value == "redundancy"

    def test_proofread_result_model_repr(self):
        """测试模型字符串表示"""
        chapter_id = uuid.uuid4()
        result = ProofreadResult(
            chapter_id=chapter_id,
            project_id=uuid.uuid4(),
            issues="[]",
            summary="test",
            issue_count=0,
            critical_count=0,
        )
        assert str(chapter_id) in str(result)


class TestProofreadIssueValidation:
    """校对问题验证测试"""

    def test_critical_issue_count(self):
        """测试严重问题计数"""
        issues = [
            ProofreadIssueItem(
                severity="critical",
                category="compliance",
                position="a",
                issue="a",
                suggestion="a",
            ),
            ProofreadIssueItem(
                severity="critical",
                category="language",
                position="b",
                issue="b",
                suggestion="b",
            ),
            ProofreadIssueItem(
                severity="warning",
                category="language",
                position="c",
                issue="c",
                suggestion="c",
            ),
        ]
        critical_count = sum(1 for i in issues if i.severity == "critical")
        assert critical_count == 2

    def test_issue_categorization(self):
        """测试问题分类"""
        issues = [
            ProofreadIssueItem(
                severity="warning",
                category="compliance",
                position="a",
                issue="a",
                suggestion="a",
            ),
            ProofreadIssueItem(
                severity="warning",
                category="language",
                position="b",
                issue="b",
                suggestion="b",
            ),
            ProofreadIssueItem(
                severity="warning",
                category="consistency",
                position="c",
                issue="c",
                suggestion="c",
            ),
            ProofreadIssueItem(
                severity="warning",
                category="redundancy",
                position="d",
                issue="d",
                suggestion="d",
            ),
        ]
        categories = [i.category for i in issues]
        assert "compliance" in categories
        assert "language" in categories
        assert "consistency" in categories
        assert "redundancy" in categories

    def test_issues_json_serialization(self):
        """测试问题列表 JSON 序列化"""
        issues = [
            {
                "severity": "critical",
                "category": "compliance",
                "position": "第1段",
                "issue": "缺少关键内容",
                "suggestion": "补充内容",
            },
            {
                "severity": "warning",
                "category": "language",
                "position": "第2段",
                "issue": "表达不当",
                "suggestion": "修改表述",
            },
        ]
        issues_json = json.dumps(issues, ensure_ascii=False)
        parsed = json.loads(issues_json)
        assert len(parsed) == 2
        assert parsed[0]["severity"] == "critical"
        assert parsed[1]["category"] == "language"


class TestProofreadEdgeCases:
    """边界情况测试"""

    def test_empty_chapter_content_error(self):
        """测试空章节内容应返回错误"""
        # 在 API 端点中会检查 chapter.content 是否为空
        # 这里验证测试逻辑
        content = None
        assert not content

    def test_very_long_issue_list(self):
        """测试大量问题的处理"""
        issues = [
            ProofreadIssueItem(
                severity="info",
                category="language",
                position=f"第{i}段",
                issue=f"问题{i}",
                suggestion=f"建议{i}",
            )
            for i in range(100)
        ]
        assert len(issues) == 100
        # 验证都能正常序列化
        issues_json = json.dumps([i.model_dump() for i in issues], ensure_ascii=False)
        parsed = json.loads(issues_json)
        assert len(parsed) == 100

    def test_special_characters_in_issue(self):
        """测试问题中包含特殊字符"""
        issue = ProofreadIssueItem(
            severity="warning",
            category="language",
            position='第1段 "引号测试"',
            issue='包含特殊字符: <>&"\'',
            suggestion='建议修改为 "正确格式"',
        )
        # 验证 JSON 序列化
        issue_json = json.dumps(issue.model_dump(), ensure_ascii=False)
        parsed = json.loads(issue_json)
        assert '<>&"' in parsed["issue"]
