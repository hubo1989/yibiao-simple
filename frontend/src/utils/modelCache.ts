/**
 * 模型缓存工具
 * 用于获取当前选择的模型配置
 */

const MODEL_CACHE_KEY = 'yibiao:model_cache';

export interface ProviderModelOption {
  configId: string;
  provider: string;
  models: string[];
  defaultModel: string;
  isDefault: boolean;
}

export interface ModelCache {
  providers: ProviderModelOption[];
  currentProviderId: string;
  currentModel: string;
  timestamp: number;
}

interface LegacyModelCache {
  models?: string[];
  currentModel?: string;
  timestamp?: number;
}

/**
 * 从缓存加载模型配置
 */
export function loadModelCache(): ModelCache | null {
  try {
    const raw = localStorage.getItem(MODEL_CACHE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<ModelCache> & LegacyModelCache;
    if (Array.isArray(parsed.providers)) {
      return {
        providers: parsed.providers.map((item) => ({
          configId: String(item.configId || ''),
          provider: String(item.provider || ''),
          models: Array.isArray(item.models) ? item.models.map(String) : [],
          defaultModel: String(item.defaultModel || item.models?.[0] || ''),
          isDefault: Boolean(item.isDefault),
        })),
        currentProviderId: String(parsed.currentProviderId || ''),
        currentModel: String(parsed.currentModel || ''),
        timestamp: Number(parsed.timestamp || Date.now()),
      };
    }

    if (Array.isArray(parsed.models)) {
      const models = parsed.models.map(String);
      const currentModel = String(parsed.currentModel || models[0] || '');
      return {
        providers: models.length > 0 ? [{
          configId: '',
          provider: '默认配置',
          models,
          defaultModel: currentModel,
          isDefault: true,
        }] : [],
        currentProviderId: '',
        currentModel,
        timestamp: Number(parsed.timestamp || Date.now()),
      };
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * 保存模型缓存
 */
export function saveModelCache(
  providers: ProviderModelOption[],
  currentProviderId: string,
  currentModel: string,
): void {
  localStorage.setItem(MODEL_CACHE_KEY, JSON.stringify({
    providers,
    currentProviderId,
    currentModel,
    timestamp: Date.now(),
  }));
}

/**
 * 获取当前选择的 provider 配置 ID
 */
export function getCurrentProviderConfigId(): string | null {
  const cache = loadModelCache();
  return cache?.currentProviderId || null;
}

/**
 * 获取当前选择的模型名称
 * @returns 当前模型名称，如果未选择则返回 null
 */
export function getCurrentModel(): string | null {
  const cache = loadModelCache();
  return cache?.currentModel || null;
}

/**
 * 获取完整的模型缓存信息
 * @returns 模型缓存对象，如果不存在则返回 null
 */
export function getModelCache(): { models: string[]; currentModel: string } | null {
  const cache = loadModelCache();
  if (!cache) return null;
  const activeProvider = cache.providers.find((item) => item.configId === cache.currentProviderId)
    || cache.providers[0];
  return {
    models: activeProvider?.models || [],
    currentModel: cache.currentModel,
  };
}
