/**
 * 请求记录页面
 */
import React, { useState, useEffect, useCallback } from 'react';
import { requestLogApi } from '../services/api';
import type { RequestLog, RequestLogQuery, RequestStats } from '../types/requestLog';
import { formatDateTime } from '../utils/date';

const RequestLogs: React.FC = () => {
  const [logs, setLogs] = useState<RequestLog[]>([]);
  const [stats, setStats] = useState<RequestStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState<RequestLog | null>(null);
  
  // 过滤条件
  const [filters, setFilters] = useState<RequestLogQuery>({
    page: 1,
    page_size: 20,
  });
  
  // 分页信息
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  // 加载日志列表
  const loadLogs = useCallback(async () => {
    try {
      setLoading(true);
      const response = await requestLogApi.list(filters);
      setLogs(response.items);
      setTotal(response.total);
      setTotalPages(response.total_pages);
    } catch (err) {
      console.error('加载请求日志失败:', err);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // 加载统计数据
  const loadStats = useCallback(async () => {
    try {
      const statsData = await requestLogApi.getStats();
      setStats(statsData);
    } catch (err) {
      console.error('加载统计数据失败:', err);
    }
  }, []);

  useEffect(() => {
    loadLogs();
    loadStats();
  }, [loadLogs, loadStats]);

  // 格式化耗时
  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  // 获取状态码颜色
  const getStatusColor = (code: number) => {
    if (code >= 200 && code < 300) return 'text-green-600 bg-green-100';
    if (code >= 400 && code < 500) return 'text-yellow-600 bg-yellow-100';
    if (code >= 500) return 'text-red-600 bg-red-100';
    return 'text-gray-600 bg-gray-100';
  };

  // 获取方法颜色
  const getMethodColor = (method: string) => {
    switch (method.toUpperCase()) {
      case 'GET': return 'text-blue-600 bg-blue-100';
      case 'POST': return 'text-green-600 bg-green-100';
      case 'PUT': return 'text-yellow-600 bg-yellow-100';
      case 'DELETE': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">请求记录</h1>
          <p className="text-sm text-gray-500 mt-1">查看所有API请求的详细信息</p>
        </div>

        {/* 统计卡片 */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">总请求数</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total_requests}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">成功率</p>
              <p className="text-2xl font-bold text-green-600">{stats.success_rate.toFixed(1)}%</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">平均耗时</p>
              <p className="text-2xl font-bold text-gray-900">{formatDuration(stats.avg_duration_ms)}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">客户端错误</p>
              <p className="text-2xl font-bold text-yellow-600">{stats.client_errors}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">服务端错误</p>
              <p className="text-2xl font-bold text-red-600">{stats.server_errors}</p>
            </div>
          </div>
        )}

        {/* 过滤器 */}
        <div className="bg-white rounded-lg shadow mb-6 p-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">请求方法</label>
              <select
                value={filters.method || ''}
                onChange={(e) => setFilters({ ...filters, method: e.target.value || undefined, page: 1 })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">全部</option>
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="DELETE">DELETE</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">状态码</label>
              <select
                value={filters.status_code || ''}
                onChange={(e) => setFilters({ ...filters, status_code: e.target.value ? parseInt(e.target.value) : undefined, page: 1 })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">全部</option>
                <option value="200">2xx 成功</option>
                <option value="400">4xx 客户端错误</option>
                <option value="500">5xx 服务端错误</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">LLM 请求</label>
              <select
                value={filters.is_llm_request === undefined ? '' : filters.is_llm_request ? 'true' : 'false'}
                onChange={(e) => setFilters({
                  ...filters,
                  is_llm_request: e.target.value === '' ? undefined : e.target.value === 'true',
                  page: 1
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">全部</option>
                <option value="true">仅 LLM 请求</option>
                <option value="false">仅非 LLM 请求</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">错误过滤</label>
              <select
                value={filters.has_error === undefined ? '' : filters.has_error ? 'true' : 'false'}
                onChange={(e) => setFilters({
                  ...filters,
                  has_error: e.target.value === '' ? undefined : e.target.value === 'true',
                  page: 1
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">全部</option>
                <option value="true">仅错误</option>
                <option value="false">仅成功</option>
              </select>
            </div>
          </div>
        </div>

        {/* 日志列表 */}
        <div className="bg-white rounded-lg shadow">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              暂无请求记录
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">方法</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">路径</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态码</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">耗时</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {logs.map((log) => (
                      <tr key={log.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatDateTime(log.created_at)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 text-xs font-medium rounded ${getMethodColor(log.method)}`}>
                            {log.method}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate" title={log.path}>
                          {log.path}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 text-xs font-medium rounded ${getStatusColor(log.status_code)}`}>
                            {log.status_code}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatDuration(log.duration_ms)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {log.username || '-'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <button
                            onClick={() => setSelectedLog(log)}
                            className="text-blue-600 hover:text-blue-900"
                          >
                            查看详情
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 分页 */}
              <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
                <div className="flex-1 flex justify-between sm:hidden">
                  <button
                    onClick={() => setFilters({ ...filters, page: (filters.page || 1) - 1 })}
                    disabled={(filters.page || 1) <= 1}
                    className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    上一页
                  </button>
                  <button
                    onClick={() => setFilters({ ...filters, page: (filters.page || 1) + 1 })}
                    disabled={(filters.page || 1) >= totalPages}
                    className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    下一页
                  </button>
                </div>
                <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm text-gray-700">
                      显示第 <span className="font-medium">{((filters.page || 1) - 1) * (filters.page_size || 20) + 1}</span> 到{' '}
                      <span className="font-medium">{Math.min((filters.page || 1) * (filters.page_size || 20), total)}</span> 条，
                      共 <span className="font-medium">{total}</span> 条记录
                    </p>
                  </div>
                  <div>
                    <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                      <button
                        onClick={() => setFilters({ ...filters, page: (filters.page || 1) - 1 })}
                        disabled={(filters.page || 1) <= 1}
                        className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                      >
                        上一页
                      </button>
                      {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                        let pageNum: number;
                        if (totalPages <= 5) {
                          pageNum = i + 1;
                        } else {
                          const currentPage = filters.page || 1;
                          if (currentPage <= 3) {
                            pageNum = i + 1;
                          } else if (currentPage >= totalPages - 2) {
                            pageNum = totalPages - 4 + i;
                          } else {
                            pageNum = currentPage - 2 + i;
                          }
                        }
                        return (
                          <button
                            key={pageNum}
                            onClick={() => setFilters({ ...filters, page: pageNum })}
                            className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                              pageNum === (filters.page || 1)
                                ? 'z-10 bg-blue-50 border-blue-500 text-blue-600'
                                : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                            }`}
                          >
                            {pageNum}
                          </button>
                        );
                      })}
                      <button
                        onClick={() => setFilters({ ...filters, page: (filters.page || 1) + 1 })}
                        disabled={(filters.page || 1) >= totalPages}
                        className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                      >
                        下一页
                      </button>
                    </nav>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* 详情弹窗 */}
        {selectedLog && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                <h3 className="text-lg font-medium text-gray-900">请求详情</h3>
                <button
                  onClick={() => setSelectedLog(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-6 py-4">
                <>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <p className="text-sm font-medium text-gray-500">请求方法</p>
                    <p className="mt-1 text-sm text-gray-900">{selectedLog.method}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">状态码</p>
                    <p className="mt-1 text-sm text-gray-900">{selectedLog.status_code}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">请求路径</p>
                    <p className="mt-1 text-sm text-gray-900 break-all">{selectedLog.path}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">耗时</p>
                    <p className="mt-1 text-sm text-gray-900">{formatDuration(selectedLog.duration_ms)}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">用户</p>
                    <p className="mt-1 text-sm text-gray-900">{selectedLog.username || '未认证'}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">IP 地址</p>
                    <p className="mt-1 text-sm text-gray-900">{selectedLog.ip_address || '-'}</p>
                  </div>
                  <div className="col-span-2">
                    <p className="text-sm font-medium text-gray-500">时间</p>
                    <p className="mt-1 text-sm text-gray-900">{formatDateTime(selectedLog.created_at)}</p>
                  </div>
                </div>

                {Object.keys(selectedLog.query_params).length > 0 && (
                  <div className="mb-4">
                    <p className="text-sm font-medium text-gray-500 mb-2">查询参数</p>
                    <pre className="bg-gray-50 rounded p-3 text-xs overflow-x-auto">
                      {JSON.stringify(selectedLog.query_params, null, 2)}
                    </pre>
                  </div>
                )}

                {selectedLog.request_body && (
                  <div className="mb-4">
                    <p className="text-sm font-medium text-gray-500 mb-2">请求体</p>
                    <pre className="bg-gray-50 rounded p-3 text-xs overflow-x-auto max-h-60">
                      {JSON.stringify(selectedLog.request_body, null, 2)}
                    </pre>
                  </div>
                )}

                {selectedLog.response_body && (
                  <div className="mb-4">
                    <p className="text-sm font-medium text-gray-500 mb-2">响应体</p>
                    <pre className="bg-gray-50 rounded p-3 text-xs overflow-x-auto max-h-60">
                      {JSON.stringify(selectedLog.response_body, null, 2)}
                    </pre>
                  </div>
                )}

                {selectedLog.error_message && (
                  <div className="mb-4">
                    <p className="text-sm font-medium text-red-500 mb-2">错误信息</p>
                    <pre className="bg-red-50 rounded p-3 text-xs overflow-x-auto text-red-900">
                      {selectedLog.error_message}
                    </pre>
                  </div>
                )}
                </>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default RequestLogs;
