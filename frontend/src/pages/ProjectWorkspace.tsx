/**
 * 项目工作区组件
 * 用于单个项目的标书编写流程
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { projectApi } from '../services/api';
import { useAppState } from '../hooks/useAppState';
import type { Project, ProjectProgress } from '../types/project';
import ConfigPanel from '../components/ConfigPanel';
import StepBar from '../components/StepBar';
import DocumentAnalysis from './DocumentAnalysis';
import OutlineEdit from './OutlineEdit';
import ContentEdit from './ContentEdit';

const ProjectWorkspace: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [project, setProject] = useState<Project | null>(null);
  const [progress, setProgress] = useState<ProjectProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const {
    state,
    updateConfig,
    updateStep,
    updateFileContent,
    updateAnalysisResults,
    updateOutline,
    updateSelectedChapter,
    nextStep,
    prevStep,
  } = useAppState();

  const steps = ['标书解析', '目录编辑', '正文编辑'];

  const loadProject = useCallback(async () => {
    if (!projectId) return;

    try {
      setLoading(true);
      setError(null);
      const projectData = await projectApi.get(projectId);
      setProject(projectData);

      // 如果项目有已保存的数据，加载到状态中
      if (projectData.file_content) {
        updateFileContent(projectData.file_content);
      }
      if (projectData.project_overview && projectData.tech_requirements) {
        updateAnalysisResults(projectData.project_overview, projectData.tech_requirements);
      }

      // 加载进度
      try {
        const progressData = await projectApi.getProgress(projectId);
        setProgress(progressData);
      } catch {
        // 忽略进度加载失败
      }
    } catch (err) {
      setError('加载项目失败，请稍后重试');
      console.error('加载项目失败:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId, updateFileContent, updateAnalysisResults]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleBackToList = () => {
    navigate('/');
  };

  const renderCurrentPage = () => {
    switch (state.currentStep) {
      case 0:
        return (
          <DocumentAnalysis
            fileContent={state.fileContent}
            projectOverview={state.projectOverview}
            techRequirements={state.techRequirements}
            onFileUpload={updateFileContent}
            onAnalysisComplete={updateAnalysisResults}
          />
        );
      case 1:
        return (
          <OutlineEdit
            projectOverview={state.projectOverview}
            techRequirements={state.techRequirements}
            outlineData={state.outlineData}
            onOutlineGenerated={updateOutline}
          />
        );
      case 2:
        return (
          <ContentEdit
            outlineData={state.outlineData}
            selectedChapter={state.selectedChapter}
            onChapterSelect={updateSelectedChapter}
          />
        );
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-gray-50">
        <p className="text-red-600 mb-4">{error || '项目不存在'}</p>
        <button
          onClick={handleBackToList}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          返回项目列表
        </button>
      </div>
    );
  }

  return (
    <div className="h-screen overflow-hidden bg-gray-50 flex">
      {/* 左侧配置面板 */}
      <ConfigPanel
        config={state.config}
        onConfigChange={updateConfig}
      />

      {/* 主内容区域 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部导航栏 */}
        <div className="sticky top-0 z-50 bg-white shadow-sm px-6">
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center space-x-4">
              <button
                onClick={handleBackToList}
                className="inline-flex items-center text-gray-500 hover:text-gray-700"
              >
                <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
              </button>
              <div className="flex items-center">
                <h1 className="text-lg font-semibold text-gray-900">{project.name}</h1>
                {progress && progress.total_chapters > 0 && (
                  <span className="ml-3 text-sm text-gray-500">
                    {progress.finalized}/{progress.total_chapters} 已定稿
                  </span>
                )}
              </div>
            </div>
            <StepBar steps={steps} currentStep={state.currentStep} />
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">
                {user?.username} ({user?.role === 'admin' ? '管理员' : user?.role === 'reviewer' ? '审核员' : '编辑'})
              </span>
              <button
                onClick={handleLogout}
                className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                退出登录
              </button>
            </div>
          </div>
        </div>

        {/* 页面内容 */}
        <div id="app-main-scroll" className="flex-1 p-6 overflow-y-auto">
          {renderCurrentPage()}
        </div>

        {/* 底部导航按钮 */}
        <div className="sticky bottom-0 z-50 bg-white border-t border-gray-200 px-6 py-4">
          <div className="flex justify-between">
            <div className="flex items-center space-x-3">
              <button
                onClick={() => updateStep(0)}
                disabled={state.currentStep === 0}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:bg-gray-400 disabled:text-white disabled:cursor-not-allowed"
              >
                首页
              </button>

              <button
                onClick={prevStep}
                disabled={state.currentStep === 0}
                className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed"
              >
                上一步
              </button>
            </div>

            <button
              onClick={nextStep}
              disabled={state.currentStep === steps.length - 1}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              下一步
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProjectWorkspace;
