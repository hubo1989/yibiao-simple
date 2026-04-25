/**
 * 共享错误处理工具函数
 */

export interface ApiError {
  response?: {
    data?: {
      detail?: string;
    };
    status?: number;
  };
  message?: string;
}

/**
 * 从 API 错误中提取可读的错误消息
 */
export function getErrorMessage(error: unknown, fallback: string): string {
  const apiError = error as ApiError;
  return apiError?.response?.data?.detail || apiError?.message || fallback;
}

/**
 * Markdown 组件 props 类型
 */
export interface MarkdownComponentProps {
  children?: React.ReactNode;
}

/**
 * 状态颜色映射
 */
export const statusColors: Record<string, string> = {
  draft: 'default',
  in_progress: 'processing',
  completed: 'success',
  approved: 'success',
  rejected: 'error',
  pending_review: 'warning',
};

/**
 * 获取文件 URL
 * @deprecated 请从 services/api.ts 中导入 getFileUrl，此处仅保留向后兼容性
 */
export { getFileUrl } from '../services/api';
