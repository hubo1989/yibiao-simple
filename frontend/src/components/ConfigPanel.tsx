/**
 * 项目基础配置面板
 * 注：API Key 和 provider 供给已移至后台管理，项目成员只需选择当前浏览器默认 provider 与模型
 */
import React, { useEffect, useMemo, useState } from 'react';
import { configApi } from '../services/api';
import {
  loadModelCache,
  saveModelCache,
  type ProviderModelOption,
} from '../utils/modelCache';

interface ProviderModelsResponse {
  success: boolean;
  message: string;
  models?: string[];
  default_provider_config_id?: string | null;
  providers?: Array<{
    config_id: string;
    provider: string;
    models: string[];
    default_model: string;
    is_default: boolean;
  }>;
}

const normalizeProviders = ({
  providers,
  models,
}: Pick<ProviderModelsResponse, 'providers' | 'models'>): ProviderModelOption[] => {
  const normalizedProviders = (providers || []).map((item) => ({
    configId: item.config_id,
    provider: item.provider,
    models: item.models || [],
    defaultModel: item.default_model || item.models?.[0] || '',
    isDefault: item.is_default,
  }));

  if (normalizedProviders.length > 0) {
    return normalizedProviders;
  }

  const fallbackModels = (models || []).filter(Boolean);
  if (fallbackModels.length === 0) {
    return [];
  }

  return [{
    configId: '',
    provider: '默认配置',
    models: fallbackModels,
    defaultModel: fallbackModels[0],
    isDefault: true,
  }];
};

const getPreferredProviderId = (
  providers: ProviderModelOption[],
  currentProviderId: string,
  defaultProviderId?: string | null,
): string => {
  if (currentProviderId && providers.some((item) => item.configId === currentProviderId)) {
    return currentProviderId;
  }
  if (defaultProviderId && providers.some((item) => item.configId === defaultProviderId)) {
    return defaultProviderId;
  }
  return providers[0]?.configId || '';
};

const getProviderModel = (providers: ProviderModelOption[], providerId: string): ProviderModelOption | null => (
  providers.find((item) => item.configId === providerId) || providers[0] || null
);

const ConfigPanel: React.FC = () => {
  const [providers, setProviders] = useState<ProviderModelOption[]>([]);
  const [currentProviderId, setCurrentProviderId] = useState<string>('');
  const [currentModel, setCurrentModel] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    const cache = loadModelCache();
    if (cache) {
      setProviders(cache.providers);
      setCurrentProviderId(cache.currentProviderId);
      setCurrentModel(cache.currentModel);
    }
  }, []);

  useEffect(() => {
    if (providers.length > 0 && currentModel) {
      try {
        saveModelCache(providers, currentProviderId, currentModel);
      } catch (e) {
        console.warn('保存模型缓存失败:', e);
      }
    }
  }, [providers, currentProviderId, currentModel]);

  const activeProvider = useMemo(
    () => getProviderModel(providers, currentProviderId),
    [providers, currentProviderId],
  );

  const handleProviderChange = (providerId: string) => {
    const provider = getProviderModel(providers, providerId);
    setCurrentProviderId(providerId);
    if (!provider) {
      setCurrentModel('');
      return;
    }

    const nextModel = provider.models.includes(currentModel)
      ? currentModel
      : (provider.defaultModel || provider.models[0] || '');
    setCurrentModel(nextModel);
  };

  const handleGetModels = async () => {
    try {
      setLoading(true);
      const response = await configApi.getModels();
      const data = response.data as ProviderModelsResponse;

      if (data.success) {
        const nextProviders = normalizeProviders(data);
        const nextProviderId = getPreferredProviderId(
          nextProviders,
          currentProviderId,
          data.default_provider_config_id,
        );
        const nextProvider = getProviderModel(nextProviders, nextProviderId);
        const nextModel = nextProvider
          ? (nextProvider.models.includes(currentModel)
            ? currentModel
            : (nextProvider.defaultModel || nextProvider.models[0] || ''))
          : '';

        setProviders(nextProviders);
        setCurrentProviderId(nextProviderId);
        setCurrentModel(nextModel);
        setMessage({
          type: 'success',
          text: `获取到 ${nextProviders.length} 个 Provider`,
        });
        setTimeout(() => setMessage(null), 3000);
      } else {
        setMessage({ type: 'error', text: data.message });
      }
    } catch {
      setMessage({ type: 'error', text: '获取模型列表失败' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="bg-white shadow rounded-lg">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-medium text-gray-900">拉卡拉标书智能体配置</h2>
        <p className="mt-1 text-sm text-gray-500">
          Provider 与模型选择会缓存到当前浏览器，供标书解析、目录生成与正文扩写流程复用。
        </p>
      </div>

      <div className="px-6 py-5 space-y-6">
        <div>
          <div className="flex items-center justify-between gap-3 mb-3">
            <h3 className="text-base font-medium text-gray-900">模型信息</h3>
            {providers.length > 0 && (
              <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                已缓存 {providers.length} 个 Provider
              </span>
            )}
          </div>

          <button
            onClick={handleGetModels}
            disabled={loading}
            className="w-full inline-flex justify-center items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:bg-gray-100"
          >
            {loading ? '获取中...' : '重新获取模型列表'}
          </button>

          {activeProvider ? (
            <div className="mt-4 space-y-4">
              <div>
                <label htmlFor="provider-select" className="block text-sm font-medium text-gray-700 mb-1">
                  当前 Provider
                </label>
                <select
                  id="provider-select"
                  value={currentProviderId}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                >
                  {providers.map((provider) => (
                    <option key={provider.configId} value={provider.configId}>
                      {provider.provider}{provider.isDefault ? '（默认）' : ''}
                    </option>
                  ))}
                </select>
                <p className="mt-2 text-xs text-gray-500">
                  当管理员配置了多个 Provider 时，可在这里切换当前编写流程使用的服务源。
                </p>
              </div>

              <div>
                <label htmlFor="model-select" className="block text-sm font-medium text-gray-700 mb-1">
                  当前默认模型
                </label>
                <select
                  id="model-select"
                  value={currentModel}
                  onChange={(e) => setCurrentModel(e.target.value)}
                  className="w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                >
                  {activeProvider.models.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
                <p className="mt-2 text-xs text-gray-500">
                  {activeProvider.provider} 下的模型列表已缓存。若后台配置有更新，请重新获取。
                </p>
              </div>
            </div>
          ) : (
            <p className="mt-4 text-sm text-gray-500">
              暂未读取 Provider 与模型列表。点击上方按钮后，可切换当前浏览器默认使用的 Provider 与模型。
            </p>
          )}
        </div>

        {message && (
          <div className={`p-3 rounded-md text-sm ${
            message.type === 'success'
              ? 'bg-green-100 text-green-700 border border-green-200'
              : 'bg-red-100 text-red-700 border border-red-200'
          }`}>
            {message.text}
          </div>
        )}

        <div className="border-t border-gray-200 pt-4">
          <h3 className="text-sm font-medium text-gray-900 mb-2">使用说明</h3>
          <div className="text-sm text-gray-600 space-y-2">
            <p>1. 管理员在系统设置中维护 API Key、Provider 和模型供给。</p>
            <p>2. 这里选中的 Provider 和模型会应用到当前浏览器的编写流程，不区分具体项目文件。</p>
            <p>3. 若解析或生成前需要切换 Provider，先到项目设置刷新并选择后再继续。</p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ConfigPanel;
