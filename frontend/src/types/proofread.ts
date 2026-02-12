/**
 * 校对相关类型定义
 */

export type IssueSeverity = 'critical' | 'warning' | 'info';
export type IssueCategory = 'compliance' | 'language' | 'consistency' | 'redundancy';

export interface ProofreadIssue {
  severity: IssueSeverity;
  category: IssueCategory;
  position: string;
  issue: string;
  suggestion: string;
}

export interface ProofreadResult {
  id: string;
  chapter_id: string;
  project_id: string;
  issues: ProofreadIssue[];
  summary: string;
  issue_count: number;
  critical_count: number;
  status_changed: boolean;
  created_at: string;
}

// 严重程度配置
export const ISSUE_SEVERITY_CONFIG: Record<IssueSeverity, {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
}> = {
  critical: {
    label: '严重',
    color: 'text-red-700',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-300',
  },
  warning: {
    label: '警告',
    color: 'text-yellow-700',
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-300',
  },
  info: {
    label: '提示',
    color: 'text-blue-700',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-300',
  },
};

// 问题类别配置
export const ISSUE_CATEGORY_CONFIG: Record<IssueCategory, {
  label: string;
  icon: string;
}> = {
  compliance: {
    label: '合规性',
    icon: '📋',
  },
  language: {
    label: '语言质量',
    icon: '📝',
  },
  consistency: {
    label: '一致性',
    icon: '🔗',
  },
  redundancy: {
    label: '冗余',
    icon: '📄',
  },
};
