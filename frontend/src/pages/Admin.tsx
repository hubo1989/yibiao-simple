/**
 * 后台管理页面
 * 仅管理员可见
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { adminApi, requestLogApi } from '../services/api';
import type {
  AdminUser,
  AdminUserCreate,
  AdminUserUpdate,
  ApiKeyConfig,
  ApiKeyConfigCreate,
  ApiKeyConfigUpdate,
  ApiKeyModelConfig,
  OperationLogSummary,
  OperationLogQuery,
  UsageStats,
  ActionType,
} from '../types/admin';
import type { UserRole } from '../types/auth';
import type { PromptResponse, PromptCategory } from '../types/prompt';
import { promptApi } from '../services/api';
import PromptEditor from '../components/PromptEditor';
import { useLayoutHeader } from '../layouts/layoutHeader';

type TabType = 'stats' | 'users' | 'keys' | 'logs' | 'prompts' | 'requestLogs';

const ROLE_LABELS: Record<UserRole, string> = {
  admin: '管理员',
  editor: '编辑',
  reviewer: '审核员',
};

const DEFAULT_KEY_MODEL_ID = 'gpt-3.5-turbo';

const createEmptyModelConfig = (): ApiKeyModelConfig => ({
  model_id: '',
  use_for_generation: false,
  use_for_indexing: false,
});

const createDefaultModelConfig = (): ApiKeyModelConfig => ({
  model_id: DEFAULT_KEY_MODEL_ID,
  use_for_generation: true,
  use_for_indexing: true,
});

const normalizeKeyModelConfigs = (modelConfigs: ApiKeyModelConfig[]): ApiKeyModelConfig[] => {
  const seen = new Set<string>();
  const cleaned = modelConfigs.reduce<ApiKeyModelConfig[]>((accumulator, config) => {
    const modelId = config.model_id.trim();
    if (!modelId || seen.has(modelId)) {
      return accumulator;
    }
    seen.add(modelId);
    accumulator.push({ ...config, model_id: modelId });
    return accumulator;
  }, []);

  if (!cleaned.length) {
    return [];
  }

  let hasGenerationModel = false;
  let hasIndexModel = false;
  const normalized = cleaned.map((config) => {
    const nextConfig = { ...config };

    if (nextConfig.use_for_generation) {
      if (hasGenerationModel) {
        nextConfig.use_for_generation = false;
      } else {
        hasGenerationModel = true;
      }
    }

    if (nextConfig.use_for_indexing) {
      if (hasIndexModel) {
        nextConfig.use_for_indexing = false;
      } else {
        hasIndexModel = true;
      }
    }

    return nextConfig;
  });

  if (!hasGenerationModel) {
    normalized[0].use_for_generation = true;
  }
  if (!hasIndexModel) {
    const generationIndex = normalized.findIndex((config) => config.use_for_generation);
    normalized[generationIndex >= 0 ? generationIndex : 0].use_for_indexing = true;
  }

  return normalized;
};

const createEmptyKeyForm = (): ApiKeyConfigCreate => ({
  provider: '',
  api_key: '',
  base_url: '',
  model_name: DEFAULT_KEY_MODEL_ID,
  model_configs: [createDefaultModelConfig()],
  is_default: false,
});

const Admin: React.FC = () => {
  const { user } = useAuth();
  const { setLayoutHeader } = useLayoutHeader();
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
  const [editingKey, setEditingKey] = useState<ApiKeyConfig | null>(null);
  const [keyForm, setKeyForm] = useState<ApiKeyConfigCreate>(createEmptyKeyForm());

  // 操作日志
  const [logs, setLogs] = useState<OperationLogSummary[]>([]);
  const [logsTotal, setLogsTotal] = useState(0);
  const [logsPage, setLogsPage] = useState(1);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logFilter, setLogFilter] = useState<OperationLogQuery>({});

  // 提示词配置
  const [prompts, setPrompts] = useState<PromptResponse[]>([]);
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [promptCategoryFilter, setPromptCategoryFilter] = useState<PromptCategory | ''>('');
  const [expandedPrompt, setExpandedPrompt] = useState<string | null>(null);

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

  // 加载提示词配置
  const loadPrompts = useCallback(async () => {
    try {
      setPromptsLoading(true);
      const data = await promptApi.listPrompts({
        category: promptCategoryFilter || undefined,
      });
      setPrompts(data.items);
    } catch (err) {
      console.error('加载提示词配置失败:', err);
    } finally {
      setPromptsLoading(false);
    }
  }, [promptCategoryFilter]);

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

  useEffect(() => {
    if (activeTab === 'prompts') loadPrompts();
  }, [activeTab, loadPrompts]);

  useEffect(() => {
    const tabs: Array<{ key: TabType; label: string }> = [
      { key: 'stats', label: '统计面板' },
      { key: 'users', label: '用户管理' },
      { key: 'keys', label: '密钥管理' },
      { key: 'logs', label: '操作日志' },
      { key: 'requestLogs', label: '请求记录' },
      { key: 'prompts', label: '提示词配置' },
    ];

    setLayoutHeader({
      content: (
        <div className="flex min-w-0 items-center gap-4 py-2">
          <h1 className="shrink-0 text-[18px] font-semibold tracking-tight text-slate-900">系统设置</h1>
          <span className="h-5 w-px shrink-0 bg-slate-200" />
          <span className="truncate text-sm text-slate-500">
            统一维护用户、Provider、日志与提示词配置
          </span>
        </div>
      ),
      subContent: (
        <div className="flex items-center gap-2 overflow-x-auto py-3">
          {tabs.map((tab) => {
            const active = tab.key === activeTab;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={[
                  'whitespace-nowrap rounded-full border px-4 py-2 text-sm font-medium transition-colors',
                  active
                    ? 'border-sky-200 bg-sky-50 text-sky-700'
                    : 'border-transparent bg-transparent text-slate-500 hover:border-slate-200 hover:bg-slate-50 hover:text-slate-800',
                ].join(' ')}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      ),
    });

    return () => {
      setLayoutHeader(null);
    };
  }, [activeTab, setLayoutHeader]);

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
  const closeKeyModal = () => {
    setShowKeyModal(false);
    resetKeyForm();
  };

  const openCreateKeyModal = () => {
    setEditingKey(null);
    resetKeyForm();
    setShowKeyModal(true);
  };

  const openEditKeyModal = (key: ApiKeyConfig) => {
    setEditingKey(key);
    setKeyForm({
      provider: key.provider,
      api_key: '',
      base_url: key.base_url || '',
      model_name: key.generation_model_name || key.model_name,
      model_configs: key.model_configs.length
        ? key.model_configs.map((config) => ({ ...config }))
        : [
            {
              model_id: key.model_name,
              use_for_generation: true,
              use_for_indexing: true,
            },
          ],
      is_default: key.is_default,
    });
    setShowKeyModal(true);
  };

  const handleSaveApiKey = async () => {
    const normalizedModelConfigs = normalizeKeyModelConfigs(keyForm.model_configs);

    if (!keyForm.provider.trim()) {
      alert('请输入提供商名称');
      return;
    }
    if (!editingKey && !keyForm.api_key.trim()) {
      alert('请输入 API Key');
      return;
    }
    if (!normalizedModelConfigs.length) {
      alert('请至少配置一个模型 ID');
      return;
    }

    const modelName = normalizedModelConfigs.find((config) => config.use_for_generation)?.model_id
      || normalizedModelConfigs[0].model_id;

    try {
      setSaving(true);

      if (editingKey) {
        const payload: ApiKeyConfigUpdate = {
          provider: keyForm.provider.trim(),
          api_key: keyForm.api_key.trim() || undefined,
          base_url: keyForm.base_url?.trim() ?? '',
          model_name: modelName,
          model_configs: normalizedModelConfigs,
          is_default: !!keyForm.is_default,
        };
        await adminApi.updateApiKey(editingKey.id, payload);
      } else {
        await adminApi.createApiKey({
          provider: keyForm.provider.trim(),
          api_key: keyForm.api_key.trim(),
          base_url: keyForm.base_url?.trim() || undefined,
          model_name: modelName,
          model_configs: normalizedModelConfigs,
          is_default: !!keyForm.is_default,
        });
      }

      closeKeyModal();
      loadApiKeys();
    } catch (err: any) {
      alert(err.response?.data?.detail || (editingKey ? '更新 API Key 失败' : '创建 API Key 失败'));
    } finally {
      setSaving(false);
    }
  };

  const handleModelIdChange = (index: number, modelId: string) => {
    setKeyForm((previous) => ({
      ...previous,
      model_configs: previous.model_configs.map((config, currentIndex) => (
        currentIndex === index ? { ...config, model_id: modelId } : config
      )),
    }));
  };

  const handleModelUsageChange = (
    index: number,
    field: 'use_for_generation' | 'use_for_indexing',
    checked: boolean,
  ) => {
    setKeyForm((previous) => ({
      ...previous,
      model_configs: previous.model_configs.map((config, currentIndex) => {
        if (currentIndex === index) {
          return { ...config, [field]: checked };
        }
        if (checked) {
          return { ...config, [field]: false };
        }
        return config;
      }),
    }));
  };

  const handleAddModelConfig = () => {
    setKeyForm((previous) => ({
      ...previous,
      model_configs: [...previous.model_configs, createEmptyModelConfig()],
    }));
  };

  const handleRemoveModelConfig = (index: number) => {
    setKeyForm((previous) => {
      const nextModelConfigs = previous.model_configs.filter((_, currentIndex) => currentIndex !== index);
      return {
        ...previous,
        model_configs: nextModelConfigs.length ? nextModelConfigs : [createEmptyModelConfig()],
      };
    });
  };

  const handleDeleteApiKey = async (id: string) => {
    // eslint-disable-next-line no-restricted-globals
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
    setEditingKey(null);
    setKeyForm(createEmptyKeyForm());
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
    <>
      <div className="min-h-full bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
              <div>
                <h2 className="text-lg font-medium text-gray-900">API Key 列表</h2>
                <p className="text-sm text-gray-500 mt-1">单个提供商可配置多个模型，并分别指定生成模型与索引模型。</p>
              </div>
              <button
                onClick={openCreateKeyModal}
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
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">模型配置</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {apiKeys.map((key) => (
                      <tr key={key.id}>
                        <td className="px-6 py-4 align-top text-sm font-medium text-gray-900">{key.provider}</td>
                        <td className="px-6 py-4 align-top text-sm text-gray-500 font-mono">{key.api_key_masked}</td>
                        <td className="px-6 py-4 align-top text-sm text-gray-500">
                          <div className="space-y-2">
                            <div className="text-sm text-gray-900">
                              <span className="font-medium">生成：</span>
                              {key.generation_model_name}
                            </div>
                            <div className="text-sm text-gray-900">
                              <span className="font-medium">索引：</span>
                              {key.index_model_name}
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {key.model_configs.map((modelConfig) => (
                                <span
                                  key={`${key.id}-${modelConfig.model_id}`}
                                  className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-700"
                                >
                                  <span>{modelConfig.model_id}</span>
                                  {modelConfig.use_for_generation && <span className="text-blue-600">生成</span>}
                                  {modelConfig.use_for_indexing && <span className="text-emerald-600">索引</span>}
                                </span>
                              ))}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 align-top whitespace-nowrap">
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
                        <td className="px-6 py-4 align-top whitespace-nowrap text-sm">
                          <div className="flex items-center gap-3">
                            <button
                              onClick={() => openEditKeyModal(key)}
                              className="text-gray-700 hover:text-gray-900"
                            >
                              修改
                            </button>
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
                          </div>
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

        {/* 提示词配置 */}
        {activeTab === 'prompts' && (
          <div>
            <div className="mb-6 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <select
                  value={promptCategoryFilter}
                  onChange={(e) => setPromptCategoryFilter(e.target.value as PromptCategory | '')}
                  className="px-3 py-2 border border-gray-300 rounded-md text-sm"
                >
                  <option value="">全部类别</option>
                  <option value="analysis">解析类</option>
                  <option value="generation">生成类</option>
                  <option value="check">检查类</option>
                </select>
              </div>
              <div className="text-sm text-gray-500">
                共 {prompts.length} 个场景
              </div>
            </div>

            {promptsLoading ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : prompts.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                暂无提示词配置
              </div>
            ) : (
              <div className="space-y-4">
                {prompts.map((prompt) => (
                  <div key={prompt.scene_key}>
                    <button
                      onClick={() => setExpandedPrompt(expandedPrompt === prompt.scene_key ? null : prompt.scene_key)}
                      className="w-full flex items-center justify-between p-4 bg-white rounded-lg border border-gray-200 hover:border-gray-300 text-left"
                    >
                      <div className="flex items-center gap-4">
                        <div>
                          <h3 className="text-sm font-medium text-gray-900">{prompt.scene_name}</h3>
                          <p className="text-xs text-gray-500 mt-0.5">{prompt.scene_key}</p>
                        </div>
                        <span className={`px-2 py-0.5 text-xs rounded-full ${
                          prompt.category === 'analysis' ? 'bg-blue-100 text-blue-700' :
                          prompt.category === 'generation' ? 'bg-green-100 text-green-700' :
                          'bg-orange-100 text-orange-700'
                        }`}>
                          {prompt.category === 'analysis' ? '解析' : prompt.category === 'generation' ? '生成' : '检查'}
                        </span>
                        {prompt.is_customized && (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-purple-100 text-purple-700">
                            已自定义
                          </span>
                        )}
                      </div>
                      <svg
                        className={`w-5 h-5 text-gray-400 transition-transform ${expandedPrompt === prompt.scene_key ? 'rotate-180' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    {expandedPrompt === prompt.scene_key && (
                      <div className="mt-2">
                        <PromptEditor
                          sceneKey={prompt.scene_key}
                          sceneName={prompt.scene_name}
                          prompt={prompt.prompt}
                          availableVars={prompt.available_vars}
                          source={prompt.is_customized ? 'global' : 'builtin'}
                          hasGlobalOverride={prompt.is_customized}
                          currentVersion={prompt.version}
                          onSave={async (newPrompt) => {
                            try {
                              await promptApi.updatePrompt(prompt.scene_key, {
                                prompt: newPrompt,
                              });
                              loadPrompts();
                            } catch (err: any) {
                              alert(err.response?.data?.detail || '保存失败');
                            }
                          }}
                          onReset={async () => {
                            try {
                              await promptApi.resetPrompt(prompt.scene_key);
                              loadPrompts();
                            } catch (err: any) {
                              alert(err.response?.data?.detail || '重置失败');
                            }
                          }}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 请求记录 */}
        {activeTab === 'requestLogs' && <RequestLogsTab />}
      </div>
      </div>

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

      {/* API Key 创建/修改弹窗 */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-screen items-center justify-center p-4">
            <div className="fixed inset-0 bg-black bg-opacity-50" onClick={closeKeyModal}></div>
            <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{editingKey ? '修改 API Key' : '新增 API Key'}</h3>
              <p className="text-sm text-gray-500 mb-6">可为同一提供商维护多个模型 ID，并分别指定生成模型与索引模型。</p>
              <div className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                    <label className="block text-sm font-medium text-gray-700 mb-1">Base URL (可选)</label>
                    <input
                      type="text"
                      value={keyForm.base_url || ''}
                      onChange={(e) => setKeyForm({ ...keyForm, base_url: e.target.value })}
                      placeholder="自定义 API 地址"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
                  <input
                    type="password"
                    value={keyForm.api_key}
                    onChange={(e) => setKeyForm({ ...keyForm, api_key: e.target.value })}
                    placeholder={editingKey ? '留空表示保持当前密钥不变' : '请输入 API Key'}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">模型配置</label>
                      <p className="text-xs text-gray-500 mt-1">保存时会自动保证只有一个生成模型和一个索引模型；若未勾选，则默认取第一条模型。</p>
                    </div>
                    <button
                      type="button"
                      onClick={handleAddModelConfig}
                      className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50"
                    >
                      新增模型
                    </button>
                  </div>
                  <div className="space-y-3">
                    {keyForm.model_configs.map((modelConfig, index) => (
                      <div key={`model-config-${index}`} className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_110px_110px_72px] gap-3 items-center rounded-lg border border-gray-200 p-3">
                        <input
                          type="text"
                          value={modelConfig.model_id}
                          onChange={(e) => handleModelIdChange(index, e.target.value)}
                          placeholder="请输入模型 ID"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        />
                        <label className="flex items-center justify-center gap-2 text-sm text-gray-700">
                          <input
                            type="checkbox"
                            checked={modelConfig.use_for_generation}
                            onChange={(e) => handleModelUsageChange(index, 'use_for_generation', e.target.checked)}
                            className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                          />
                          生成
                        </label>
                        <label className="flex items-center justify-center gap-2 text-sm text-gray-700">
                          <input
                            type="checkbox"
                            checked={modelConfig.use_for_indexing}
                            onChange={(e) => handleModelUsageChange(index, 'use_for_indexing', e.target.checked)}
                            className="h-4 w-4 text-emerald-600 border-gray-300 rounded"
                          />
                          索引
                        </label>
                        <button
                          type="button"
                          onClick={() => handleRemoveModelConfig(index)}
                          className="text-sm text-red-600 hover:text-red-900"
                        >
                          删除
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="isDefault"
                    checked={!!keyForm.is_default}
                    onChange={(e) => setKeyForm({ ...keyForm, is_default: e.target.checked })}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                  />
                  <label htmlFor="isDefault" className="ml-2 text-sm text-gray-700">设为默认</label>
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  onClick={closeKeyModal}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  取消
                </button>
                <button
                  onClick={handleSaveApiKey}
                  disabled={saving || !keyForm.provider.trim() || (!editingKey && !keyForm.api_key.trim()) || !keyForm.model_configs.some((config) => config.model_id.trim())}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? (editingKey ? '保存中...' : '创建中...') : (editingKey ? '保存修改' : '创建')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

// 请求记录标签页组件
const RequestLogsTab: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState<any>(null);
  
  const [filters, setFilters] = useState<any>({
    page: 1,
    page_size: 20,
  });
  
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

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

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const getStatusColor = (code: number) => {
    if (code >= 200 && code < 300) return 'text-green-600 bg-green-100';
    if (code >= 400 && code < 500) return 'text-yellow-600 bg-yellow-100';
    if (code >= 500) return 'text-red-600 bg-red-100';
    return 'text-gray-600 bg-gray-100';
  };

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
    <div>
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
            <label className="block text-sm font-medium text-gray-700 mb-1">路径搜索</label>
            <input
              type="text"
              value={filters.path || ''}
              onChange={(e) => setFilters({ ...filters, path: e.target.value || undefined, page: 1 })}
              placeholder="输入路径关键词"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
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
                        {formatTime(log.created_at)}
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
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
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
                  <p className="mt-1 text-sm text-gray-900">{formatTime(selectedLog.created_at)}</p>
                </div>
              </div>

              {Object.keys(selectedLog.query_params).length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-500 mb-2">查询参数</p>
                  <pre className="bg-gray-50 rounded p-3 text-xs overflow-x-auto">
                    {JSON.stringify(selectedLog.query_params, null, 2)}
                  </pre>
                </div>
              )}

              {selectedLog.request_body && (
                <div>
                  <p className="text-sm font-medium text-gray-500 mb-2">请求体</p>
                  <pre className="bg-gray-50 rounded p-3 text-xs overflow-x-auto max-h-60">
                    {JSON.stringify(selectedLog.request_body, null, 2)}
                  </pre>
                </div>
              )}

              {selectedLog.response_body && (
                <div>
                  <p className="text-sm font-medium text-gray-500 mb-2">响应体</p>
                  <pre className="bg-gray-50 rounded p-3 text-xs overflow-x-auto max-h-60">
                    {JSON.stringify(selectedLog.response_body, null, 2)}
                  </pre>
                </div>
              )}

              {selectedLog.error_message && (
                <div>
                  <p className="text-sm font-medium text-red-500 mb-2">错误信息</p>
                  <pre className="bg-red-50 rounded p-3 text-xs overflow-x-auto text-red-900">
                    {selectedLog.error_message}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Admin;
