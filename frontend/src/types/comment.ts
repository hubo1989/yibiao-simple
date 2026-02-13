/**
 * 评论批注相关类型定义
 */

export interface Comment {
  id: string;
  chapter_id: string;
  user_id: string;
  username: string;
  content: string;
  position_start: number | null;
  position_end: number | null;
  is_resolved: boolean;
  resolved_by: string | null;
  resolved_by_username: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CommentListResponse {
  items: Comment[];
  total: number;
}

export interface CommentCreateRequest {
  content: string;
  position_start?: number;
  position_end?: number;
}
