/**
 * 知识库相关类型定义
 */

export type DocType = 'history_bid' | 'company_info' | 'case_fragment' | 'other';
export type Scope = 'global' | 'enterprise' | 'user';
export type ContentSource = 'file' | 'manual';
export type IndexStatus = 'pending' | 'indexing' | 'completed' | 'failed';

export interface KnowledgeDoc {
  id: string;
  title: string;
  doc_type: DocType;
  scope: Scope;
  content_source: ContentSource;
  file_type?: string;
  pageindex_status: IndexStatus;
  pageindex_error?: string;
  vector_index_status?: IndexStatus;
  vector_index_error?: string;
  tags: string[];
  category?: string;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocCreate {
  title: string;
  content: string;
  doc_type: DocType;
  scope: Scope;
  tags?: string[];
  category?: string;
}

export interface KnowledgeSearchRequest {
  chapter_title: string;
  chapter_description?: string;
  parent_chapters?: Array<{ title: string; description: string }>;
  project_overview?: string;
  top_k?: number;
  use_vector?: boolean;
}

export interface KnowledgeSearchResult {
  id: string;
  title: string;
  doc_type: DocType;
  content: string;
  score: number;
  relevance_reason: string;
}

export interface KnowledgeSearchResponse {
  results: KnowledgeSearchResult[];
  total: number;
}

export const DOC_TYPE_LABELS: Record<DocType, string> = {
  history_bid: '历史标书',
  company_info: '企业资料',
  case_fragment: '案例片段',
  other: '其他',
};

export const SCOPE_LABELS: Record<Scope, string> = {
  global: '全局',
  enterprise: '企业',
  user: '个人',
};

export const INDEX_STATUS_LABELS: Record<IndexStatus, string> = {
  pending: '待索引',
  indexing: '索引中',
  completed: '已完成',
  failed: '失败',
};
