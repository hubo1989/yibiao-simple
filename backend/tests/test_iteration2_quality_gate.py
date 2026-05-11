import pytest

from app.models.schemas import ChapterGenerationResult, SourceRef
from app.routers.export import _issue_payload
from app.services.anti_hallucination_service import AntiHallucinationService


def test_anti_hallucination_downgrades_when_evidence_covers_claim():
    service = AntiHallucinationService()
    issues = service.scan_text(
        "我方具备ISO9001认证，并提供7x24小时服务。",
        [{"source_title": "资质证书", "quote": "ISO9001质量管理体系认证证书"}],
    )

    cert_issue = next(issue for issue in issues if issue.category == "certification")
    metric_issue = next(issue for issue in issues if issue.category == "metric")
    assert cert_issue.severity == "info"
    assert metric_issue.severity == "warning"


def test_chapter_generation_result_schema_includes_evidence_chain():
    result = ChapterGenerationResult(
        content="正文",
        source_refs=[
            SourceRef(
                ref_id="ref-1",
                source_type="tender_document",
                source_id="clause-1",
                location="第1页",
                quote="必须满足服务要求",
                relation="响应矩阵绑定的招标条款",
            )
        ],
        hallucination_issues=[],
    )

    payload = result.model_dump()
    assert payload["content"] == "正文"
    assert payload["source_refs"][0]["source_type"] == "tender_document"


def test_export_preflight_issue_payload_shape():
    issue = AntiHallucinationService().scan_text("具备高新技术企业资质", [])[0]
    payload = _issue_payload(issue)

    assert payload["severity"] == "critical"
    assert payload["category"] == "certification"
    assert "suggestion" in payload
