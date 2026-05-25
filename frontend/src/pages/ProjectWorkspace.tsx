/**
 * 项目工作区组件
 * 用于单个项目的标书编写流程
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { projectApi, consistencyApi, documentApi, outlineApi, bidAgentApi } from '../services/api';
import { useAppState } from '../hooks/useAppState';
import type { Project, ProjectProgress } from '../types/project';
import type { BidAgentRun, BidAgentStep } from '../services/api';
import type { ConsistencyCheckResponse } from '../types/consistency';
import { getErrorMessage } from '../utils/error';
import { consumeSseEvents } from '../utils/sse';
import StepBar from '../components/StepBar';
import VersionHistory from '../components/VersionHistory';
import MemberSidebar from '../components/MemberSidebar';
import ConsistencyPanel from '../components/ConsistencyPanel';
import CommentPanel from '../components/CommentPanel';
import MaterialRequirementDrawer from '../components/MaterialRequirementDrawer';
import DisqualificationPanel from '../components/DisqualificationPanel';
import ScoringPanel from '../components/ScoringPanel';
import { useLayoutHeader } from '../layouts/layoutHeader';
import DocumentAnalysis from './DocumentAnalysis';
import OutlineEdit from './OutlineEdit';
import ContentEdit from './ContentEdit';

import { Layout, Button, Typography, message, Tooltip } from 'antd';
import {
  TeamOutlined,
  SettingOutlined,
  HistoryOutlined,
  ArrowLeftOutlined,
  PaperClipOutlined,
  SafetyOutlined,
  TrophyOutlined,
  ThunderboltOutlined,
  ExclamationCircleOutlined,
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
  const [showDisqualificationPanel, setShowDisqualificationPanel] = useState(false);
  const [showScoringPanel, setShowScoringPanel] = useState(false);
  const [lastChapterSummaries, setLastChapterSummaries] = useState<{ chapter_number: string; title: string; summary: string }[]>([]);
  const [highlightedChapters, setHighlightedChapters] = useState<Set<string>>(new Set());
  const [agentRun, setAgentRun] = useState<BidAgentRun | null>(null);
  const [agentSteps, setAgentSteps] = useState<BidAgentStep[]>([]);
  const [agentRunning, setAgentRunning] = useState(false);

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

      try {
        const latestRun = await bidAgentApi.getLatestRun(projectId);
        setAgentRun(latestRun);
        if (latestRun) {
          const steps = await bidAgentApi.getRunSteps(latestRun.id);
          setAgentSteps(steps);
        }
      } catch {
        // Ignore bid agent history fail
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
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                borderRadius: 9999, border: '1px solid #2a2640',
                background: '#1a1825', padding: '8px 16px',
                fontSize: 13, fontWeight: 500, color: '#8b85a0',
                transition: 'all 0.2s ease',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#7c3aed'; e.currentTarget.style.color = '#f1f0f5'; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#2a2640'; e.currentTarget.style.color = '#8b85a0'; }}
            >
              <ArrowLeftOutlined />
              返回
            </button>

            <div style={{ height: 20, width: 1, background: '#2a2640' }} />

            <div className="flex min-w-0 items-center gap-3">
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 13, color: '#8b85a0' }}>{project.name}</span>
              <span style={{ color: '#2a2640' }}>/</span>
              <h1 style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 18, fontWeight: 600, letterSpacing: '-0.01em', color: '#f1f0f5' }}>
                标书编写工作区
              </h1>
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-3">
            <Button icon={<TeamOutlined />} onClick={() => setShowMemberSidebar(true)}>成员</Button>
            <Button icon={<PaperClipOutlined />} onClick={() => setShowMaterialDrawer(true)}>材料需求</Button>
            <Tooltip title="废标项检查 — 自动提取否决性条款并逐项核实">
              <Button
                icon={<SafetyOutlined />}
                onClick={() => setShowDisqualificationPanel(true)}
              >
                废标检查
              </Button>
            </Tooltip>
            <Tooltip title="评分标准 — 提取评分项并绑定章节，驱动目录和内容生成">
              <Button
                icon={<TrophyOutlined />}
                onClick={() => setShowScoringPanel(true)}
              >
                评分标准
              </Button>
            </Tooltip>
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
  }, [projectId, state.projectOverview, state.techRequirements]);

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

  const handleRunBidAgent = useCallback(async () => {
    if (!projectId) return;
    setAgentRunning(true);
    setAgentSteps([]);
    try {
      const response = await bidAgentApi.generateDraftStream(projectId, token || undefined);
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `请求失败: ${response.status}`);
      }
      const reader = response.body?.getReader();
      if (!reader) throw new Error('无法读取智能体执行流');

      const decoder = new TextDecoder();
      let pending = '';
      const finalRunRef: { current: BidAgentRun | null } = { current: null };

      const upsertStep = (incoming: BidAgentStep) => {
        setAgentSteps((previous) => {
          const exists = previous.some((item) => item.id === incoming.id);
          const next = exists
            ? previous.map((item) => item.id === incoming.id ? incoming : item)
            : [...previous, incoming];
          return next.sort((a, b) => a.order_index - b.order_index);
        });
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        pending += decoder.decode(value, { stream: true });
        const sseResult = consumeSseEvents(pending, (event) => {
          const payload = event as Record<string, any>;
          if (payload.run) {
            finalRunRef.current = payload.run as BidAgentRun;
            setAgentRun(payload.run as BidAgentRun);
          }
          if (payload.step) {
            upsertStep(payload.step as BidAgentStep);
          }
          if (payload.type === 'error') {
            throw new Error(String(payload.message || '一键标书处理失败'));
          }
        });
        pending = sseResult.remainder;
        if (sseResult.done) break;
      }

      const finalRun = finalRunRef.current;
      if (finalRun && finalRun.status === 'completed') {
        message.success(finalRun.summary || '一键标书处理完成');
        await loadProject();
      } else if (finalRun && finalRun.status === 'failed') {
        message.error(finalRun.error_message || '一键标书处理失败');
      } else {
        await loadProject();
      }
    } catch (error) {
      console.error('一键标书处理失败:', error);
      message.error(getErrorMessage(error, '一键标书处理失败'));
    } finally {
      setAgentRunning(false);
    }
  }, [loadProject, projectId, token]);

  const getAgentStepTone = (status: string): { color: string; background: string; text: string } => {
    if (status === 'completed') return { color: '#34d399', background: 'rgba(16,185,129,0.12)', text: '已完成' };
    if (status === 'failed') return { color: '#f87171', background: 'rgba(239,68,68,0.12)', text: '失败' };
    if (status === 'running') return { color: '#60a5fa', background: 'rgba(96,165,250,0.12)', text: '执行中' };
    if (status === 'skipped') return { color: '#a78bfa', background: 'rgba(167,139,250,0.12)', text: '已跳过' };
    return { color: '#8b85a0', background: 'rgba(139,133,160,0.12)', text: '待执行' };
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
      <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#0f0d15' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
          <div className="ai-thinking-dots" style={{ transform: 'scale(2.5)' }}>
            <span /><span /><span />
          </div>
          <span style={{ color: '#8b85a0', fontSize: 14, letterSpacing: 1 }}>正在加载工作区...</span>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div style={{ minHeight: '60vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backgroundColor: '#0f0d15', gap: 16 }}>
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(239,68,68,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <ExclamationCircleOutlined style={{ fontSize: 28, color: '#f87171' }} />
        </div>
        <Typography.Text type="danger" style={{ marginBottom: 8, fontSize: 15 }}>{error || '项目不存在'}</Typography.Text>
        <Button type="primary" onClick={handleBackToList} icon={<ArrowLeftOutlined />}>返回项目列表</Button>
      </div>
    );
  }

  return (
    <Layout style={{ minHeight: '100%', backgroundColor: '#0f0d15' }}>
      <Content id="app-main-scroll" style={{ padding: 0, backgroundColor: '#0f0d15' }}>
        <div style={{ maxWidth: 1360, margin: '0 auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 24 }}>
          <section className="rounded-[28px] border" style={{ borderColor: '#2a2640', background: '#1a1825', padding: '16px 20px', boxShadow: '0 24px 50px -40px rgba(124,58,237,0.25)' }}>
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

          <section className="rounded-[28px] border" style={{ borderColor: '#2a2640', background: '#1a1825', padding: 20, boxShadow: '0 24px 50px -40px rgba(9,164,250,0.25)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 16, alignItems: 'center' }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                  <span style={{ display: 'grid', placeItems: 'center', width: 34, height: 34, borderRadius: 12, background: 'rgba(9,164,250,0.12)', color: '#38bdf8' }}>
                    <ThunderboltOutlined />
                  </span>
                  <Typography.Title level={4} style={{ margin: 0, color: '#f1f0f5' }}>一键标书处理</Typography.Title>
                </div>
                <Typography.Text style={{ color: '#9b95ad' }}>
                  串行执行招标文件分析、目录生成、响应矩阵、正文生成、质量检查和导出前门禁。已有数据的步骤会自动跳过。
                </Typography.Text>
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                <Button
                  type="primary"
                  icon={<ThunderboltOutlined />}
                  loading={agentRunning}
                  onClick={() => void handleRunBidAgent()}
                >
                  {agentRunning ? '处理中...' : '一键生成标书'}
                </Button>
                <Button onClick={() => navigate(`/project/${projectId}/review`)}>
                  评审现有标书
                </Button>
              </div>
            </div>

            {(agentRun || agentSteps.length > 0) && (
              <div style={{ marginTop: 16, display: 'grid', gap: 10 }}>
                {agentRun && (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 12px', borderRadius: 14, background: '#23202f', color: '#c8c4d4' }}>
                    <span>运行状态：{agentRun.summary || agentRun.status}</span>
                    <strong style={{ color: '#38bdf8' }}>{agentRun.progress}%</strong>
                  </div>
                )}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
                  {agentSteps.map((step) => {
                    const tone = getAgentStepTone(step.status);
                    return (
                      <div key={step.id} style={{ display: 'grid', gap: 8, padding: 12, border: '1px solid #2a2640', borderRadius: 14, background: '#14121d' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center' }}>
                          <strong style={{ color: '#f1f0f5', fontSize: 13 }}>{step.order_index}. {step.step_name}</strong>
                          <span style={{ padding: '3px 8px', borderRadius: 999, background: tone.background, color: tone.color, fontSize: 12, fontWeight: 700 }}>{tone.text}</span>
                        </div>
                        <Typography.Text style={{ color: step.status === 'failed' ? '#f87171' : '#8b85a0', fontSize: 12 }}>
                          {step.error_message || step.summary || '等待执行'}
                        </Typography.Text>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
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

      {projectId && (
        <DisqualificationPanel
          projectId={projectId}
          isOpen={showDisqualificationPanel}
          onClose={() => setShowDisqualificationPanel(false)}
        />
      )}
      {projectId && (
        <ScoringPanel
          projectId={projectId}
          isOpen={showScoringPanel}
          onClose={() => setShowScoringPanel(false)}
        />
      )}
    </Layout>
  );
};

export default ProjectWorkspace;
