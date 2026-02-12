/**
 * API服务
 */
import axios, { AxiosError } from 'axios';
import type { User, LoginRequest, RegisterRequest, Token } from '../types/auth';
import type { ProjectSummary, Project, ProjectCreate, ProjectProgress, ProjectMember } from '../types/project';
import type {
  VersionSummary,
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
} from '../types/chapter';
import type { Comment, CommentListResponse, CommentCreateRequest } from '../types/comment';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

// Token 管理函数
export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setStoredTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearStoredTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
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

// 请求拦截器：自动附加 Authorization header
api.interceptors.request.use(
  (config) => {
    const token = getStoredToken();
    if (token && !config.headers['Authorization']) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as any;

    // 如果是 401 错误且不是刷新 token 请求，尝试刷新 token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = getStoredRefreshToken();
      if (refreshToken) {
        try {
          const response = await axios.post<Token>(`${API_BASE_URL}/api/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token, refresh_token } = response.data;
          setStoredTokens(access_token, refresh_token);
          setAuthToken(access_token);

          // 重试原始请求
          originalRequest.headers['Authorization'] = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch {
          // 刷新 token 失败，清除认证状态
          clearStoredTokens();
          clearAuthToken();
          // 跳转到登录页
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
        }
      }
    }

    console.error('API请求错误:', error);
    return Promise.reject(error);
  }
);

// 认证相关 API
export const authApi = {
  // 用户登录
  login: (credentials: LoginRequest) =>
    api.post<Token>('/api/auth/login', credentials),

  // 用户注册
  register: (data: RegisterRequest) =>
    api.post<Token>('/api/auth/register', data),

  // 获取当前用户信息
  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/api/auth/me');
    return response.data;
  },

  // 刷新令牌
  refresh: (refreshToken: string) =>
    api.post<Token>('/api/auth/refresh', { refresh_token: refreshToken }),
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
  api_key: string;
  base_url?: string;
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
}

export interface OutlineRequest {
  overview: string;
  requirements: string;
  uploaded_expand?: boolean;
  old_outline?: string;
  old_document?: string;
}

export interface ContentGenerationRequest {
  outline: { outline: any[] };
  project_overview: string;
}

export interface ChapterContentRequest {
  chapter: any;
  parent_chapters?: any[];
  sibling_chapters?: any[];
  project_overview: string;
}

// 配置相关API
export const configApi = {
  // 保存配置
  saveConfig: (config: ConfigData) =>
    api.post('/api/config/save', config),

  // 加载配置
  loadConfig: () =>
    api.get('/api/config/load'),

  // 获取可用模型
  getModels: (config: ConfigData) =>
    api.post('/api/config/models', config),
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
  analyzeDocumentStream: (data: AnalysisRequest) =>
    fetch(`${API_BASE_URL}/api/document/analyze-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),

  // 导出Word文档
  exportWord: (data: any) =>
    fetch(`${API_BASE_URL}/api/document/export-word`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),
};

// 目录相关API
export const outlineApi = {
  // 生成目录
  generateOutline: (data: OutlineRequest) =>
    api.post('/api/outline/generate', data),

  // 流式生成目录
  generateOutlineStream: (data: OutlineRequest) =>
    fetch(`${API_BASE_URL}/api/outline/generate-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),

};

// 内容相关API
export const contentApi = {
  // 生成单章节内容
  generateChapterContent: (data: ChapterContentRequest) =>
    api.post('/api/content/generate-chapter', data),

  // 流式生成单章节内容
  generateChapterContentStream: (data: ChapterContentRequest) =>
    fetch(`${API_BASE_URL}/api/content/generate-chapter-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }),
};

// 方案扩写相关API
export const expandApi = {
  // 上传方案扩写文件
  uploadExpandFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<FileUploadResponse>('/api/expand/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 300000, // 文件上传专用超时设置：5分钟
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

export default api;
