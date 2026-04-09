/**
 * 项目工作区组件
 * 用于单个项目的标书编写流程
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { projectApi, consistencyApi, documentApi, outlineApi } from '../services/api';
import { useAppState } from '../hooks/useAppState';
import type { Project, ProjectProgress } from '../types/project';
import type { ConsistencyCheckResponse } from '../types/consistency';
import { getErrorMessage } from '../utils/error';
import StepBar from '../components/StepBar';
import VersionHistory from '../components/VersionHistory';
import MemberSidebar from '../components/MemberSidebar';
import ConsistencyPanel from '../components/ConsistencyPanel';
import CommentPanel from '../components/CommentPanel';
import MaterialRequirementDrawer from '../components/MaterialRequirementDrawer';
import { useLayoutHeader } from '../layouts/layoutHeader';
import DocumentAnalysis from './DocumentAnalysis';
import OutlineEdit from './OutlineEdit';
import ContentEdit from './ContentEdit';

import { Layout, Button, Typography, Spin, message } from 'antd';
import {
  TeamOutlined,
  SettingOutlined,
  HistoryOutlined,
  ArrowLeftOutlined,
  PaperClipOutlined,
} from '@ant-design/icons';

const { Content } = Layout;

const ProjectWorkspace: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const { setLayoutHeader } = useLayoutHeader();
  const [project, setProject] = useState<Project | null>(null);
  const [progress, setProgress] = useState<ProjectProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [showMemberSidebar, setShowMemberSidebar] = useState(false);
  const [showConsistencyPanel, setShowConsistencyPanel] = useState(false);
  const [consistencyResult, setConsistencyResult] = useState<ConsistencyCheckResponse | null>(null);
  const [isCheckingConsistency, setIsCheckingConsistency] = useState(false);
  const [activeCommentChapter, setActiveCommentChapter] = useState<string | null>(null);
  const [showMaterialDrawer, setShowMaterialDrawer] = useState(false);
  const [lastChapterSummaries, setLastChapterSummaries] = useState<{ chapter_number: string; title: string; summary: string }[]>([]);
  const [highlightedChapters, setHighlightedChapters] = useState<Set<string>>(new Set());

  const {
    state,
    updateStep,
    updateFileContent,
    updateAnalysisResults,
    updateOutline,
    updateSelectedChapter,
  } = useAppState(projectId);

  const steps = ['标书解析', '目录编辑', '正文编辑'];
  const analysisReady = Boolean(state.projectOverview.trim() && state.techRequirements.trim());
  const outlineReady = Boolean(state.outlineData?.outline?.length);

  const loadProject = useCallback(async () => {
    if (!projectId) return;

    try {
      setLoading(true);
      setError(null);
      const projectData = await projectApi.get(projectId);

      // 权限检查
      const isOwner = projectData.creator_id === user?.id;
      const isAdmin = user?.role === 'admin';

      let isMember = false;
      if (!isOwner && !isAdmin) {
        try {
          const members = await projectApi.getMembers(projectId);
          isMember = members.some(m => m.user_id === user?.id);
        } catch {
          isMember = false;
        }
      }

      if (!isOwner && !isAdmin && !isMember) {
        setError('您没有权限访问此项目');
        setLoading(false);
        return;
      }

      setProject(projectData);

      if (projectData.file_content) {
        updateFileContent(projectData.file_content);
      }
      if (projectData.project_overview && projectData.tech_requirements) {
        updateAnalysisResults(projectData.project_overview, projectData.tech_requirements);
      }

      try {
        const progressData = await projectApi.getProgress(projectId);
        setProgress(progressData);
      } catch {
        // Ignore progress fail
      }

      // 从后端加载已保存的章节目录（确保即使 draftStorage 丢失也能恢复）
      try {
        const chaptersResp = await outlineApi.getProjectChapters(projectId);
        if (chaptersResp.chapters?.length) {
          // 将扁平章节列表构建为 OutlineData 树形结构
          const chapterMap = new Map<string | null, typeof chaptersResp.chapters>();
          for (const ch of chaptersResp.chapters) {
            const parentKey = ch.parent_id ?? null;
            if (!chapterMap.has(parentKey)) chapterMap.set(parentKey, []);
            chapterMap.get(parentKey)!.push(ch);
          }
          const buildTree = (parentId: string | null): import('../types').OutlineItem[] => {
            const children = chapterMap.get(parentId) ?? [];
            return children.map(ch => ({
              id: ch.chapter_number,
              title: ch.title,
              description: '',
              rating_item: undefined,
              chapter_role: undefined,
              avoid_overlap: undefined,
              children: buildTree(ch.id),
              status: ch.status === 'generated' ? 'generated' as const
                    : ch.status === 'pending' ? 'pending' as const
                    : undefined,
            })).map(item => item.children?.length ? item : { ...item, children: undefined });
          };
          const outlineTree = buildTree(null);
          if (outlineTree.length) {
            updateOutline({
              outline: outlineTree,
              project_overview: projectData.project_overview || '',
            });
          }
        }
      } catch {
        // 目录加载失败不阻塞
      }
    } catch (err) {
      setError('加载项目失败，请稍后重试');
      console.error('加载项目失败:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId, user, updateFileContent, updateAnalysisResults, updateOutline]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  useEffect(() => {
    return () => {
      setLayoutHeader(null);
    };
  }, [setLayoutHeader]);

  const handleBackToList = useCallback(() => {
    navigate('/projects');
  }, [navigate]);

  useEffect(() => {
    if (loading || error || !project) {
      setLayoutHeader(null);
      return;
    }

    setLayoutHeader({
      content: (
        <div className="flex min-w-0 items-center justify-between gap-6 py-2">
          <div className="flex min-w-0 items-center gap-4">
            <button
              onClick={handleBackToList}
              className="inline-flex shrink-0 items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:text-slate-900"
            >
              <ArrowLeftOutlined />
              返回
            </button>

            <div className="h-5 w-px shrink-0 bg-slate-200" />

            <div className="flex min-w-0 items-center gap-3">
              <span className="truncate text-sm font-medium text-slate-500">{project.name}</span>
              <span className="text-slate-300">/</span>
              <h1 className="truncate text-[18px] font-semibold tracking-tight text-slate-900">
                标书编写工作区
              </h1>
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-3">
            <Button icon={<TeamOutlined />} onClick={() => setShowMemberSidebar(true)}>成员</Button>
            <Button icon={<PaperClipOutlined />} onClick={() => setShowMaterialDrawer(true)}>材料需求</Button>
            <Button icon={<SettingOutlined />} onClick={() => navigate(`/project/${projectId}/settings`)}>设置</Button>
            <Button icon={<HistoryOutlined />} onClick={() => setShowVersionHistory(true)}>版本历史</Button>
          </div>
        </div>
      ),
    });
  }, [
    error,
    handleBackToList,
    loading,
    navigate,
    progress,
    project,
    projectId,
    setLayoutHeader,
  ]);

  const persistAnalysisResults = useCallback(async () => {
    if (projectId && (state.projectOverview || state.techRequirements)) {
      try {
        await documentApi.saveProjectAnalysis(
          projectId,
          {
            project_overview: state.projectOverview,
            tech_requirements: state.techRequirements,
          }
        );
      } catch (error) {
        console.error('保存分析结果失败:', error);
      }
    }
  }, [projectId, state.projectOverview, state.techRequirements, token]);

  const handleStepChange = useCallback(async (targetStep: number) => {
    if (targetStep === state.currentStep) {
      return;
    }

    if (targetStep === 1 && !(analysisReady || state.currentStep > 0)) {
      return;
    }

    if (targetStep === 2 && !(outlineReady || state.currentStep > 1)) {
      return;
    }

    if (state.currentStep === 0 && targetStep > 0) {
      await persistAnalysisResults();
    }

    updateStep(targetStep);
  }, [analysisReady, outlineReady, persistAnalysisResults, state.currentStep, updateStep]);

  const handleCheckConsistency = async (chapterSummaries?: { chapter_number: string; title: string; summary: string }[]) => {
    if (!projectId) return;

    const hasValidSummaries = chapterSummaries && chapterSummaries.length >= 2;
    const summariesToUse = hasValidSummaries ? chapterSummaries : lastChapterSummaries;
    if (hasValidSummaries) {
      setLastChapterSummaries(chapterSummaries!);
    }

    if (!summariesToUse || summariesToUse.length < 2) {
      message.warning('至少需要2个有内容的章节才能进行一致性检查。请先生成章节内容。');
      return;
    }

    setIsCheckingConsistency(true);
    try {
      const result = await consistencyApi.checkConsistency(projectId, summariesToUse);
      setConsistencyResult(result);
    } catch (error: unknown) {
      console.error('一致性检查失败:', error);
      const errorMessage = getErrorMessage(error, '一致性检查失败，请重试');
      message.error(errorMessage);
    } finally {
      setIsCheckingConsistency(false);
    }
  };

  const handleOpenConsistencyPanel = (chapterSummaries?: { chapter_number: string; title: string; summary: string }[]) => {
    if (chapterSummaries && chapterSummaries.length >= 2) {
      setLastChapterSummaries(chapterSummaries);
    }
    setShowConsistencyPanel(true);
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
            projectId={projectId}
            onContinue={() => {
              void handleStepChange(1);
            }}
          />
        );
      case 1:
        return (
          <OutlineEdit
            projectOverview={state.projectOverview}
            techRequirements={state.techRequirements}
            outlineData={state.outlineData}
            onOutlineGenerated={updateOutline}
            projectId={projectId || ''}
            onContinue={() => {
              void handleStepChange(2);
            }}
          />
        );
      case 2:
        return (
          <ContentEdit
            outlineData={state.outlineData}
            selectedChapter={state.selectedChapter}
            onChapterSelect={updateSelectedChapter}
            projectId={projectId}
            onToggleComments={(chapterId) => setActiveCommentChapter(chapterId)}
            onToggleConsistency={handleOpenConsistencyPanel}
            highlightedChapters={highlightedChapters}
          />
        );
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f0f2f5' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div style={{ minHeight: '60vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f0f2f5' }}>
        <Typography.Text type="danger" style={{ marginBottom: 16 }}>{error || '项目不存在'}</Typography.Text>
        <Button type="primary" onClick={handleBackToList}>返回项目列表</Button>
      </div>
    );
  }

  return (
    <Layout style={{ minHeight: '100%', backgroundColor: '#f5f5f5' }}>
      <Content id="app-main-scroll" style={{ padding: 0, backgroundColor: '#f5f5f5' }}>
        <div style={{ maxWidth: 1360, margin: '0 auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 24 }}>
          <section className="rounded-[28px] border border-slate-200 bg-white px-5 py-4 shadow-[0_24px_50px_-40px_rgba(15,23,42,0.45)]">
            <StepBar
              steps={steps}
              currentStep={state.currentStep}
              variant="inline"
              onStepClick={(stepIndex) => {
                void handleStepChange(stepIndex);
              }}
              isStepEnabled={(stepIndex) => {
                if (stepIndex === 0) return true;
                if (stepIndex === 1) return analysisReady || state.currentStep > 0;
                if (stepIndex === 2) return outlineReady || state.currentStep > 1;
                return false;
              }}
            />
          </section>

          {renderCurrentPage()}
        </div>
      </Content>

      {/* 浮动面板 */}
      {projectId && (
        <VersionHistory
          projectId={projectId}
          isOpen={showVersionHistory}
          onClose={() => setShowVersionHistory(false)}
        />
      )}

      {projectId && (
        <MemberSidebar
          projectId={projectId}
          isOpen={showMemberSidebar}
          onClose={() => setShowMemberSidebar(false)}
        />
      )}

      <ConsistencyPanel
        isOpen={showConsistencyPanel}
        onClose={() => setShowConsistencyPanel(false)}
        result={consistencyResult}
        isLoading={isCheckingConsistency}
        onCheck={() => handleCheckConsistency()}
        onApplyFixes={async (selectedFixes) => {
          if (!state.outlineData || !projectId) return [];

          const collectChapters = (items: typeof state.outlineData.outline): { id: string; title: string }[] => {
            const result: { id: string; title: string }[] = [];
            for (const item of items) {
              result.push({ id: item.id, title: item.title });
              if (item.children) {
                result.push(...collectChapters(item.children));
              }
            }
            return result;
          };

          const allChapters = collectChapters(state.outlineData.outline);

          const findChapterId = (chapterRef: string): string | null => {
            const chapterNumMatch = chapterRef.match(/章节?(\d+)(?:\.(\d+))?/);
            if (chapterNumMatch) {
              const mainNum = chapterNumMatch[1];
              const subNum = chapterNumMatch[2];
              const targetId = subNum ? `${mainNum}.${subNum}` : mainNum;
              const found = allChapters.find(c => c.id === targetId);
              if (found) return found.id;
            }
            const exactMatch = allChapters.find(c => c.id === chapterRef);
            if (exactMatch) return exactMatch.id;
            return null;
          };

          const chapterFixes = new Map<string, { title: string; suggestions: string[] }>();

          for (const fix of selectedFixes) {
            const chapterIdA = findChapterId(fix.chapter_a);
            const chapterIdB = findChapterId(fix.chapter_b);

            if (chapterIdA) {
              const chapter = allChapters.find(c => c.id === chapterIdA);
              if (chapter) {
                const existing = chapterFixes.get(chapterIdA) || { title: chapter.title, suggestions: [] };
                existing.suggestions.push(fix.suggestion);
                chapterFixes.set(chapterIdA, existing);
              }
            }
            if (chapterIdB) {
              const chapter = allChapters.find(c => c.id === chapterIdB);
              if (chapter) {
                const existing = chapterFixes.get(chapterIdB) || { title: chapter.title, suggestions: [] };
                existing.suggestions.push(fix.suggestion);
                chapterFixes.set(chapterIdB, existing);
              }
            }
          }

          const generatedChapters = new Map<string, string>();
          const modifiedChapterIds = new Set<string>();

          for (const [chapterId, { title, suggestions }] of Array.from(chapterFixes.entries())) {
            try {
              const result = await consistencyApi.rewriteChapter(
                projectId,
                title,
                '',
                suggestions
              );
              generatedChapters.set(chapterId, result.rewritten_content);
              modifiedChapterIds.add(chapterId);
            } catch (error) {
              console.error('❌ 章节', chapterId, '生成失败:', error);
            }
          }

          const updateChapterContent = (items: typeof state.outlineData.outline): typeof state.outlineData.outline => {
            return items.map((item) => {
              const generatedContent = generatedChapters.get(item.id);
              return {
                ...item,
                content: generatedContent !== undefined ? generatedContent : item.content,
                children: item.children ? updateChapterContent(item.children) : undefined,
              };
            });
          };

          const updatedOutline = updateChapterContent(state.outlineData.outline);
          updateOutline({
            ...state.outlineData,
            outline: updatedOutline,
          });

          setHighlightedChapters(new Set(modifiedChapterIds));

          setTimeout(() => {
            setHighlightedChapters(new Set());
          }, 5000);

          return Array.from(modifiedChapterIds);
        }}
      />

      {activeCommentChapter && (
        <CommentPanel
          chapterId={activeCommentChapter}
          isOpen={!!activeCommentChapter}
          onClose={() => setActiveCommentChapter(null)}
        />
      )}
      {projectId ? (
        <MaterialRequirementDrawer
          open={showMaterialDrawer}
          projectId={projectId}
          onClose={() => setShowMaterialDrawer(false)}
        />
      ) : null}
    </Layout>
  );
};

export default ProjectWorkspace;
