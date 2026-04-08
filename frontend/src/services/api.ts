/**
 * API服务
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import type { User, LoginRequest, RegisterRequest, Token, TokenResponseWithCsrf } from '../types/auth';
import type { ProjectSummary, Project, ProjectCreate, ProjectProgress, ProjectMember } from '../types/project';
import type {
  VersionResponse,
  VersionList,
  VersionDiffResponse,
  VersionRollbackResponse,
} from '../types/version';
import type {
  ChapterContentResponse,
  LockResponse,
  StatusUpdateResponse,
  ChapterStatus,
  ProjectChapterListResponse,
} from '../types/chapter';
import type { Comment, CommentListResponse, CommentCreateRequest } from '../types/comment';
import type { ConsistencyCheckResponse } from '../types/consistency';
import type {
  RatingChecklistResponse,
  ClauseResponseRequest,
  ClauseResponseResult,
  ChapterReverseEnhanceResponse,
} from '../types/bid';
import type {
  AdminUser,
  AdminUserListResponse,
  AdminUserCreate,
  AdminUserUpdate,
  ResetPasswordRequest,
  ApiKeyConfig,
  ApiKeyConfigListResponse,
  ApiKeyConfigCreate,
  ApiKeyConfigUpdate,
  OperationLogListResponse,
  OperationLogQuery,
  UsageStats,
} from '../types/admin';
import type {
  ReviewExecuteRequest,
  BidFileUploadResponse,
  ReviewResultResponse,
  ReviewHistoryResponse,
  ReviewExportRequest,
} from '../types/review';
import type {
  PromptResponse,
  PromptListResponse,
  PromptUpdate,
  PromptVersionListResponse,
  PromptRollbackRequest,
  ProjectPromptConfig,
  ProjectPromptConfigListResponse,
  ProjectPromptOverride,
} from '../types/prompt';
import type {
  RequestLog,
  RequestLogListResponse,
  RequestLogQuery,
  RequestStats,
} from '../types/requestLog';
import type {
  ChapterMaterialBinding,
  MaterialAsset,
  MaterialMatchCandidate,
  MaterialRequirement,
} from '../types/material';

/**
 * 统一提取 API 错误信息，优先使用后端返回的 detail，否则使用兜底中文消息。
 * 页面层 catch 时只需 `message.error(error.message)` 即可，无需重复解析。
 */
function handleApiError(error: unknown, fallback: string): never {
  const detail = (error as AxiosError<{ detail?: string }>)?.response?.data?.detail;
  throw new Error(detail || fallback, { cause: error });
}

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/** 构建文件 URL（用于图片/PDF 预览等） */
export function getFileUrl(path: string | undefined | null): string {
  if (!path) return '';
  return `${API_BASE_URL}/${path.replace(/^\/+/, '')}`;
}

const TOKEN_KEY = 'auth_token';
const CSRF_TOKEN_KEY = 'csrf_token';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  withCredentials: true, // 允许携带 httpOnly cookie
});

// Token 管理函数（仅 access_token 存储在内存/localStorage）
export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(accessToken: string): void {
  localStorage.setItem(TOKEN_KEY, accessToken);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// CSRF Token 管理函数
export function getCsrfToken(): string | null {
  return localStorage.getItem(CSRF_TOKEN_KEY);
}

export function setCsrfToken(csrfToken: string): void {
  localStorage.setItem(CSRF_TOKEN_KEY, csrfToken);
}

export function clearCsrfToken(): void {
  localStorage.removeItem(CSRF_TOKEN_KEY);
}

// 从 cookie 读取 CSRF token（用于首次登录后）
export function getCsrfTokenFromCookie(): string | null {
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : null;
}

export function setAuthToken(token: string | null): void {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common['Authorization'];
  }
}

export function clearAuthToken(): void {
  delete api.defaults.headers.common['Authorization'];
}

// 请求拦截器：自动附加 Authorization header 和 CSRF token
api.interceptors.request.use(
  (config) => {
    // 添加 access token
    const token = getStoredToken();
    if (token && !config.headers['Authorization']) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }

    // 添加 CSRF token（对于状态变更请求）
    const csrfToken = getCsrfToken() || getCsrfTokenFromCookie();
    if (csrfToken && config.method && ['post', 'put', 'delete', 'patch'].includes(config.method.toLowerCase())) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    // 从响应中提取 CSRF token（如果有）
    const csrfToken = response.data?.csrf_token;
    if (csrfToken) {
      setCsrfToken(csrfToken);
    }
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // 如果是 401 错误且不是刷新 token 请求，尝试刷新 token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // refresh token 在 httpOnly cookie 中，自动携带
        const response = await axios.post<Token>(`${API_BASE_URL}/api/auth/refresh`, {}, {
          withCredentials: true,
        });

        const { access_token } = response.data;
        setStoredToken(access_token);
        setAuthToken(access_token);

        // 更新 CSRF token（如果有）
        const newCsrfToken = getCsrfTokenFromCookie();
        if (newCsrfToken) {
          setCsrfToken(newCsrfToken);
        }

        // 重试原始请求
        originalRequest.headers['Authorization'] = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch {
        // 刷新 token 失败，清除认证状态
        clearStoredToken();
        clearAuthToken();
        clearCsrfToken();
        // 跳转到登录页
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }

    console.error('API请求错误:', error);
    return Promise.reject(error);
  }
);

// 认证相关 API
export const authApi = {
  // 获取 CSRF token（登录前调用）
  getCsrfToken: async (): Promise<{ csrf_token: string }> => {
    const response = await axios.get<{ csrf_token: string }>(`${API_BASE_URL}/api/auth/csrf-token`, {
      withCredentials: true,
    });
    // 存储 CSRF token
    setCsrfToken(response.data.csrf_token);
    return response.data;
  },

  // 用户登录
  login: (credentials: LoginRequest) =>
    api.post<TokenResponseWithCsrf>('/api/auth/login', credentials),

  // 用户注册
  register: (data: RegisterRequest) =>
    api.post<TokenResponseWithCsrf>('/api/auth/register', data),

  // 获取当前用户信息
  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/api/auth/me');
    return response.data;
  },

  // 登出
  logout: async () => {
    await api.post('/api/auth/logout');
    clearStoredToken();
    clearAuthToken();
    clearCsrfToken();
  },
};

// 项目相关 API
export const projectApi = {
  // 获取项目列表
  list: async (params?: {
    status?: string;
    sort_by?: string;
    sort_order?: string;
    skip?: number;
    limit?: number;
  }): Promise<ProjectSummary[]> => {
    const response = await api.get<ProjectSummary[]>('/api/projects', { params });
    return response.data;
  },

  // 获取项目详情
  get: async (projectId: string): Promise<Project> => {
    const response = await api.get<Project>(`/api/projects/${projectId}`);
    return response.data;
  },

  // 创建项目
  create: async (data: ProjectCreate): Promise<Project> => {
    const response = await api.post<Project>('/api/projects', data);
    return response.data;
  },

  // 更新项目
  update: async (projectId: string, data: Partial<ProjectCreate & { status: string }>): Promise<Project> => {
    const response = await api.put<Project>(`/api/projects/${projectId}`, data);
    return response.data;
  },

  // 删除项目
  delete: async (projectId: string): Promise<void> => {
    await api.delete(`/api/projects/${projectId}`);
  },

  // 获取项目进度
  getProgress: async (projectId: string): Promise<ProjectProgress> => {
    const response = await api.get<ProjectProgress>(`/api/projects/${projectId}/progress`);
    return response.data;
  },

  // 获取项目成员列表
  getMembers: async (projectId: string): Promise<ProjectMember[]> => {
    const response = await api.get<ProjectMember[]>(`/api/projects/${projectId}/members`);
    return response.data;
  },
};

export interface ConfigData {
  model_name: string;
}

export interface FileUploadResponse {
  success: boolean;
  message: string;
  file_content?: string;
  old_outline?: string;
}

export interface AnalysisRequest {
  file_content: string;
  analysis_type: 'overview' | 'requirements';
  model_name?: string;
  provider_config_id?: string;
}

export interface OutlineRequest {
  overview: string;
  requirements: string;
  uploaded_expand?: boolean;
  old_outline?: string;
  old_document?: string;
  model_name?: string;
  provider_config_id?: string;
}

export interface OutlineItem {
  id: string;
  title: string;
  description?: string;
  content?: string;
  status?: string;
  children?: OutlineItem[];
  rating_item?: string;
  chapter_role?: string;
  avoid_overlap?: string;
}

export interface ContentGenerationRequest {
  outline: { outline: OutlineItem[] };
  project_overview: string;
}

export interface ChapterContentRequest {
  chapter: OutlineItem;
  parent_chapters?: OutlineItem[];
  sibling_chapters?: OutlineItem[];
  project_overview: string;
  model_name?: string;
  provider_config_id?: string;
}

export interface ProviderModelsOption {
  config_id: string;
  provider: string;
  models: string[];
  default_model: string;
  is_default: boolean;
}

export interface ProviderModelsResponse {
  models: string[];
  providers: ProviderModelsOption[];
  default_provider_config_id?: string | null;
  success: boolean;
  message: string;
}

// 配置相关API
export const configApi = {
  // 获取可用模型（从数据库读取配置，无需传参）
  getModels: () =>
    api.post<ProviderModelsResponse>('/api/config/models'),
};

// 文档相关API
export const documentApi = {
  // 上传文件
  uploadFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<FileUploadResponse>('/api/document/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },


  // 流式分析文档
  analyzeDocumentStream: (data: AnalysisRequest) => {
    return api.post('/api/document/analyze-stream', data, {
      responseType: 'stream',
    });
  },

  // 上传文件到项目
  uploadToProject: (projectId: string, file: File) => {
    const formData = new FormData();
    formData.append('project_id', projectId);
    formData.append('file', file);
    return api.post('/api/document/upload-to-project', formData);
  },

  // 流式分析项目文档（保存到数据库）
  analyzeProjectStream: (
    data: {
      project_id: string;
      analysis_type: 'overview' | 'requirements';
      model_name?: string;
      provider_config_id?: string;
    }
  ) => {
    return api.post('/api/document/analyze-project-stream', data, {
      responseType: 'stream',
    });
  },

  // 保存项目分析结果（用于下一步前的备份保存）
  saveProjectAnalysis: (projectId: string, data: { project_overview?: string; tech_requirements?: string }) => {
    return api.post(`/api/document/save-analysis/${projectId}`, data);
  },

  // 导出Word文档
  exportWord: (data: { project_name: string; project_overview?: string; project_id?: string; outline: OutlineItem[] }) => {
    return api.post('/api/document/export-word', data, {
      responseType: 'blob',
    });
  },
};

export const materialApi = {
  list: async (params?: { category?: string; expired?: boolean; keyword?: string }): Promise<MaterialAsset[]> => {
    try {
      const response = await api.get<MaterialAsset[]>('/api/materials', { params });
      return response.data;
    } catch (error) { handleApiError(error, '获取素材列表失败'); }
  },

  upload: async (formData: FormData): Promise<MaterialAsset> => {
    try {
      const response = await api.post<MaterialAsset>('/api/materials/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    } catch (error) { handleApiError(error, '素材上传失败'); }
  },

  analyzeRequirements: async (projectId: string): Promise<MaterialRequirement[]> => {
    try {
      const response = await api.post<MaterialRequirement[]>(`/api/projects/${projectId}/material-requirements/analyze`);
      return response.data;
    } catch (error) { handleApiError(error, '分析素材需求失败'); }
  },

  listRequirements: async (projectId: string): Promise<MaterialRequirement[]> => {
    try {
      const response = await api.get<MaterialRequirement[]>(`/api/projects/${projectId}/material-requirements`);
      return response.data;
    } catch (error) { handleApiError(error, '获取素材需求列表失败'); }
  },

  updateRequirement: async (projectId: string, requirementId: string, payload: Partial<MaterialRequirement>): Promise<MaterialRequirement> => {
    try {
      const response = await api.put<MaterialRequirement>(`/api/projects/${projectId}/material-requirements/${requirementId}`, payload);
      return response.data;
    } catch (error) { handleApiError(error, '更新素材需求失败'); }
  },

  matchRequirement: async (projectId: string, requirementId: string): Promise<MaterialMatchCandidate[]> => {
    try {
      const response = await api.post<MaterialMatchCandidate[]>(`/api/projects/${projectId}/material-requirements/${requirementId}/match`);
      return response.data;
    } catch (error) { handleApiError(error, '匹配素材失败'); }
  },

  confirmMatch: async (projectId: string, requirementId: string, materialAssetId: string): Promise<MaterialRequirement> => {
    try {
      const response = await api.post<MaterialRequirement>(`/api/projects/${projectId}/material-requirements/${requirementId}/confirm-match`, {
        material_asset_id: materialAssetId,
      });
      return response.data;
    } catch (error) { handleApiError(error, '确认素材匹配失败'); }
  },

  update: async (id: string, payload: { name?: string; category?: string; description?: string; tags?: string[] | string; review_status?: string; valid_from?: string; valid_until?: string }): Promise<MaterialAsset> => {
    try {
      const response = await api.put<MaterialAsset>(`/api/materials/${id}`, payload);
      return response.data;
    } catch (error) { handleApiError(error, '更新素材失败'); }
  },

  delete: async (id: string): Promise<void> => {
    try {
      await api.delete(`/api/materials/${id}`);
    } catch (error) { handleApiError(error, '删除素材失败'); }
  },

  listBindings: async (projectId: string, chapterId: string): Promise<ChapterMaterialBinding[]> => {
    try {
      const response = await api.get<ChapterMaterialBinding[]>(`/api/projects/${projectId}/chapters/${chapterId}/material-bindings`);
      return response.data;
    } catch (error) { handleApiError(error, '获取素材绑定列表失败'); }
  },

  createBinding: async (
    projectId: string,
    chapterId: string,
    payload: {
      material_requirement_id?: string | null;
      material_asset_id: string;
      anchor_type?: string;
      anchor_value?: string | null;
      display_mode?: string;
      caption?: string | null;
      sort_index?: number;
    }
  ): Promise<ChapterMaterialBinding> => {
    try {
      const response = await api.post<ChapterMaterialBinding>(`/api/projects/${projectId}/chapters/${chapterId}/material-bindings`, payload);
      return response.data;
    } catch (error) { handleApiError(error, '创建素材绑定失败'); }
  },
};

// 目录相关API
export const outlineApi = {
  // 生成目录
  generateOutline: (data: OutlineRequest) =>
    api.post('/api/outline/generate', data),

  // 流式生成目录
  generateOutlineStream: (data: OutlineRequest) => {
    return api.post('/api/outline/generate-stream', data, {
      responseType: 'stream',
    });
  },

  // 流式生成项目目录（保存到数据库）
  generateProjectOutlineStream: (data: { project_id: string; model_name?: string; provider_config_id?: string }) => {
    return api.post('/api/outline/generate-project-stream', data, {
      responseType: 'stream',
    });
  },

  // 流式生成项目一级目录
  generateProjectOutlineL1Stream: (data: { project_id: string; model_name?: string; provider_config_id?: string }) => {
    return api.post('/api/outline/generate-project-l1-stream', data, {
      responseType: 'stream',
    });
  },

  // 流式生成项目二三级目录
  generateProjectOutlineL2L3Stream: (
    data: { project_id: string; model_name?: string; provider_config_id?: string; outline_data?: { outline: OutlineItem[] } }
  ) => {
    return api.post('/api/outline/generate-project-l2l3-stream', data, {
      responseType: 'stream',
    });
  },

  getProjectChapters: async (projectId: string): Promise<ProjectChapterListResponse> => {
    const response = await api.get<ProjectChapterListResponse>(`/api/outline/project-chapters/${projectId}`);
    return response.data;
  },

};

// 方案扩写相关API
export const expandApi = {
  // 上传扩写文件
  uploadExpandFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/api/expand/upload', formData);
  },
};

// 内容相关API
export const contentApi = {
  // 生成单章节内容
  generateChapterContent: (data: ChapterContentRequest) =>
    api.post('/api/content/generate-chapter', data),

  // 流式生成单章节内容
  generateChapterContentStream: (data: ChapterContentRequest) => {
    return api.post('/api/content/generate-chapter-stream', data, {
      responseType: 'stream',
    });
  },
};

// 版本历史相关API
export const versionApi = {
  // 获取版本列表
  list: async (projectId: string, params?: {
    chapter_id?: string;
    change_type?: string;
    skip?: number;
    limit?: number;
  }): Promise<VersionList> => {
    const response = await api.get<VersionList>(`/api/projects/${projectId}/versions`, { params });
    return response.data;
  },

  // 获取版本详情
  get: async (projectId: string, versionId: string): Promise<VersionResponse> => {
    const response = await api.get<VersionResponse>(`/api/projects/${projectId}/versions/${versionId}`);
    return response.data;
  },

  // 对比两个版本
  diff: async (projectId: string, v1: string, v2: string): Promise<VersionDiffResponse> => {
    const response = await api.get<VersionDiffResponse>(`/api/projects/${projectId}/versions/diff`, {
      params: { v1, v2 },
    });
    return response.data;
  },

  // 回滚到指定版本
  rollback: async (projectId: string, versionId: string, createSnapshot = true): Promise<VersionRollbackResponse> => {
    const response = await api.post<VersionRollbackResponse>(
      `/api/projects/${projectId}/versions/${versionId}/rollback`,
      null,
      { params: { create_snapshot: createSnapshot } }
    );
    return response.data;
  },

  // 手动创建快照
  createSnapshot: async (projectId: string, changeSummary?: string): Promise<VersionResponse> => {
    const response = await api.post<VersionResponse>(
      `/api/projects/${projectId}/versions`,
      null,
      { params: { change_summary: changeSummary } }
    );
    return response.data;
  },
};

// 章节相关 API
export const chapterApi = {
  // 获取章节详情
  get: async (chapterId: string): Promise<ChapterContentResponse> => {
    const response = await api.get<ChapterContentResponse>(`/api/chapters/${chapterId}`);
    return response.data;
  },

  // 锁定章节
  lock: async (chapterId: string): Promise<LockResponse> => {
    const response = await api.post<LockResponse>(`/api/chapters/${chapterId}/lock`);
    return response.data;
  },

  // 解锁章节
  unlock: async (chapterId: string): Promise<LockResponse> => {
    const response = await api.post<LockResponse>(`/api/chapters/${chapterId}/unlock`);
    return response.data;
  },

  // 更新章节内容
  updateContent: async (chapterId: string, content: string, changeSummary?: string): Promise<ChapterContentResponse> => {
    const response = await api.put<ChapterContentResponse>(`/api/chapters/${chapterId}/content`, {
      content,
      change_summary: changeSummary,
    });
    return response.data;
  },

  // 更新章节状态
  updateStatus: async (chapterId: string, status: ChapterStatus): Promise<StatusUpdateResponse> => {
    const response = await api.put<StatusUpdateResponse>(`/api/chapters/${chapterId}/status`, {
      status,
    });
    return response.data;
  },
};

// 评论批注相关 API
export const commentApi = {
  // 获取章节批注列表
  list: async (chapterId: string, includeResolved = false): Promise<CommentListResponse> => {
    const response = await api.get<CommentListResponse>(`/api/chapters/${chapterId}/comments`, {
      params: { include_resolved: includeResolved },
    });
    return response.data;
  },

  // 创建批注
  create: async (chapterId: string, data: CommentCreateRequest): Promise<Comment> => {
    const response = await api.post<Comment>(`/api/chapters/${chapterId}/comments`, data);
    return response.data;
  },

  // 标记批注为已解决
  resolve: async (commentId: string): Promise<Comment> => {
    const response = await api.put<Comment>(`/api/comments/${commentId}/resolve`);
    return response.data;
  },

  // 删除批注
  delete: async (commentId: string): Promise<void> => {
    await api.delete(`/api/comments/${commentId}`);
  },
};

// 校对相关 API
export const proofreadApi = {
  // 触发章节校对（流式返回）
  proofreadChapter: (chapterId: string) => {
    return api.post(`/api/chapters/${chapterId}/proofread`, undefined, {
      responseType: 'stream',
    });
  },
};

// 一致性检查相关 API
export const consistencyApi = {
  // 检查项目跨章节一致性
  checkConsistency: async (
    projectId: string,
    chapterSummaries?: { chapter_number: string; title: string; summary: string; chapter_id?: string }[]
  ): Promise<ConsistencyCheckResponse> => {
    // 只有当 chapterSummaries 存在且长度>=2 时才发送请求体，否则不发送
    if (chapterSummaries && chapterSummaries.length >= 2) {
      const response = await api.post<ConsistencyCheckResponse>(
        `/api/projects/${projectId}/consistency-check`,
        { chapter_summaries: chapterSummaries }
      );
      return response.data;
    } else {
      // 不发送请求体，让后端从数据库读取
      const response = await api.post<ConsistencyCheckResponse>(
        `/api/projects/${projectId}/consistency-check`
      );
      return response.data;
    }
  },

  // 使用 LLM 重写章节
  rewriteChapter: async (
    projectId: string,
    chapterTitle: string,
    chapterContent: string,
    suggestions: string[]
  ): Promise<{ rewritten_content: string }> => {
    const response = await api.post<{ rewritten_content: string }>(
      `/api/projects/${projectId}/chapters/rewrite`,
      {
        chapter_title: chapterTitle,
        chapter_content: chapterContent,
        suggestions: suggestions,
      }
    );
    return response.data;
  },

  generateRatingChecklist: async (projectId: string): Promise<RatingChecklistResponse> => {
    const response = await api.post<RatingChecklistResponse>(
      `/api/projects/${projectId}/rating-response-checklist`
    );
    return response.data;
  },

  reverseEnhanceChapter: async (
    projectId: string,
    chapterId: string
  ): Promise<ChapterReverseEnhanceResponse> => {
    const response = await api.post<ChapterReverseEnhanceResponse>(
      `/api/projects/${projectId}/chapters/${chapterId}/reverse-enhance`
    );
    return response.data;
  },

  generateClauseResponse: async (
    projectId: string,
    data: ClauseResponseRequest
  ): Promise<ClauseResponseResult> => {
    const response = await api.post<ClauseResponseResult>(
      `/api/projects/${projectId}/clause-response`,
      data
    );
    return response.data;
  },
};

// 后台管理相关 API
export const adminApi = {
  // ==================== 用户管理 ====================

  // 获取用户列表
  listUsers: async (params?: {
    username?: string;
    email?: string;
    role?: string;
    is_active?: boolean;
    page?: number;
    page_size?: number;
  }): Promise<AdminUserListResponse> => {
    const response = await api.get<AdminUserListResponse>('/api/admin/users', { params });
    return response.data;
  },

  // 创建用户
  createUser: async (data: AdminUserCreate): Promise<AdminUser> => {
    const response = await api.post<AdminUser>('/api/admin/users', data);
    return response.data;
  },

  // 更新用户
  updateUser: async (userId: string, data: AdminUserUpdate): Promise<AdminUser> => {
    const response = await api.put<AdminUser>(`/api/admin/users/${userId}`, data);
    return response.data;
  },

  // 重置用户密码
  resetPassword: async (userId: string, data: ResetPasswordRequest): Promise<AdminUser> => {
    const response = await api.post<AdminUser>(`/api/admin/users/${userId}/reset-password`, data);
    return response.data;
  },

  // ==================== API Key 管理 ====================

  // 获取 API Key 列表
  listApiKeys: async (params?: { skip?: number; limit?: number }): Promise<ApiKeyConfigListResponse> => {
    const response = await api.get<ApiKeyConfigListResponse>('/api/admin/api-keys', { params });
    return response.data;
  },

  // 创建 API Key
  createApiKey: async (data: ApiKeyConfigCreate): Promise<ApiKeyConfig> => {
    const response = await api.post<ApiKeyConfig>('/api/admin/api-keys', data);
    return response.data;
  },

  // 更新 API Key
  updateApiKey: async (configId: string, data: ApiKeyConfigUpdate): Promise<ApiKeyConfig> => {
    const response = await api.put<ApiKeyConfig>(`/api/admin/api-keys/${configId}`, data);
    return response.data;
  },

  // 删除 API Key
  deleteApiKey: async (configId: string): Promise<void> => {
    await api.delete(`/api/admin/api-keys/${configId}`);
  },

  // 设置默认 API Key
  setDefaultApiKey: async (configId: string): Promise<ApiKeyConfig> => {
    const response = await api.put<ApiKeyConfig>(`/api/admin/api-keys/${configId}/default`);
    return response.data;
  },

  // ==================== 操作日志 ====================

  // 获取操作日志列表
  listLogs: async (params?: OperationLogQuery): Promise<OperationLogListResponse> => {
    const response = await api.get<OperationLogListResponse>('/api/admin/logs', { params });
    return response.data;
  },

  // ==================== 统计 ====================

  // 获取使用统计
  getStats: async (): Promise<UsageStats> => {
    const response = await api.get<UsageStats>('/api/admin/stats');
    return response.data;
  },
};

// ==================== 提示词配置 API ====================

export const promptApi = {
  // ==================== 管理员全局提示词 ====================

  // 获取所有提示词配置
  listPrompts: async (params?: { category?: string }): Promise<PromptListResponse> => {
    const response = await api.get<PromptListResponse>('/api/admin/prompts', { params });
    return response.data;
  },

  // 获取单个提示词配置
  getPrompt: async (sceneKey: string): Promise<PromptResponse> => {
    const response = await api.get<PromptResponse>(`/api/admin/prompts/${sceneKey}`);
    return response.data;
  },

  // 更新提示词配置
  updatePrompt: async (sceneKey: string, data: PromptUpdate): Promise<PromptResponse> => {
    const response = await api.put<PromptResponse>(`/api/admin/prompts/${sceneKey}`, data);
    return response.data;
  },

  // 获取提示词版本历史
  listPromptVersions: async (sceneKey: string, params?: { limit?: number }): Promise<PromptVersionListResponse> => {
    const response = await api.get<PromptVersionListResponse>(`/api/admin/prompts/${sceneKey}/versions`, { params });
    return response.data;
  },

  // 回滚提示词到指定版本
  rollbackPrompt: async (sceneKey: string, data: PromptRollbackRequest): Promise<PromptResponse> => {
    const response = await api.post<PromptResponse>(`/api/admin/prompts/${sceneKey}/rollback`, data);
    return response.data;
  },

  // 重置提示词为内置默认值
  resetPrompt: async (sceneKey: string): Promise<PromptResponse> => {
    const response = await api.post<PromptResponse>(`/api/admin/prompts/${sceneKey}/reset`);
    return response.data;
  },

  // ==================== 项目级提示词 ====================

  // 获取项目的所有提示词配置
  listProjectPrompts: async (projectId: string, params?: { category?: string }): Promise<ProjectPromptConfigListResponse> => {
    const response = await api.get<ProjectPromptConfigListResponse>(`/api/projects/${projectId}/prompts`, { params });
    return response.data;
  },

  // 获取项目中特定场景的提示词配置
  getProjectPrompt: async (projectId: string, sceneKey: string): Promise<ProjectPromptConfig> => {
    const response = await api.get<ProjectPromptConfig>(`/api/projects/${projectId}/prompts/${sceneKey}`);
    return response.data;
  },

  // 设置项目级提示词覆盖
  setProjectPrompt: async (projectId: string, sceneKey: string, data: ProjectPromptOverride): Promise<ProjectPromptConfig> => {
    const response = await api.put<ProjectPromptConfig>(`/api/projects/${projectId}/prompts/${sceneKey}`, data);
    return response.data;
  },

  // 删除项目级提示词覆盖
  deleteProjectPrompt: async (projectId: string, sceneKey: string): Promise<ProjectPromptConfig> => {
    const response = await api.delete<ProjectPromptConfig>(`/api/projects/${projectId}/prompts/${sceneKey}`);
    return response.data;
  },
};

// ==================== 请求日志 API ====================

export const requestLogApi = {
  // 获取请求日志列表
  list: async (params?: RequestLogQuery): Promise<RequestLogListResponse> => {
    const response = await api.get<RequestLogListResponse>('/api/request-logs', { params });
    return response.data;
  },

  // 获取请求日志详情
  get: async (logId: string): Promise<RequestLog> => {
    const response = await api.get<RequestLog>(`/api/request-logs/${logId}`);
    return response.data;
  },

  // 获取请求统计
  getStats: async (startTime?: string, endTime?: string): Promise<RequestStats> => {
    const response = await api.get<RequestStats>('/api/request-logs/stats/summary', {
      params: { start_time: startTime, end_time: endTime },
    });
    return response.data;
  },
};

// ==================== 标书审查 API ====================

export const reviewApi = {
  // 上传投标文件
  uploadBidFile: async (
    projectId: string,
    file: File,
  ): Promise<BidFileUploadResponse> => {
    const formData = new FormData();
    formData.append('project_id', projectId);
    formData.append('file', file);
    const response = await api.post('/api/review/upload-bid', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 执行审查（返回 fetch Response 用于 SSE 流式处理）
  executeReview: async (
    request: ReviewExecuteRequest,
    token?: string,
  ): Promise<Response> => {
    const authToken = token || getStoredToken();
    const csrfToken = getCsrfToken() || getCsrfTokenFromCookie();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
    const response = await fetch(`${API_BASE_URL}/api/review/execute`, {
      method: 'POST',
      headers,
      body: JSON.stringify(request),
      credentials: 'include',
    });
    return response;
  },

  // 获取审查结果
  getResult: async (taskId: string): Promise<ReviewResultResponse> => {
    const response = await api.get(`/api/review/result/${taskId}`);
    return response.data;
  },

  // 获取审查历史
  getHistory: async (projectId: string): Promise<ReviewHistoryResponse> => {
    const response = await api.get(`/api/review/history/${projectId}`);
    return response.data;
  },

  // 导出带批注的 Word
  exportWord: async (
    request: ReviewExportRequest,
    token?: string,
  ): Promise<Blob> => {
    const authToken = token || getStoredToken();
    const csrfToken = getCsrfToken() || getCsrfTokenFromCookie();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
    const response = await fetch(`${API_BASE_URL}/api/review/export-word`, {
      method: 'POST',
      headers,
      body: JSON.stringify(request),
      credentials: 'include',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || '导出失败');
    }
    return response.blob();
  },
};

export default api;
