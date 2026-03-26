"""标书审查相关 Pydantic Schema"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..models.bid_review_task import ReviewTaskStatus


# === 审查维度与状态类型 ===

ReviewDimension: type = Literal["responsiveness", "compliance", "consistency"]
CoverageStatus: type = Literal["covered", "partial", "missing", "risk"]
Severity: type = Literal["critical", "warning", "info"]
RiskLevel: type = Literal["low", "medium", "high"]


# === 响应性审查 ===

class SourceRef(BaseModel):
    """招标文件引用"""
    ref_id: str = Field("", description="引用ID")
    source_type: str = Field("tender_document", description="来源类型")
    location: str = Field("", description="在招标文件中的位置")
    quote: str = Field("", description="引用原文")
    relation: str = Field("", description="与投标文件的关联说明")


class ResponsivenessItem(BaseModel):
    """响应性审查项"""
    rating_item: str = Field(..., description="评分项名称")
    score: int = Field(0, description="实际得分")
    max_score: int = Field(0, description="满分")
    coverage_status: CoverageStatus = Field("missing", description="覆盖状态")
    evidence: str = Field("", description="证据说明")
    source_refs: list[SourceRef] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list, description="问题列表")
    suggestions: list[str] = Field(default_factory=list, description="修改建议")
    rewrite_suggestions: list[str] = Field(default_factory=list, description="参考改写建议")
    chapter_targets: list[str] = Field(default_factory=list, description="涉及的投标文件章节")
    confidence: Literal["high", "medium", "low"] = Field("medium", description="置信度")


# === 合规性审查 ===

class ComplianceItem(BaseModel):
    """合规性审查项"""
    compliance_category: str = Field(..., description="合规类别")
    clause_text: str = Field("", description="招标条款原文")
    check_result: Literal["pass", "warning", "fail"] = Field("warning", description="检查结果")
    detail: str = Field("", description="详细说明")
    bid_location: str = Field("", description="投标文件中的位置")
    severity: Severity = Field("warning", description="严重程度")
    suggestion: str = Field("", description="修改建议")


# === 一致性审查 ===

class ConsistencyItem(BaseModel):
    """一致性审查项"""
    severity: Severity = Field("warning", description="严重程度")
    category: str = Field("", description="矛盾类别")
    description: str = Field("", description="矛盾描述")
    chapter_a: str = Field("", description="章节A编号和标题")
    detail_a: str = Field("", description="章节A中的内容")
    chapter_b: str = Field("", description="章节B编号和标题")
    detail_b: str = Field("", description="章节B中的内容")
    suggestion: str = Field("", description="修改建议")


# === 审查汇总 ===

class IssueDistribution(BaseModel):
    """问题分布统计"""
    critical: int = 0
    warning: int = 0
    info: int = 0


class ReviewSummary(BaseModel):
    """审查汇总"""
    overall_score: int = Field(0, description="综合得分")
    score_max: int = Field(100, description="满分")
    coverage_rate: float = Field(0.0, description="覆盖率")
    risk_level: RiskLevel = Field("medium", description="风险等级")
    total_issues: int = Field(0, description="问题总数")
    issue_distribution: IssueDistribution = Field(
        default_factory=IssueDistribution
    )


# === API 请求/响应 ===

class ReviewExecuteRequest(BaseModel):
    """执行审查请求"""
    task_id: uuid.UUID = Field(..., description="任务ID")
    dimensions: list[ReviewDimension] = Field(
        default=["responsiveness", "compliance", "consistency"]
    )
    scope: str = Field("full", description="审查范围: full 或 chapters")
    chapter_ids: list[str] | None = Field(None, description="指定章节ID列表")
    model_name: str | None = Field(None, description="模型名称")
    provider_config_id: uuid.UUID | None = Field(None, description="Provider配置ID")
    use_knowledge: bool = Field(False, description="是否使用知识库")
    knowledge_ids: list[str] | None = Field(None, description="知识库ID列表")


class BidFileInfo(BaseModel):
    """投标文件信息"""
    filename: str = ""
    file_size: int = 0
    paragraph_count: int = 0
    heading_count: int = 0


class ReviewConfig(BaseModel):
    """审查配置"""
    dimensions: list[ReviewDimension] = []
    scope: str = "full"
    model_name: str | None = None


class ResponsivenessResult(BaseModel):
    """响应性审查结果"""
    items: list[ResponsivenessItem] = []


class ComplianceResult(BaseModel):
    """合规性审查结果"""
    items: list[ComplianceItem] = []


class ConsistencyResult(BaseModel):
    """一致性审查结果"""
    contradictions: list[ConsistencyItem] = []


class BidFileUploadResponse(BaseModel):
    """投标文件上传响应"""
    success: bool
    message: str
    task_id: str | None = None
    file_info: BidFileInfo | None = None


class ReviewHistoryItem(BaseModel):
    """审查历史条目"""
    task_id: uuid.UUID
    status: ReviewTaskStatus
    summary: ReviewSummary | None = None
    model_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewHistoryResponse(BaseModel):
    """审查历史响应"""
    items: list[ReviewHistoryItem]


class ReviewResultResponse(BaseModel):
    """审查结果响应"""
    task_id: uuid.UUID
    project_id: uuid.UUID
    status: ReviewTaskStatus
    config: ReviewConfig
    summary: ReviewSummary | None = None
    responsiveness: ResponsivenessResult | None = None
    compliance: ComplianceResult | None = None
    consistency: ConsistencyResult | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewExportRequest(BaseModel):
    """导出带批注Word请求"""
    task_id: uuid.UUID = Field(..., description="任务ID")
    dimensions: list[ReviewDimension] = Field(
        default=["responsiveness", "compliance", "consistency"]
    )
