/**
 * 模型缓存工具
 * 用于获取当前选择的模型配置
 */

const MODEL_CACHE_KEY = 'yibiao:model_cache';

interface ModelCache {
  models: string[];
  currentModel: string;
  timestamp: number;
}

/**
 * 从缓存加载模型配置
 */
const loadModelCache = (): ModelCache | null => {
  try {
    const raw = localStorage.getItem(MODEL_CACHE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

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
  return {
    models: cache.models,
    currentModel: cache.currentModel,
  };
}
