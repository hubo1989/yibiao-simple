/**
 * 项目相关类型定义
 */

export type ProjectStatus = 'draft' | 'in_progress' | 'reviewing' | 'completed';

export type ProjectMemberRole = 'owner' | 'editor' | 'reviewer';

export interface Project {
  id: string;
  name: string;
  description: string | null;
  creator_id: string | null;
  status: ProjectStatus;
  file_content: string | null;
  project_overview: string | null;
  tech_requirements: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string | null;
  creator_id: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface ProjectProgress {
  total_chapters: number;
  pending: number;
  generated: number;
  reviewing: number;
  finalized: number;
  completion_percentage: number;
}

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: '草稿',
  in_progress: '进行中',
  reviewing: '审核中',
  completed: '已完成',
};

export const PROJECT_STATUS_COLORS: Record<ProjectStatus, string> = {
  draft: 'bg-gray-100 text-gray-800',
  in_progress: 'bg-blue-100 text-blue-800',
  reviewing: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
};
