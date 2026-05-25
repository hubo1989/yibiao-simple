from app.services.review_service import ReviewService


def test_normalize_issue_ids_preserves_existing_and_adds_missing():
    responsiveness = {"items": [{"rating_item": "评分项"}, {"id": "custom", "rating_item": "已有"}]}
    compliance = {"items": [{"compliance_category": "格式"}]}
    consistency = {"contradictions": [{"description": "前后不一致"}]}

    ReviewService.normalize_issue_ids(responsiveness, compliance, consistency)

    assert responsiveness["items"][0]["id"] == "responsiveness-1"
    assert responsiveness["items"][1]["id"] == "custom"
    assert compliance["items"][0]["id"] == "compliance-1"
    assert consistency["contradictions"][0]["id"] == "consistency-1"


def test_generate_summary_counts_direct_severity_values():
    compliance = {
        "items": [
            {"severity": "critical", "check_result": "fail"},
            {"severity": "warning", "check_result": "warning"},
            {"severity": "info", "check_result": "pass"},
        ]
    }
    consistency = {"contradictions": [{"severity": "critical"}]}

    summary = ReviewService.generate_summary(None, compliance, consistency)

    assert summary["total_issues"] == 4
    assert summary["issue_distribution"]["critical"] == 2
    assert summary["issue_distribution"]["warning"] == 1
    assert summary["issue_distribution"]["info"] == 1


def test_fallback_dimension_result_wraps_non_json_compliance_text():
    result = ReviewService._fallback_dimension_result("bid_review_compliance", "项目名称与编号不一致")

    assert result["items"][0]["check_result"] == "warning"
    assert "项目名称与编号不一致" in result["items"][0]["detail"]


def test_fallback_dimension_result_wraps_non_json_consistency_text():
    result = ReviewService._fallback_dimension_result("bid_review_consistency", "前后项目范围冲突")

    assert result["contradictions"][0]["severity"] == "warning"
    assert "前后项目范围冲突" in result["contradictions"][0]["detail_a"]


def test_fallback_dimension_result_wraps_non_json_responsiveness_text():
    result = ReviewService._fallback_dimension_result("bid_review_responsiveness", "评分项缺少响应")

    assert result["items"][0]["coverage_status"] == "risk"
    assert "评分项缺少响应" in result["items"][0]["evidence"]
