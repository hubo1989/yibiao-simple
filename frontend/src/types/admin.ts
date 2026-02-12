/**
 * 后台管理相关类型定义
 */
import type { UserRole } from './auth';

// ==================== 用户管理类型 ====================

export interface AdminUser {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminUserListResponse {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUserCreate {
  username: string;
  email: string;
  password: string;
  role: UserRole;
  is_active: boolean;
}

export interface AdminUserUpdate {
  username?: string;
  email?: string;
  role?: UserRole;
  is_active?: boolean;
}

export interface ResetPasswordRequest {
  new_password: string;
}

// ==================== API Key 配置类型 ====================

export interface ApiKeyConfig {
  id: string;
  provider: string;
  api_key_masked: string;
  base_url: string | null;
  model_name: string;
  is_default: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyConfigListResponse {
  items: ApiKeyConfig[];
  total: number;
}

export interface ApiKeyConfigCreate {
  provider: string;
  api_key: string;
  base_url?: string;
  model_name?: string;
  is_default?: boolean;
}

// ==================== 操作日志类型 ====================

export type ActionType =
  | 'login'
  | 'logout'
  | 'register'
  | 'project_create'
  | 'project_update'
  | 'project_delete'
  | 'project_view'
  | 'chapter_create'
  | 'chapter_update'
  | 'chapter_delete'
  | 'chapter_lock'
  | 'chapter_unlock'
  | 'content_generate'
  | 'content_edit'
  | 'version_create'
  | 'version_rollback'
  | 'comment_create'
  | 'comment_resolve'
  | 'ai_generate'
  | 'ai_proofread'
  | 'consistency_check';

export interface OperationLogSummary {
  id: string;
  user_id: string | null;
  project_id: string | null;
  action: ActionType;
  ip_address: string | null;
  created_at: string;
  method: string | null;
  path: string | null;
  status_code: number | null;
  duration_ms: number | null;
}

export interface OperationLogListResponse {
  items: OperationLogSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface OperationLogDetail extends OperationLogSummary {
  detail: Record<string, unknown>;
  username: string | null;
  project_name: string | null;
}

export interface OperationLogQuery {
  user_id?: string;
  username?: string;
  project_id?: string;
  action?: ActionType;
  start_time?: string;
  end_time?: string;
  ip_address?: string;
  page?: number;
  page_size?: number;
}

// ==================== 统计类型 ====================

export interface UsageStats {
  total_projects: number;
  total_users: number;
  active_users: number;
  monthly_generations: number;
  estimated_tokens: number;
}

// ==================== 操作类型中文标签 ====================

export const ACTION_TYPE_LABELS: Record<ActionType, string> = {
  login: '登录',
  logout: '登出',
  register: '注册',
  project_create: '创建项目',
  project_update: '更新项目',
  project_delete: '删除项目',
  project_view: '查看项目',
  chapter_create: '创建章节',
  chapter_update: '更新章节',
  chapter_delete: '删除章节',
  chapter_lock: '锁定章节',
  chapter_unlock: '解锁章节',
  content_generate: '生成内容',
  content_edit: '编辑内容',
  version_create: '创建版本',
  version_rollback: '回滚版本',
  comment_create: '创建评论',
  comment_resolve: '解决评论',
  ai_generate: 'AI 生成',
  ai_proofread: 'AI 校对',
  consistency_check: '一致性检查',
};
