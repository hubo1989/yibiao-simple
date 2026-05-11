"""反幻觉策略服务 — 纯规则扫描，检测无证据支撑的企业能力表述

不调用 LLM，全部基于正则匹配 + 证据库交叉验证。
"""
import re
from dataclasses import dataclass


@dataclass
class HallucinationIssue:
    severity: str   # critical / warning / info
    category: str   # certification / project_case / personnel / commitment / metric
    text: str       # 匹配到的原文
    reason: str     # 为什么被标记
    suggestion: str # 修改建议


class AntiHallucinationService:
    # ── 模式定义 ──────────────────────────────────────────────
    CERT_PATTERNS = [
        (r"ISO\s?\d{4,5}", "ISO认证"),
        (r"CMMI\s?[CLM]?\d?", "CMMI认证"),
        (r"等保[一二三四五]级", "等保认证"),
        (r"资质证书", "资质证书"),
        (r"营业执照", "营业执照"),
        (r"高新技术企业", "高新企业"),
        (r"软件著作权", "软件著作权"),
        (r"专利证?号?", "专利"),
    ]

    CASE_PATTERNS = [
        (r"成功实施", "项目案例"),
        (r"典型案例", "项目案例"),
        (r"服务过.{2,20}?(客户|单位|企业)", "项目案例"),
        (r"类似项目经验", "项目案例"),
        (r"承建过", "项目案例"),
    ]

    PERSONNEL_PATTERNS = [
        (r"高级工程师", "人员资质"),
        (r"PMP[证认]", "人员资质"),
        (r"专家[团]队", "人员资质"),
        (r"注册[\u4e00-\u9fa5]{2,6}师", "人员资质"),
    ]

    COMMITMENT_PATTERNS = [
        (r"保证[\u4e00-\u9fa5]{0,10}?(不|无)", "确定性承诺"),
        (r"确保[\u4e00-\u9fa5]{0,10}", "确定性承诺"),
        (r"完全满足", "确定性承诺"),
        (r"零(风险|故障)", "确定性承诺"),
        (r"100%?(可靠|安全)", "确定性承诺"),
    ]

    METRIC_PATTERNS = [
        (r"\d{2,}\.\d+%", "数字指标"),
        (r"7[x×]24", "服务指标"),
        (r"响应时间.{0,5}?\d+", "服务指标"),
        (r"\d+.{0,3}?(人天|人月|工作日)", "工作量指标"),
    ]

    # ── 核心扫描 ──────────────────────────────────────────────

    def scan_text(
        self, text: str, evidence_refs: list[dict] | None = None
    ) -> list[HallucinationIssue]:
        """扫描文本中需要证据支撑的表述。

        evidence_refs 格式: [{source_type, source_title, quote}, ...]
        如果证据库中包含匹配内容，严重程度会降级为 info。
        """
        issues: list[HallucinationIssue] = []
        if evidence_refs is None:
            evidence_refs = []

        evidence_text = " ".join(
            ref.get("source_title", "") + " " + ref.get("quote", "")
            for ref in evidence_refs
        ).lower()

        issues.extend(self._scan_category(
            text, evidence_text, self.CERT_PATTERNS,
            "certification", "资质证书类表述需要对应证书素材支撑",
        ))
        issues.extend(self._scan_category(
            text, evidence_text, self.CASE_PATTERNS,
            "project_case", "项目案例类表述需要对应案例素材支撑",
        ))
        issues.extend(self._scan_category(
            text, evidence_text, self.PERSONNEL_PATTERNS,
            "personnel", "人员能力表述需要对应人员资质素材支撑",
        ))
        issues.extend(self._scan_category(
            text, evidence_text, self.COMMITMENT_PATTERNS,
            "commitment", "确定性承诺需要招标条款+企业证据支撑",
            default_severity="warning",
        ))
        issues.extend(self._scan_category(
            text, evidence_text, self.METRIC_PATTERNS,
            "metric", "具体数字指标需要数据来源支撑",
            default_severity="warning",
        ))

        return issues

    def scan_chapters(
        self,
        chapters: list[dict],
        evidence_refs: list[dict] | None = None,
    ) -> dict[str, list[HallucinationIssue]]:
        """批量扫描多个章节，返回 {chapter_id: [issues]}"""
        result: dict[str, list[HallucinationIssue]] = {}
        for ch in chapters:
            content = ch.get("content", "")
            if not content:
                continue
            chapter_issues = self.scan_text(content, evidence_refs)
            if chapter_issues:
                result[str(ch.get("id", ""))] = chapter_issues
        return result

    # ── 内部方法 ──────────────────────────────────────────────

    def _scan_category(
        self,
        text: str,
        evidence_text: str,
        patterns: list[tuple[str, str]],
        category: str,
        reason: str,
        default_severity: str = "critical",
    ) -> list[HallucinationIssue]:
        issues: list[HallucinationIssue] = []
        for pattern, label in patterns:
            for match in re.finditer(pattern, text):
                matched = match.group()
                severity = default_severity
                if self._evidence_covers(evidence_text, matched, label):
                    severity = "info"
                issues.append(HallucinationIssue(
                    severity=severity,
                    category=category,
                    text=matched,
                    reason=f"{label}：{reason}",
                    suggestion=f"请补充「{label}」对应的支撑材料，或移除此表述",
                ))
        return issues

    @staticmethod
    def _evidence_covers(evidence_text: str, claim: str, label: str) -> bool:
        """检查证据文本是否覆盖该声明"""
        claim_lower = claim.lower()
        if claim_lower in evidence_text:
            return True
        keywords = re.findall(r"[\w\u4e00-\u9fa5]{2,}", claim_lower)
        return any(kw in evidence_text for kw in keywords if len(kw) >= 2)
