/**
 * 类型定义
 */

export interface ConfigData {
  model_name: string;
}

export interface OutlineItem {
  id: string;
  title: string;
  description: string;
  rating_item?: string;
  chapter_role?: string;
  avoid_overlap?: string;
  children?: OutlineItem[];
  content?: string;
  generationError?: string;
  status?: 'pending' | 'generating' | 'generated'; // 章节状态：待生成、生成中、已生成
}

export interface OutlineData {
  outline: OutlineItem[];
  project_name?: string;
  project_overview?: string;
}

export interface AppState {
  currentStep: number;
  config: ConfigData;
  fileContent: string;
  projectOverview: string;
  techRequirements: string;
  outlineData: OutlineData | null;
  selectedChapter: string;
}