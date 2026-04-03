/**
 * 项目设置页面
 * 包含项目级提示词配置等功能
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { promptApi, projectApi } from '../services/api';
import type { Project } from '../types/project';
import type { ProjectPromptConfig, PromptCategory } from '../types/prompt';
import { PROMPT_CATEGORY_NAMES } from '../types/prompt';
import ConfigPanel from '../components/ConfigPanel';
import PromptEditor from '../components/PromptEditor';
import { useLayoutHeader } from '../layouts/layoutHeader';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { getErrorMessage } from '../utils/error';

const ProjectSettings: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { setLayoutHeader } = useLayoutHeader();
  
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [prompts, setPrompts] = useState<ProjectPromptConfig[]>([]);
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [promptCategoryFilter, setPromptCategoryFilter] = useState<PromptCategory | ''>('');
  const [expandedPrompt, setExpandedPrompt] = useState<string | null>(null);

  // 加载项目信息
  const loadProject = useCallback(async () => {
    if (!projectId) return;
    
    try {
      setLoading(true);
      const projectData = await projectApi.get(projectId);
      setProject(projectData);
    } catch (err) {
      console.error('加载项目失败:', err);
      alert('加载项目失败');
      navigate(-1);
    } finally {
      setLoading(false);
    }
  }, [projectId, navigate]);

  // 加载项目提示词配置
  const loadPrompts = useCallback(async () => {
    if (!projectId) return;
    
    try {
      setPromptsLoading(true);
      const data = await promptApi.listProjectPrompts(projectId, {
        category: promptCategoryFilter || undefined,
      });
      setPrompts(data.items);
    } catch (err) {
      console.error('加载提示词配置失败:', err);
    } finally {
      setPromptsLoading(false);
    }
  }, [projectId, promptCategoryFilter]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  useEffect(() => {
    if (project) {
      loadPrompts();
    }
  }, [project, loadPrompts]);

  useEffect(() => {
    return () => {
      setLayoutHeader(null);
    };
  }, [setLayoutHeader]);

  useEffect(() => {
    if (!project) {
      setLayoutHeader(null);
      return;
    }

    setLayoutHeader({
      content: (
        <div className="flex min-w-0 items-center gap-4 py-2">
          <button
            onClick={() => navigate(-1)}
            className="inline-flex shrink-0 items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:text-slate-900"
          >
            <ArrowLeftOutlined />
            返回
          </button>

          <div className="h-5 w-px shrink-0 bg-slate-200" />

          <div className="flex min-w-0 items-center gap-3">
            <span className="truncate text-sm font-medium text-slate-500">{project.name}</span>
            <span className="text-slate-300">/</span>
            <h1 className="truncate text-[18px] font-semibold tracking-tight text-slate-900">项目设置</h1>
            <span className="hidden truncate text-sm text-slate-500 xl:inline">
              Provider、模型与提示词配置统一在这里维护
            </span>
          </div>
        </div>
      ),
    });
  }, [navigate, project, setLayoutHeader]);

  // 权限检查：只有项目管理员和成员可以访问
  const canEdit = project && (
    project.creator_id === user?.id || 
    user?.role === 'admin'
  );

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center bg-gray-50">
        <p className="text-red-600 mb-4">项目不存在</p>
        <button
          onClick={() => navigate(-1)}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          返回
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-gray-50">
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <div className="grid gap-8 xl:grid-cols-3 items-start">
          <div className="space-y-8 xl:col-span-1 xl:sticky xl:top-8">
            <ConfigPanel />
          </div>

          {/* 提示词配置部分 */}
          <div className="bg-white shadow rounded-lg xl:col-span-2">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-medium text-gray-900">提示词配置</h2>
              <p className="text-sm text-gray-500 mt-1">
                自定义项目级提示词，优先级高于全局配置。未配置的场景将继承全局或内置默认提示词。
              </p>
            </div>

            <div className="px-6 py-4">
              <div className="mb-6 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <select
                    value={promptCategoryFilter}
                    onChange={(e) => setPromptCategoryFilter(e.target.value as PromptCategory | '')}
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                        className="w-full flex items-center justify-between p-4 bg-white rounded-lg border border-gray-200 hover:border-gray-300 text-left transition-colors"
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
                            {PROMPT_CATEGORY_NAMES[prompt.category]}
                          </span>
                          
                          {/* 来源标识 */}
                          <span className={`px-2 py-0.5 text-xs rounded-full ${
                            prompt.source === 'project' ? 'bg-purple-100 text-purple-700' :
                            prompt.source === 'global' ? 'bg-blue-100 text-blue-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {prompt.source === 'project' ? '项目自定义' : 
                             prompt.source === 'global' ? '全局配置' : '内置默认'}
                          </span>
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
                            source={prompt.source}
                            hasProjectOverride={prompt.has_project_override}
                            hasGlobalOverride={prompt.has_global_override}
                            onSave={async (newPrompt) => {
                              if (!canEdit) {
                                alert('您没有权限修改此项目的提示词');
                                return;
                              }
                              try {
                                await promptApi.setProjectPrompt(projectId!, prompt.scene_key, {
                                  prompt: newPrompt,
                                });
                                loadPrompts();
                              } catch (err: unknown) {
                                const errorMsg = getErrorMessage(err, '保存失败');
                                alert(errorMsg);
                              }
                            }}
                            onDelete={prompt.has_project_override ? async () => {
                              if (!canEdit) {
                                alert('您没有权限修改此项目的提示词');
                                return;
                              }
                              if (!window.confirm('确定要删除项目级自定义提示词，恢复继承全局配置吗？')) {
                                return;
                              }
                              try {
                                await promptApi.deleteProjectPrompt(projectId!, prompt.scene_key);
                                loadPrompts();
                              } catch (err: unknown) {
                                const errorMsg = getErrorMessage(err, '删除失败');
                                alert(errorMsg);
                              }
                            } : undefined}
                            readOnly={!canEdit}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ProjectSettings;
