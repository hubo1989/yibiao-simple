/**
 * 后台管理页面
 * 仅管理员可见
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { adminApi } from '../services/api';
import type {
  AdminUser,
  AdminUserCreate,
  AdminUserUpdate,
  ApiKeyConfig,
  ApiKeyConfigCreate,
  OperationLogSummary,
  OperationLogQuery,
  UsageStats,
  ActionType,
  ACTION_TYPE_LABELS,
} from '../types/admin';
import type { UserRole } from '../types/auth';

type TabType = 'stats' | 'users' | 'keys' | 'logs';

const ROLE_LABELS: Record<UserRole, string> = {
  admin: '管理员',
  editor: '编辑',
  reviewer: '审核员',
};

const Admin: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('stats');

  // 统计数据
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // 用户管理
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersPage, setUsersPage] = useState(1);
  const [usersLoading, setUsersLoading] = useState(false);
  const [showUserModal, setShowUserModal] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [userForm, setUserForm] = useState<AdminUserCreate>({
    username: '',
    email: '',
    password: '',
    role: 'editor',
    is_active: true,
  });
  const [showResetPassword, setShowResetPassword] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [saving, setSaving] = useState(false);

  // API Key 管理
  const [apiKeys, setApiKeys] = useState<ApiKeyConfig[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [keyForm, setKeyForm] = useState<ApiKeyConfigCreate>({
    provider: '',
    api_key: '',
    base_url: '',
    model_name: 'gpt-3.5-turbo',
    is_default: false,
  });

  // 操作日志
  const [logs, setLogs] = useState<OperationLogSummary[]>([]);
  const [logsTotal, setLogsTotal] = useState(0);
  const [logsPage, setLogsPage] = useState(1);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logFilter, setLogFilter] = useState<OperationLogQuery>({});

  // 加载统计数据
  const loadStats = useCallback(async () => {
    try {
      setStatsLoading(true);
      const data = await adminApi.getStats();
      setStats(data);
    } catch (err) {
      console.error('加载统计失败:', err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // 加载用户列表
  const loadUsers = useCallback(async () => {
    try {
      setUsersLoading(true);
      const data = await adminApi.listUsers({ page: usersPage, page_size: 10 });
      setUsers(data.items);
      setUsersTotal(data.total);
    } catch (err) {
      console.error('加载用户列表失败:', err);
    } finally {
      setUsersLoading(false);
    }
  }, [usersPage]);

  // 加载 API Key 列表
  const loadApiKeys = useCallback(async () => {
    try {
      setApiKeysLoading(true);
      const data = await adminApi.listApiKeys();
      setApiKeys(data.items);
    } catch (err) {
      console.error('加载 API Key 列表失败:', err);
    } finally {
      setApiKeysLoading(false);
    }
  }, []);

  // 加载操作日志
  const loadLogs = useCallback(async () => {
    try {
      setLogsLoading(true);
      const data = await adminApi.listLogs({ ...logFilter, page: logsPage, page_size: 20 });
      setLogs(data.items);
      setLogsTotal(data.total);
    } catch (err) {
      console.error('加载操作日志失败:', err);
    } finally {
      setLogsLoading(false);
    }
  }, [logsPage, logFilter]);

  // 初始加载
  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    if (activeTab === 'users') loadUsers();
  }, [activeTab, loadUsers]);

  useEffect(() => {
    if (activeTab === 'keys') loadApiKeys();
  }, [activeTab, loadApiKeys]);

  useEffect(() => {
    if (activeTab === 'logs') loadLogs();
  }, [activeTab, loadLogs]);

  // 用户操作
  const handleCreateUser = async () => {
    try {
      setSaving(true);
      await adminApi.createUser(userForm);
      setShowUserModal(false);
      resetUserForm();
      loadUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || '创建用户失败');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateUser = async () => {
    if (!editingUser) return;
    try {
      setSaving(true);
      const updateData: AdminUserUpdate = {};
      if (userForm.username !== editingUser.username) updateData.username = userForm.username;
      if (userForm.email !== editingUser.email) updateData.email = userForm.email;
      if (userForm.role !== editingUser.role) updateData.role = userForm.role;
      if (userForm.is_active !== editingUser.is_active) updateData.is_active = userForm.is_active;

      await adminApi.updateUser(editingUser.id, updateData);
      setShowUserModal(false);
      setEditingUser(null);
      resetUserForm();
      loadUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || '更新用户失败');
    } finally {
      setSaving(false);
    }
  };

  const handleResetPassword = async (userId: string) => {
    if (!newPassword || newPassword.length < 8) {
      alert('密码长度至少 8 位');
      return;
    }
    try {
      setSaving(true);
      await adminApi.resetPassword(userId, { new_password: newPassword });
      setShowResetPassword(null);
      setNewPassword('');
    } catch (err: any) {
      alert(err.response?.data?.detail || '重置密码失败');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleUserStatus = async (u: AdminUser) => {
    if (u.id === user?.id) {
      alert('不能禁用自己的账户');
      return;
    }
    try {
      await adminApi.updateUser(u.id, { is_active: !u.is_active });
      loadUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || '操作失败');
    }
  };

  const resetUserForm = () => {
    setUserForm({
      username: '',
      email: '',
      password: '',
      role: 'editor',
      is_active: true,
    });
  };

  const openEditUser = (u: AdminUser) => {
    setEditingUser(u);
    setUserForm({
      username: u.username,
      email: u.email,
      password: '',
      role: u.role,
      is_active: u.is_active,
    });
    setShowUserModal(true);
  };

  // API Key 操作
  const handleCreateApiKey = async () => {
    try {
      setSaving(true);
      await adminApi.createApiKey(keyForm);
      setShowKeyModal(false);
      resetKeyForm();
      loadApiKeys();
    } catch (err: any) {
      alert(err.response?.data?.detail || '创建 API Key 失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteApiKey = async (id: string) => {
    if (!confirm('确定要删除这个 API Key 吗？')) return;
    try {
      await adminApi.deleteApiKey(id);
      loadApiKeys();
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败');
    }
  };

  const handleSetDefaultKey = async (id: string) => {
    try {
      await adminApi.setDefaultApiKey(id);
      loadApiKeys();
    } catch (err: any) {
      alert(err.response?.data?.detail || '设置失败');
    }
  };

  const resetKeyForm = () => {
    setKeyForm({
      provider: '',
      api_key: '',
      base_url: '',
      model_name: 'gpt-3.5-turbo',
      is_default: false,
    });
  };

  // 日志筛选
  const handleLogFilter = () => {
    setLogsPage(1);
    loadLogs();
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN');
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // 统计卡片组件
  const StatCard: React.FC<{ title: string; value: number | string; icon: React.ReactNode; color: string }> = ({
    title, value, icon, color
  }) => (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center">
        <div className={`p-3 rounded-full ${color}`}>
          {icon}
        </div>
        <div className="ml-4">
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航栏 */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => navigate('/')}
                className="text-gray-500 hover:text-gray-700"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
              </button>
              <h1 className="text-xl font-bold text-gray-900">后台管理</h1>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">{user?.username}</span>
              <button
                onClick={handleLogout}
                className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
              >
                退出登录
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Tab 导航 */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8">
            {[
              { key: 'stats', label: '统计面板' },
              { key: 'users', label: '用户管理' },
              { key: 'keys', label: '密钥管理' },
              { key: 'logs', label: '操作日志' },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as TabType)}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.key
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* 统计面板 */}
        {activeTab === 'stats' && (
          <div>
            {statsLoading ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : stats ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard
                  title="项目总数"
                  value={stats.total_projects}
                  color="bg-blue-100 text-blue-600"
                  icon={
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                  }
                />
                <StatCard
                  title="用户总数"
                  value={stats.total_users}
                  color="bg-green-100 text-green-600"
                  icon={
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                    </svg>
                  }
                />
                <StatCard
                  title="本月生成次数"
                  value={stats.monthly_generations}
                  color="bg-purple-100 text-purple-600"
                  icon={
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  }
                />
                <StatCard
                  title="Token 消耗估算"
                  value={stats.estimated_tokens.toLocaleString()}
                  color="bg-orange-100 text-orange-600"
                  icon={
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  }
                />
              </div>
            ) : (
              <p className="text-center text-gray-500 py-12">加载失败</p>
            )}

            {/* 快速信息 */}
            <div className="mt-8 bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">系统概览</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-gray-500">活跃用户</p>
                  <p className="text-xl font-semibold text-gray-900">{stats?.active_users ?? 0}</p>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-gray-500">平均 Token/次</p>
                  <p className="text-xl font-semibold text-gray-900">
                    {stats && stats.monthly_generations > 0
                      ? Math.round(stats.estimated_tokens / stats.monthly_generations)
                      : 0}
                  </p>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-gray-500">API Key 数量</p>
                  <p className="text-xl font-semibold text-gray-900">{apiKeys.length}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 用户管理 */}
        {activeTab === 'users' && (
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-medium text-gray-900">用户列表</h2>
              <button
                onClick={() => {
                  setEditingUser(null);
                  resetUserForm();
                  setShowUserModal(true);
                }}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                创建用户
              </button>
            </div>

            {usersLoading ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : (
              <>
                <div className="bg-white shadow overflow-hidden rounded-lg">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户名</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">邮箱</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">角色</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">创建时间</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {users.map((u) => (
                        <tr key={u.id}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{u.username}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{u.email}</td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              u.role === 'admin' ? 'bg-red-100 text-red-800' :
                              u.role === 'reviewer' ? 'bg-yellow-100 text-yellow-800' :
                              'bg-green-100 text-green-800'
                            }`}>
                              {ROLE_LABELS[u.role]}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              u.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                            }`}>
                              {u.is_active ? '启用' : '禁用'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatDate(u.created_at)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                            <button
                              onClick={() => openEditUser(u)}
                              className="text-blue-600 hover:text-blue-900"
                            >
                              编辑
                            </button>
                            <button
                              onClick={() => handleToggleUserStatus(u)}
                              disabled={u.id === user?.id}
                              className={`hover:underline disabled:opacity-50 ${
                                u.is_active ? 'text-red-600 hover:text-red-900' : 'text-green-600 hover:text-green-900'
                              }`}
                            >
                              {u.is_active ? '禁用' : '启用'}
                            </button>
                            <button
                              onClick={() => setShowResetPassword(u.id)}
                              className="text-yellow-600 hover:text-yellow-900"
                            >
                              重置密码
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* 分页 */}
                {usersTotal > 10 && (
                  <div className="mt-4 flex justify-center">
                    <nav className="flex items-center space-x-2">
                      <button
                        onClick={() => setUsersPage(p => Math.max(1, p - 1))}
                        disabled={usersPage === 1}
                        className="px-3 py-1 rounded border border-gray-300 text-sm disabled:opacity-50"
                      >
                        上一页
                      </button>
                      <span className="text-sm text-gray-600">
                        第 {usersPage} 页，共 {Math.ceil(usersTotal / 10)} 页
                      </span>
                      <button
                        onClick={() => setUsersPage(p => p + 1)}
                        disabled={usersPage >= Math.ceil(usersTotal / 10)}
                        className="px-3 py-1 rounded border border-gray-300 text-sm disabled:opacity-50"
                      >
                        下一页
                      </button>
                    </nav>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* 密钥管理 */}
        {activeTab === 'keys' && (
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-medium text-gray-900">API Key 列表</h2>
              <button
                onClick={() => {
                  resetKeyForm();
                  setShowKeyModal(true);
                }}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                新增 Key
              </button>
            </div>

            {apiKeysLoading ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : apiKeys.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-lg shadow">
                <p className="text-gray-500">暂无 API Key 配置</p>
              </div>
            ) : (
              <div className="bg-white shadow overflow-hidden rounded-lg">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">提供商</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">API Key</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">模型</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {apiKeys.map((key) => (
                      <tr key={key.id}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{key.provider}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">{key.api_key_masked}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{key.model_name}</td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {key.is_default ? (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                              默认
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                              普通
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                          {!key.is_default && (
                            <button
                              onClick={() => handleSetDefaultKey(key.id)}
                              className="text-blue-600 hover:text-blue-900"
                            >
                              设为默认
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteApiKey(key.id)}
                            className="text-red-600 hover:text-red-900"
                          >
                            删除
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* 操作日志 */}
        {activeTab === 'logs' && (
          <div>
            {/* 筛选栏 */}
            <div className="bg-white shadow rounded-lg p-4 mb-6">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">用户名</label>
                  <input
                    type="text"
                    value={logFilter.username || ''}
                    onChange={(e) => setLogFilter({ ...logFilter, username: e.target.value || undefined })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                    placeholder="搜索用户名"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">操作类型</label>
                  <select
                    value={logFilter.action || ''}
                    onChange={(e) => setLogFilter({ ...logFilter, action: e.target.value as ActionType || undefined })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="">全部</option>
                    <option value="login">登录</option>
                    <option value="logout">登出</option>
                    <option value="project_create">创建项目</option>
                    <option value="project_update">更新项目</option>
                    <option value="project_delete">删除项目</option>
                    <option value="chapter_update">更新章节</option>
                    <option value="ai_generate">AI 生成</option>
                    <option value="ai_proofread">AI 校对</option>
                    <option value="consistency_check">一致性检查</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">开始时间</label>
                  <input
                    type="datetime-local"
                    value={logFilter.start_time || ''}
                    onChange={(e) => setLogFilter({ ...logFilter, start_time: e.target.value || undefined })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">结束时间</label>
                  <input
                    type="datetime-local"
                    value={logFilter.end_time || ''}
                    onChange={(e) => setLogFilter({ ...logFilter, end_time: e.target.value || undefined })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                  />
                </div>
              </div>
              <div className="mt-4 flex justify-end">
                <button
                  onClick={handleLogFilter}
                  className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
                >
                  筛选
                </button>
              </div>
            </div>

            {logsLoading ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : (
              <>
                <div className="bg-white shadow overflow-hidden rounded-lg">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作类型</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">请求路径</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态码</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP 地址</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">耗时</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {logs.map((log) => (
                        <tr key={log.id}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatDate(log.created_at)}</td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              log.action.startsWith('ai_') || log.action === 'consistency_check'
                                ? 'bg-purple-100 text-purple-800'
                                : log.action.includes('delete')
                                  ? 'bg-red-100 text-red-800'
                                  : log.action.includes('create')
                                    ? 'bg-green-100 text-green-800'
                                    : 'bg-gray-100 text-gray-800'
                            }`}>
                              {log.action}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">
                            {log.method} {log.path}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`text-sm ${
                              log.status_code && log.status_code < 400 ? 'text-green-600' : 'text-red-600'
                            }`}>
                              {log.status_code || '-'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{log.ip_address || '-'}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {log.duration_ms ? `${log.duration_ms}ms` : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* 分页 */}
                {logsTotal > 20 && (
                  <div className="mt-4 flex justify-center">
                    <nav className="flex items-center space-x-2">
                      <button
                        onClick={() => setLogsPage(p => Math.max(1, p - 1))}
                        disabled={logsPage === 1}
                        className="px-3 py-1 rounded border border-gray-300 text-sm disabled:opacity-50"
                      >
                        上一页
                      </button>
                      <span className="text-sm text-gray-600">
                        第 {logsPage} 页，共 {Math.ceil(logsTotal / 20)} 页
                      </span>
                      <button
                        onClick={() => setLogsPage(p => p + 1)}
                        disabled={logsPage >= Math.ceil(logsTotal / 20)}
                        className="px-3 py-1 rounded border border-gray-300 text-sm disabled:opacity-50"
                      >
                        下一页
                      </button>
                    </nav>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>

      {/* 用户创建/编辑弹窗 */}
      {showUserModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-center justify-center p-4">
            <div className="fixed inset-0 bg-black bg-opacity-50" onClick={() => setShowUserModal(false)}></div>
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                {editingUser ? '编辑用户' : '创建用户'}
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                  <input
                    type="text"
                    value={userForm.username}
                    onChange={(e) => setUserForm({ ...userForm, username: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
                  <input
                    type="email"
                    value={userForm.email}
                    onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                {!editingUser && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">密码</label>
                    <input
                      type="password"
                      value={userForm.password}
                      onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                )}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">角色</label>
                  <select
                    value={userForm.role}
                    onChange={(e) => setUserForm({ ...userForm, role: e.target.value as UserRole })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  >
                    <option value="editor">编辑</option>
                    <option value="reviewer">审核员</option>
                    <option value="admin">管理员</option>
                  </select>
                </div>
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="isActive"
                    checked={userForm.is_active}
                    onChange={(e) => setUserForm({ ...userForm, is_active: e.target.checked })}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                  />
                  <label htmlFor="isActive" className="ml-2 text-sm text-gray-700">启用账户</label>
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  onClick={() => setShowUserModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  取消
                </button>
                <button
                  onClick={editingUser ? handleUpdateUser : handleCreateUser}
                  disabled={saving}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? '保存中...' : '保存'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 重置密码弹窗 */}
      {showResetPassword && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-center justify-center p-4">
            <div className="fixed inset-0 bg-black bg-opacity-50" onClick={() => setShowResetPassword(null)}></div>
            <div className="relative bg-white rounded-lg shadow-xl max-w-sm w-full p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">重置密码</h3>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">新密码</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="至少 8 位"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  onClick={() => {
                    setShowResetPassword(null);
                    setNewPassword('');
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  取消
                </button>
                <button
                  onClick={() => handleResetPassword(showResetPassword)}
                  disabled={saving || newPassword.length < 8}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? '重置中...' : '重置'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* API Key 创建弹窗 */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-center justify-center p-4">
            <div className="fixed inset-0 bg-black bg-opacity-50" onClick={() => setShowKeyModal(false)}></div>
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">新增 API Key</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">提供商</label>
                  <input
                    type="text"
                    value={keyForm.provider}
                    onChange={(e) => setKeyForm({ ...keyForm, provider: e.target.value })}
                    placeholder="如: OpenAI, Azure"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
                  <input
                    type="password"
                    value={keyForm.api_key}
                    onChange={(e) => setKeyForm({ ...keyForm, api_key: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Base URL (可选)</label>
                  <input
                    type="text"
                    value={keyForm.base_url || ''}
                    onChange={(e) => setKeyForm({ ...keyForm, base_url: e.target.value })}
                    placeholder="自定义 API 地址"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">默认模型</label>
                  <input
                    type="text"
                    value={keyForm.model_name || ''}
                    onChange={(e) => setKeyForm({ ...keyForm, model_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="isDefault"
                    checked={keyForm.is_default}
                    onChange={(e) => setKeyForm({ ...keyForm, is_default: e.target.checked })}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                  />
                  <label htmlFor="isDefault" className="ml-2 text-sm text-gray-700">设为默认</label>
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  onClick={() => setShowKeyModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  取消
                </button>
                <button
                  onClick={handleCreateApiKey}
                  disabled={saving || !keyForm.provider || !keyForm.api_key}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? '创建中...' : '创建'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Admin;
