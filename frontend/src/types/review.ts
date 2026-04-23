/**
 * 标书审查相关类型定义
 */

export type ReviewDimension = 'responsiveness' | 'compliance' | 'consistency';
export type ReviewTaskStatus = 'pending' | 'processing' | 'completed' | 'failed';
export type CoverageStatus = 'covered' | 'partial' | 'missing' | 'risk';
export type Severity = 'critical' | 'warning' | 'info';
export type RiskLevel = 'low' | 'medium' | 'high';

// === 响应性审查 ===

export interface SourceRef {
  ref_id: string;
  source_type: string;
  location: string;
  quote: string;
  relation: string;
}

export interface ResponsivenessItem {
  rating_item: string;
  score: number;
  max_score: number;
  coverage_status: CoverageStatus;
  evidence: string;
  source_refs: SourceRef[];
  issues: string[];
  suggestions: string[];
  rewrite_suggestions: string[];
  chapter_targets: string[];
  confidence: 'high' | 'medium' | 'low';
}

// === 合规性审查 ===

export interface ComplianceItem {
  compliance_category: string;
  clause_text: string;
  check_result: 'pass' | 'warning' | 'fail';
  detail: string;
  bid_location: string;
  severity: Severity;
  suggestion: string;
}

// === 一致性审查 ===

export interface ConsistencyItem {
  severity: Severity;
  category: string;
  description: string;
  chapter_a: string;
  detail_a: string;
  chapter_b: string;
  detail_b: string;
  suggestion: string;
}

// === 审查汇总 ===

export interface IssueDistribution {
  critical: number;
  warning: number;
  info: number;
}

export interface ReviewSummary {
  overall_score: number;
  score_max: number;
  coverage_rate: number;
  risk_level: RiskLevel;
  total_issues: number;
  issue_distribution: IssueDistribution;
}

// === API 请求/响应 ===

export interface ReviewExecuteRequest {
  task_id: string;
  dimensions: ReviewDimension[];
  scope?: string;
  chapter_ids?: string[];
  model_name?: string;
  provider_config_id?: string;
  use_knowledge?: boolean;
  knowledge_ids?: string[];
}

export interface BidFileUploadResponse {
  success: boolean;
  message: string;
  task_id: string | null;
  file_info: {
    filename: string;
    file_size: number;
    paragraph_count: number;
    heading_count: number;
  } | null;
}

export interface ReviewHistoryItem {
  task_id: string;
  status: ReviewTaskStatus;
  bid_filename: string | null;
  summary: ReviewSummary | null;
  model_name: string | null;
  created_at: string;
}

export interface ReviewHistoryResponse {
  items: ReviewHistoryItem[];
}

export interface ReviewResultResponse {
  task_id: string;
  project_id: string;
  status: ReviewTaskStatus;
  config: {
    dimensions: ReviewDimension[];
    scope: string;
    model_name: string | null;
  };
  summary: ReviewSummary | null;
  responsiveness: { items: ResponsivenessItem[] } | null;
  compliance: { items: ComplianceItem[] } | null;
  consistency: { contradictions: ConsistencyItem[] } | null;
  error_message?: string | null;
  created_at: string;
}

export interface ReviewExportRequest {
  task_id: string;
  dimensions: ReviewDimension[];
}

// === UI 辅助 ===

export const REVIEW_DIMENSION_LABELS: Record<ReviewDimension, string> = {
  responsiveness: '响应性',
  compliance: '合规性',
  consistency: '一致性',
};

export const COVERAGE_STATUS_LABELS: Record<CoverageStatus, string> = {
  covered: '已覆盖',
  partial: '部分覆盖',
  missing: '未覆盖',
  risk: '有风险',
};

export const COVERAGE_STATUS_COLORS: Record<CoverageStatus, string> = {
  covered: 'green',
  partial: 'orange',
  missing: 'red',
  risk: 'volcano',
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  critical: '高',
  warning: '中',
  info: '低',
};

export const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'red',
  warning: 'orange',
  info: 'blue',
};

export const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  low: '低',
  medium: '中等',
  high: '高',
};

export const RISK_LEVEL_COLORS: Record<RiskLevel, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red',
};

export const REVIEW_TASK_STATUS_LABELS: Record<ReviewTaskStatus, string> = {
  pending: '待执行',
  processing: '审查中',
  completed: '已完成',
  failed: '失败',
};
