/**
 * 状态颜色映射工具函数
 */

export type StatusType = 'default' | 'processing' | 'success' | 'error' | 'warning';

/**
 * 项目状态颜色映射
 */
export const projectStatusColors: Record<string, StatusType> = {
  draft: 'default',
  in_progress: 'processing',
  completed: 'success',
  approved: 'success',
  rejected: 'error',
  pending_review: 'warning',
};

/**
 * 获取状态对应的颜色类型
 */
export function getStatusColor(status: string): StatusType {
  return projectStatusColors[status] || 'default';
}

/**
 * 获取 Ant Design Tag 的 color 属性
 */
export function getTagColor(status: string): string {
  const colorMap: Record<string, string> = {
    draft: 'default',
    in_progress: 'processing',
    completed: 'success',
    approved: 'success',
    rejected: 'error',
    pending_review: 'warning',
  };
  return colorMap[status] || 'default';
}
