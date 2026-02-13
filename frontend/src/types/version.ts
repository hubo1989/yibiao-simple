/**
 * 版本历史相关类型定义
 */

export type ChangeType = 'content_update' | 'status_change' | 'manual_edit' | 'rollback' | 'ai_generate';

export interface VersionSummary {
  id: string;
  project_id: string;
  chapter_id: string | null;
  version_number: number;
  change_type: ChangeType;
  change_summary: string | null;
  created_by: string | null;
  created_at: string;
}

export interface VersionResponse extends VersionSummary {
  snapshot_data: Record<string, unknown>;
}

export interface VersionList {
  items: VersionSummary[];
  total: number;
  project_id: string;
}

export interface VersionDiffInfo {
  id: string;
  version_number: number;
  created_at: string;
  change_type: string;
}

export interface ChapterChange {
  type: 'added' | 'deleted' | 'modified';
  chapter_id: string;
  chapter_number: string | null;
  title: string | null;
  old_content: string | null;
  new_content: string | null;
  old_title: string | null;
  new_title: string | null;
  content_changed: boolean | null;
  title_changed: boolean | null;
}

export interface VersionDiffSummary {
  total_changes: number;
  added: number;
  deleted: number;
  modified: number;
  changes: ChapterChange[];
}

export interface VersionDiffResponse {
  v1: VersionDiffInfo;
  v2: VersionDiffInfo;
  diff: VersionDiffSummary;
}

export interface RestoredChapter {
  id: string;
  chapter_number: string;
  action: string;
}

export interface VersionRollbackResponse {
  success: boolean;
  target_version_number: number | null;
  new_version_id: string | null;
  new_version_number: number | null;
  pre_snapshot_id: string | null;
  restored_chapters: RestoredChapter[];
  error: string | null;
}

export const CHANGE_TYPE_LABELS: Record<ChangeType, string> = {
  content_update: '内容更新',
  status_change: '状态变更',
  manual_edit: '手动编辑',
  rollback: '版本回滚',
  ai_generate: 'AI 生成',
};

export const CHANGE_TYPE_COLORS: Record<ChangeType, string> = {
  content_update: 'bg-blue-100 text-blue-800',
  status_change: 'bg-yellow-100 text-yellow-800',
  manual_edit: 'bg-purple-100 text-purple-800',
  rollback: 'bg-orange-100 text-orange-800',
  ai_generate: 'bg-green-100 text-green-800',
};
