/**
 * 跨章节一致性检查相关类型定义
 */

export type ConsistencySeverity = 'critical' | 'warning' | 'info';
export type ConsistencyCategory = 'data' | 'terminology' | 'timeline' | 'commitment' | 'scope';
export type OverallConsistency = 'consistent' | 'minor_issues' | 'major_issues';

export interface ContradictionItem {
  severity: ConsistencySeverity;
  category: ConsistencyCategory;
  description: string;
  chapter_a: string;
  chapter_b: string;
  detail_a: string;
  detail_b: string;
  suggestion: string;
}

export interface ConsistencyCheckResponse {
  contradictions: ContradictionItem[];
  summary: string;
  overall_consistency: OverallConsistency;
  contradiction_count: number;
  critical_count: number;
  created_at: string;
}

// 严重程度配置
export const CONSISTENCY_SEVERITY_CONFIG: Record<ConsistencySeverity, {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
}> = {
  critical: {
    label: '严重矛盾',
    color: 'text-red-700',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-300',
  },
  warning: {
    label: '一般不一致',
    color: 'text-yellow-700',
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-300',
  },
  info: {
    label: '轻微差异',
    color: 'text-blue-700',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-300',
  },
};

// 矛盾类别配置
export const CONSISTENCY_CATEGORY_CONFIG: Record<ConsistencyCategory, {
  label: string;
  icon: string;
}> = {
  data: {
    label: '数据矛盾',
    icon: '🔢',
  },
  terminology: {
    label: '术语矛盾',
    icon: '📚',
  },
  timeline: {
    label: '时间线矛盾',
    icon: '📅',
  },
  commitment: {
    label: '承诺矛盾',
    icon: '✋',
  },
  scope: {
    label: '范围矛盾',
    icon: '📐',
  },
};

// 整体一致性配置
export const OVERALL_CONSISTENCY_CONFIG: Record<OverallConsistency, {
  label: string;
  color: string;
  bgColor: string;
}> = {
  consistent: {
    label: '一致',
    color: 'text-green-700',
    bgColor: 'bg-green-100',
  },
  minor_issues: {
    label: '存在轻微问题',
    color: 'text-yellow-700',
    bgColor: 'bg-yellow-100',
  },
  major_issues: {
    label: '存在严重问题',
    color: 'text-red-700',
    bgColor: 'bg-red-100',
  },
};
