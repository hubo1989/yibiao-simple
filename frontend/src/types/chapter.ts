/**
 * 章节相关类型定义
 */

export type ChapterStatus = 'pending' | 'generating' | 'generated' | 'reviewing' | 'finalized' | 'error';

export interface ChapterContentResponse {
  id: string;
  chapter_number: string;
  title: string;
  content: string | null;
  rating_item?: string | null;
  chapter_role?: string | null;
  avoid_overlap?: string | null;
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

export interface ProjectChapterReference {
  id: string;
  chapter_number: string;
  title: string;
  parent_id: string | null;
  status: ChapterStatus;
}

export interface ProjectChapterListResponse {
  project_id: string;
  chapters: ProjectChapterReference[];
  total_count: number;
}

export const CHAPTER_STATUS_LABELS: Record<ChapterStatus, string> = {
  pending: '待生成',
  generating: '生成中',
  generated: '已生成',
  reviewing: '校对中',
  finalized: '已定稿',
  error: '生成失败',
};

export const CHAPTER_STATUS_COLORS: Record<ChapterStatus, string> = {
  pending: 'bg-gray-100 text-gray-800',
  generating: 'bg-blue-100 text-blue-800',
  generated: 'bg-green-100 text-green-800',
  reviewing: 'bg-yellow-100 text-yellow-800',
  finalized: 'bg-blue-100 text-blue-800',
  error: 'bg-red-100 text-red-800',
};
