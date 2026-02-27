/**
 * 提示词配置相关类型定义
 */

// 提示词类别
export type PromptCategory = 'analysis' | 'generation' | 'check';

// 提示词类别中文名称
export const PROMPT_CATEGORY_NAMES: Record<PromptCategory, string> = {
  analysis: '解析类',
  generation: '生成类',
  check: '检查类',
};

// 提示词响应
export interface PromptResponse {
  scene_key: string;
  scene_name: string;
  category: PromptCategory;
  prompt: string;
  available_vars: Record<string, string> | null;
  version: number;
  is_customized: boolean;
  updated_at: string | null;
}

// 提示词列表响应
export interface PromptListResponse {
  items: PromptResponse[];
  total: number;
}

// 提示词更新请求
export interface PromptUpdate {
  prompt: string;
}

// 提示词版本响应
export interface PromptVersionResponse {
  id: string;
  version: number;
  prompt: string;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
}

// 提示词版本列表响应
export interface PromptVersionListResponse {
  items: PromptVersionResponse[];
  total: number;
}

// 项目提示词配置
export interface ProjectPromptConfig {
  scene_key: string;
  scene_name: string;
  category: PromptCategory;
  prompt: string;
  available_vars: Record<string, string> | null;
  source: 'project' | 'global' | 'builtin';
  has_project_override: boolean;
  has_global_override: boolean;
}

// 项目提示词配置列表响应
export interface ProjectPromptConfigListResponse {
  items: ProjectPromptConfig[];
  total: number;
}

// 项目提示词覆盖请求
export interface ProjectPromptOverride {
  prompt: string;
}

// 提示词回滚请求
export interface PromptRollbackRequest {
  version: number;
}

// 场景定义（用于前端显示）
export interface PromptScene {
  key: string;
  name: string;
  category: PromptCategory;
  description: string;
}
