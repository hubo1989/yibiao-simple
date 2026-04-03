/**
 * 提示词编辑器组件
 * 支持变量点击插入、预览、重置为默认、版本历史
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { DocumentTextIcon, VariableIcon, ArrowPathIcon, EyeIcon, ClockIcon, ArrowUturnLeftIcon } from '@heroicons/react/24/outline';
import { promptApi } from '../services/api';
import type { PromptVersionResponse } from '../types/prompt';
import type { ApiError } from '../utils/error';

interface PromptEditorProps {
  sceneKey: string;
  sceneName: string;
  prompt: string;
  availableVars: Record<string, string> | null;
  source: 'project' | 'global' | 'builtin';
  hasProjectOverride?: boolean;
  hasGlobalOverride?: boolean;
  currentVersion?: number;
  onSave: (prompt: string) => Promise<void>;
  onReset?: () => Promise<void>;
  onDelete?: () => Promise<void>;
  isSaving?: boolean;
  readOnly?: boolean;
}

const PromptEditor: React.FC<PromptEditorProps> = ({
  sceneKey,
  sceneName,
  prompt: initialPrompt,
  availableVars,
  source,
  hasProjectOverride = false,
  hasGlobalOverride = false,
  currentVersion = 1,
  onSave,
  onReset,
  onDelete,
  isSaving = false,
  readOnly = false,
}) => {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [previewVars, setPreviewVars] = useState<Record<string, string>>({});
  const [showPreview, setShowPreview] = useState(false);
  const [isChanged, setIsChanged] = useState(false);

  // 版本历史相关状态
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [versions, setVersions] = useState<PromptVersionResponse[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<PromptVersionResponse | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 监听外部 prop 变化
  useEffect(() => {
    setPrompt(initialPrompt);
    setIsChanged(false);
  }, [initialPrompt]);

  // 检测变更
  useEffect(() => {
    const changed = prompt !== initialPrompt;
    setIsChanged(changed);
  }, [prompt, initialPrompt]);

  // 插入变量到文本框
  const insertVariable = useCallback((varName: string) => {
    const textarea = textareaRef.current;
    if (!textarea || readOnly) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    const varTag = `{{${varName}}}`;

    const newText = text.substring(0, start) + varTag + text.substring(end);
    textarea.value = newText;
    textarea.selectionStart = textarea.selectionEnd = start + varTag.length;
    textarea.focus();

    // 触发 React 状态更新
    const event = new Event('input', { bubbles: true });
    textarea.dispatchEvent(event);
    setPrompt(newText);
  }, [readOnly]);

  // 渲染预览
  const renderPreview = useCallback((template: string, vars: Record<string, string>) => {
    let result = template;

    // 处理条件块 {{#if var}}...{{/if}}
    const ifPattern = /\{\{#if\s+(\w+)\}\}(.*?)\{\{\/if\}\}/gs;
    result = result.replace(ifPattern, (_, varName, content) => {
      return vars[varName] ? content : '';
    });

    // 处理列表迭代 {{#each var}}...{{/each}}
    const eachPattern = /\{\{#each\s+(\w+)\}\}(.*?)\{\{\/each\}\}/gs;
    result = result.replace(eachPattern, (_, varName, itemTemplate) => {
      const arr = vars[varName];
      if (Array.isArray(arr)) {
        return arr.map(item => {
          if (typeof item === 'object') {
            let itemText = itemTemplate;
            Object.entries(item).forEach(([key, val]) => {
              itemText = itemText.replace(new RegExp(`\\{\\{this\\.${key}\\}\\}`, 'g'), String(val));
            });
            return itemText;
          }
          return itemTemplate.replace(/{{this}}/g, String(item));
        }).join('\n');
      }
      return '';
    });

    // 替换简单变量 {{var}}
    Object.entries(vars).forEach(([key, value]) => {
      if (typeof value !== 'object') {
        result = result.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), String(value || ''));
      }
    });

    return result;
  }, []);

  // 加载版本历史
  const loadVersions = useCallback(async () => {
    if (source === 'builtin') return;

    try {
      setVersionsLoading(true);
      const data = await promptApi.listPromptVersions(sceneKey, { limit: 20 });
      setVersions(data.items);
    } catch (err) {
      console.error('加载版本历史失败:', err);
    } finally {
      setVersionsLoading(false);
    }
  }, [sceneKey, source]);

  // 回滚到指定版本
  const handleRollback = useCallback(async (version: number) => {
    if (!window.confirm(`确定要回滚到版本 ${version} 吗？`)) return;

    try {
      await promptApi.rollbackPrompt(sceneKey, { version });
      setShowVersionHistory(false);
      if (onReset) {
        await onReset();
      }
    } catch (err: unknown) {
      const detail = (err as ApiError)?.response?.data?.detail;
      alert(detail || '回滚失败');
    }
  }, [sceneKey, onReset]);

  // 预览历史版本
  const handlePreviewVersion = useCallback((version: PromptVersionResponse) => {
    setSelectedVersion(selectedVersion?.id === version.id ? null : version);
  }, [selectedVersion]);

  const handleSave = async () => {
    await onSave(prompt);
    setIsChanged(false);
  };

  const handleReset = async () => {
    if (onReset) {
      await onReset();
    }
  };

  const handleDelete = async () => {
    if (onDelete && window.confirm('确定要删除此自定义提示词吗？删除后将恢复使用全局或默认配置。')) {
      await onDelete();
    }
  };

  // 打开版本历史时加载数据
  useEffect(() => {
    if (showVersionHistory && versions.length === 0) {
      loadVersions();
    }
  }, [showVersionHistory, versions.length, loadVersions]);

  const sourceLabel = {
    project: '项目级',
    global: '全局',
    builtin: '内置默认',
  };

  const sourceColor = {
    project: 'bg-blue-100 text-blue-800',
    global: 'bg-green-100 text-green-800',
    builtin: 'bg-gray-100 text-gray-800',
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* 头部 */}
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <DocumentTextIcon className="h-5 w-5 text-gray-500" />
          <h3 className="text-sm font-medium text-gray-900">{sceneName}</h3>
          <span className={`px-2 py-0.5 text-xs rounded-full ${sourceColor[source]}`}>
            {sourceLabel[source]}
          </span>
          {source !== 'builtin' && (
            <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">
              v{currentVersion}
            </span>
          )}
          {hasProjectOverride && source !== 'project' && (
            <span className="px-2 py-0.5 text-xs rounded-full bg-blue-50 text-blue-600">
              已被项目覆盖
            </span>
          )}
          {hasGlobalOverride && source === 'builtin' && !hasProjectOverride && (
            <span className="px-2 py-0.5 text-xs rounded-full bg-green-50 text-green-600">
              已被全局覆盖
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <code className="text-xs text-gray-400 font-mono">{sceneKey}</code>
          {source !== 'builtin' && (
            <button
              onClick={() => setShowVersionHistory(!showVersionHistory)}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-600 hover:text-indigo-600 hover:bg-indigo-50 rounded"
              title="查看版本历史"
            >
              <ClockIcon className="h-4 w-4" />
              版本历史
            </button>
          )}
        </div>
      </div>

      {/* 版本历史面板 */}
      {showVersionHistory && source !== 'builtin' && (
        <div className="border-b border-gray-200 bg-gray-50 max-h-80 overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-gray-700">版本历史</h4>
              <button
                onClick={() => setShowVersionHistory(false)}
                className="text-xs text-gray-500 hover:text-gray-700"
              >
                关闭
              </button>
            </div>

            {versionsLoading ? (
              <div className="flex justify-center py-4">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600"></div>
              </div>
            ) : versions.length === 0 ? (
              <div className="text-center py-4 text-sm text-gray-500">
                暂无版本历史
              </div>
            ) : (
              <div className="space-y-2">
                {versions.map((version) => (
                  <div key={version.id} className="bg-white rounded border border-gray-200">
                    <div
                      className="flex items-center justify-between p-3 cursor-pointer hover:bg-gray-50"
                      onClick={() => handlePreviewVersion(version)}
                    >
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-0.5 text-xs rounded font-medium ${
                          version.version === currentVersion
                            ? 'bg-indigo-100 text-indigo-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}>
                          v{version.version}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(version.created_at).toLocaleString('zh-CN')}
                        </span>
                        {version.created_by_name && (
                          <span className="text-xs text-gray-400">
                            by {version.created_by_name}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {version.version !== currentVersion && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRollback(version.version);
                            }}
                            className="inline-flex items-center gap-1 px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 rounded"
                          >
                            <ArrowUturnLeftIcon className="h-3 w-3" />
                            回滚
                          </button>
                        )}
                        {version.version === currentVersion && (
                          <span className="text-xs text-green-600 font-medium">当前版本</span>
                        )}
                      </div>
                    </div>

                    {/* 版本内容预览 */}
                    {selectedVersion?.id === version.id && (
                      <div className="border-t border-gray-100 p-3 bg-gray-50">
                        <pre className="text-xs text-gray-700 whitespace-pre-wrap bg-white p-2 rounded border border-gray-200 max-h-40 overflow-y-auto">
                          {version.prompt}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="flex">
        {/* 编辑区域 */}
        <div className="flex-1 p-4">
          <textarea
            ref={textareaRef}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            readOnly={readOnly}
            className={`w-full h-80 p-3 border border-gray-200 rounded-md font-mono text-sm resize-y ${
              readOnly ? 'bg-gray-50 cursor-not-allowed' : 'focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
            }`}
            placeholder="提示词内容..."
          />
        </div>

        {/* 变量面板 */}
        {availableVars && Object.keys(availableVars).length > 0 && (
          <div className="w-64 border-l border-gray-200 p-4 bg-gray-50">
            <div className="flex items-center gap-2 mb-3">
              <VariableIcon className="h-4 w-4 text-gray-500" />
              <h4 className="text-xs font-medium text-gray-700 uppercase tracking-wide">可用变量</h4>
            </div>
            <div className="space-y-1">
              {Object.entries(availableVars).map(([varName, varDesc]) => (
                <button
                  key={varName}
                  onClick={() => insertVariable(varName)}
                  disabled={readOnly}
                  className={`w-full text-left px-2 py-1.5 rounded text-sm font-mono flex items-center justify-between group ${
                    readOnly
                      ? 'text-gray-400 cursor-not-allowed'
                      : 'text-gray-700 hover:bg-indigo-50 hover:text-indigo-600'
                  }`}
                  title={String(varDesc)}
                >
                  <span>{`{{${varName}}}`}</span>
                  <span className="text-xs text-gray-400 group-hover:text-indigo-400 truncate max-w-[100px]">
                    {String(varDesc)}
                  </span>
                </button>
              ))}
            </div>

            {/* 预览区域 */}
            <div className="mt-4 pt-4 border-t border-gray-200">
              <button
                onClick={() => setShowPreview(!showPreview)}
                className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-indigo-600"
              >
                <EyeIcon className="h-4 w-4" />
                {showPreview ? '隐藏预览' : '显示预览'}
              </button>

              {showPreview && (
                <div className="mt-3 space-y-2">
                  {Object.keys(availableVars).map((varName) => (
                    <div key={varName}>
                      <label className="block text-xs text-gray-500 mb-0.5">{varName}</label>
                      <input
                        type="text"
                        value={previewVars[varName] || ''}
                        onChange={(e) => setPreviewVars({ ...previewVars, [varName]: e.target.value })}
                        className="w-full px-2 py-1 text-sm border border-gray-200 rounded focus:ring-1 focus:ring-indigo-500"
                        placeholder={`输入示例值`}
                      />
                    </div>
                  ))}
                </div>
              )}

              {showPreview && (
                <div className="mt-3 p-2 bg-white border border-gray-200 rounded text-xs font-mono text-gray-600 whitespace-pre-wrap max-h-40 overflow-auto">
                  {renderPreview(prompt, previewVars)}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 操作按钮 */}
      {!readOnly && (
        <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between bg-gray-50">
          <div className="flex items-center gap-2">
            {onReset && source !== 'builtin' && (
              <button
                onClick={handleReset}
                disabled={isSaving}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md"
              >
                <ArrowPathIcon className="h-4 w-4" />
                重置为默认
              </button>
            )}
            {onDelete && (source === 'project' || source === 'global') && (
              <button
                onClick={handleDelete}
                disabled={isSaving}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded-md"
              >
                删除自定义
              </button>
            )}
          </div>
          <button
            onClick={handleSave}
            disabled={isSaving || !isChanged}
            className={`inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md ${
              isChanged
                ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
            }`}
          >
            {isSaving ? '保存中...' : '保存更改'}
          </button>
        </div>
      )}
    </div>
  );
};

export default PromptEditor;
