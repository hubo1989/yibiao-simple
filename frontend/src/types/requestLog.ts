/**
 * 请求日志相关类型定义
 */

export interface RequestLog {
  id: string;
  user_id?: string;
  username?: string;
  method: string;
  path: string;
  query_params: Record<string, any>;
  request_headers: Record<string, any>;
  request_body?: any;
  status_code: number;
  response_body?: any;
  duration_ms: number;
  ip_address?: string;
  user_agent?: string;
  error_message?: string;
  created_at: string;
}

export interface RequestLogListResponse {
  items: RequestLog[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface RequestLogQuery {
  method?: string;
  path?: string;
  status_code?: number;
  user_id?: string;
  start_time?: string;
  end_time?: string;
  min_duration?: number;
  max_duration?: number;
  has_error?: boolean;
  is_llm_request?: boolean;
  page?: number;
  page_size?: number;
}

export interface RequestStats {
  total_requests: number;
  success_requests: number;
  client_errors: number;
  server_errors: number;
  success_rate: number;
  avg_duration_ms: number;
  slowest_requests: Array<{
    path: string;
    method: string;
    duration_ms: number;
    created_at: string;
  }>;
  popular_paths: Array<{
    path: string;
    count: number;
  }>;
}
