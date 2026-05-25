"""反幻觉策略服务测试"""
from app.services.anti_hallucination_service import AntiHallucinationService


svc = AntiHallucinationService()


class TestCertificationScanning:
    def test_iso_claim_no_evidence_critical(self):
        issues = svc.scan_text("我司具备 ISO9001 质量管理体系认证")
        cert_issues = [i for i in issues if i.category == "certification"]
        assert len(cert_issues) >= 1
        assert cert_issues[0].severity == "critical"
        assert "ISO9001" in cert_issues[0].text or "ISO" in cert_issues[0].text

    def test_iso_claim_with_evidence_downgraded(self):
        evidence = [{"source_title": "ISO9001证书", "quote": "ISO 9001认证"}]
        issues = svc.scan_text("我司具备 ISO9001 质量管理体系认证", evidence)
        cert_issues = [i for i in issues if i.category == "certification"]
        assert len(cert_issues) >= 1
        assert cert_issues[0].severity == "info"

    def test_no_cert_claim_no_issues(self):
        issues = svc.scan_text("本项目采用微服务架构设计方案")
        cert_issues = [i for i in issues if i.category == "certification"]
        assert len(cert_issues) == 0


class TestProjectCaseScanning:
    def test_case_claim_no_evidence(self):
        issues = svc.scan_text("我司成功实施过多个类似项目")
        case_issues = [i for i in issues if i.category == "project_case"]
        assert len(case_issues) >= 1
        assert case_issues[0].severity == "critical"

    def test_case_claim_with_evidence(self):
        evidence = [{"source_title": "XX银行核心系统改造项目", "quote": "成功实施"}]
        issues = svc.scan_text("我司成功实施过多个类似项目", evidence)
        case_issues = [i for i in issues if i.category == "project_case"]
        assert len(case_issues) >= 1
        assert case_issues[0].severity == "info"


class TestCommitmentScanning:
    def test_commitment_warning(self):
        issues = svc.scan_text("我们将确保系统零故障运行")
        commit_issues = [i for i in issues if i.category == "commitment"]
        assert len(commit_issues) >= 1
        assert commit_issues[0].severity == "warning"


class TestMetricScanning:
    def test_metric_warning(self):
        issues = svc.scan_text("系统可用性达到99.99%")
        metric_issues = [i for i in issues if i.category == "metric"]
        assert len(metric_issues) >= 1
        assert metric_issues[0].severity == "warning"

    def test_7x24_metric(self):
        issues = svc.scan_text("提供7x24小时技术支持服务")
        metric_issues = [i for i in issues if i.category == "metric"]
        assert len(metric_issues) >= 1


class TestNormalText:
    def test_no_issues_for_normal_text(self):
        issues = svc.scan_text("本项目的技术方案基于主流开源框架构建，采用前后端分离架构。")
        assert len(issues) == 0


class TestScanChapters:
    def test_scan_multiple_chapters(self):
        chapters = [
            {"id": "ch1", "title": "技术方案", "content": "我司具备 ISO9001 认证"},
            {"id": "ch2", "title": "实施方案", "content": "项目采用敏捷开发方法论"},
            {"id": "ch3", "title": "案例", "content": "成功实施过大型项目"},
        ]
        result = svc.scan_chapters(chapters)
        assert "ch1" in result
        assert "ch3" in result
        assert "ch2" not in result  # normal text, no issues

    def test_empty_chapters_no_error(self):
        result = svc.scan_chapters([])
        assert result == {}
