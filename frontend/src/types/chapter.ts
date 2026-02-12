/**
 * 章节相关类型定义
 */

export type ChapterStatus = 'pending' | 'generated' | 'reviewing' | 'finalized';

export interface ChapterContentResponse {
  id: string;
  chapter_number: string;
  title: string;
  content: string | null;
  status: ChapterStatus;
  locked_by: string | null;
  locked_at: string | null;
  locked_by_username: string | null;
  is_locked: boolean;
  lock_expired: boolean;
}

export interface LockResponse {
  success: boolean;
  chapter_id: string;
  locked_by: string | null;
  locked_at: string | null;
  locked_by_username: string | null;
  message: string;
}

export interface StatusUpdateResponse {
  id: string;
  chapter_number: string;
  title: string;
  old_status: string;
  new_status: string;
  message: string;
}

export const CHAPTER_STATUS_LABELS: Record<ChapterStatus, string> = {
  pending: '待生成',
  generated: '已生成',
  reviewing: '校对中',
  finalized: '已定稿',
};

export const CHAPTER_STATUS_COLORS: Record<ChapterStatus, string> = {
  pending: 'bg-gray-100 text-gray-800',
  generated: 'bg-green-100 text-green-800',
  reviewing: 'bg-yellow-100 text-yellow-800',
  finalized: 'bg-blue-100 text-blue-800',
};
