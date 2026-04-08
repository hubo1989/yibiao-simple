import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { reviewApi, projectApi } from '../services/api';
import { getCurrentModel, getCurrentProviderConfigId } from '../utils/modelCache';
import ContentPageHeader from '../components/ContentPageHeader';
import ReviewConfig from '../components/review/ReviewConfig';
import BidFileUpload from '../components/review/BidFileUpload';
import ReviewProgress from '../components/review/ReviewProgress';
import ReviewSummaryCards from '../components/review/ReviewSummaryCards';
import ReviewIssueList from '../components/review/ReviewIssueList';
import ReviewHistoryDrawer from '../components/review/ReviewHistoryDrawer';
import type { Project } from '../types/project';
import type {
  ReviewDimension,
  ReviewSummary,
  ReviewResultResponse,
  ReviewHistoryItem,
} from '../types/review';
import { REVIEW_DIMENSION_LABELS } from '../types/review';
import {
  Typography,
  Button,
  Tag,
  message,
  Card,
  Space,
  Alert,
  Statistic,
  Spin,
  Drawer,
} from 'antd';
import {
  PlayCircleOutlined,
  DownloadOutlined,
  HistoryOutlined,
  ReloadOutlined,
} from '@ant-design/icons';

type PageStep = 'config' | 'upload' | 'reviewing' | 'report';

const consumeSseEvents = (
  buffer: string,
  onEvent: (event: any) => void,
): { remainder: string; done: boolean } => {
  const normalized = buffer.replace(/\r\n/g, '\n');
  const events = normalized.split('\n\n');
  const remainder = events.pop() ?? '';

  for (const event of events) {
    if (!event.trim()) continue;
    const data = event
      .split('\n')
      .filter((l) => l.startsWith('data: '))
      .map((l) => l.slice(6))
      .join('\n')
      .trim();
    if (!data) continue;
    if (data === '[DONE]') return { remainder: '', done: true };
    try {
      onEvent(JSON.parse(data));
    } catch {
      // ignore malformed events
    }
  }
  return { remainder, done: false };
};

const BidReview: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const { token } = useAuth();
  const navigate = useNavigate();

  // 项目信息
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  // 页面步骤
  const [step, setStep] = useState<PageStep>('config');

  // 审查配置
  const [dimensions, setDimensions] = useState<ReviewDimension[]>([
    'responsiveness', 'compliance', 'consistency',
  ]);
  const [useKnowledge, setUseKnowledge] = useState(false);

  // 上传
  const [taskId, setTaskId] = useState<string | null>(null);
  const [fileInfo, setFileInfo] = useState<{ filename: string; file_size: number; paragraph_count: number; heading_count: number } | null>(null);
  const [uploading, setUploading] = useState(false);

  // 审查执行
  const [progress, setProgress] = useState<Record<string, string>>({});
  const [reviewing, setReviewing] = useState(false);

  // 审查结果
  const [result, setResult] = useState<ReviewResultResponse | null>(null);

  // 审查历史
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyItems, setHistoryItems] = useState<ReviewHistoryItem[]>([]);

  // 结果筛选
  const [dimensionTab, setDimensionTab] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');

  // AI 修复
  const [selectedIssueIds, setSelectedIssueIds] = useState<string[]>([]);
  const [applyFixDrawerOpen, setApplyFixDrawerOpen] = useState(false);
  const [applyFixContent, setApplyFixContent] = useState('');
  const [applyFixStreaming, setApplyFixStreaming] = useState(false);

  const fetchProject = useCallback(async () => {
    if (!projectId) return;
    try {
      const data = await projectApi.get(projectId);
      setProject(data);
    } catch {
      message.error('获取项目失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const fetchHistory = useCallback(async () => {
    if (!projectId) return;
    try {
      const data = await reviewApi.getHistory(projectId);
      setHistoryItems(data.items);
    } catch {
      // silent
    }
  }, [projectId]);

  useEffect(() => {
    fetchProject();
    fetchHistory();
  }, [fetchProject, fetchHistory]);

  const loadResult = useCallback(async (tid: string) => {
    try {
      const data = await reviewApi.getResult(tid);
      setResult(data);
      setStep('report');
    } catch {
      message.error('加载审查结果失败');
    }
  }, []);

  // 前置条件校验
  const canStart = project?.file_content && project?.project_overview && project?.tech_requirements;

  // 上传投标文件
  const handleUpload = async (file: File) => {
    if (!projectId || !canStart) {
      message.error('请先完成招标文件上传和分析');
      return false;
    }
    if (!file.name.endsWith('.docx')) {
      message.error('仅支持 .docx 格式');
      return false;
    }

    setUploading(true);
    try {
      const data = await reviewApi.uploadBidFile(projectId, file, token || undefined);
      if (data.success && data.task_id) {
        setTaskId(data.task_id);
        setFileInfo(data.file_info);
        setStep('upload');
        message.success('投标文件上传成功');
      } else {
        message.error(data.message || '上传失败');
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '上传失败');
    } finally {
      setUploading(false);
    }
    return false;
  };

  // 执行审查
  const handleExecute = async () => {
    if (!taskId) return;
    setReviewing(true);
    setStep('reviewing');
    setProgress({});
    setResult(null);

    try {
      const currentModel = getCurrentModel();
      const currentProviderConfigId = getCurrentProviderConfigId();
      const response = await reviewApi.executeReview(
        {
          task_id: taskId,
          dimensions,
          scope: 'full',
          model_name: currentModel || undefined,
          provider_config_id: currentProviderConfigId || undefined,
          use_knowledge: useKnowledge,
        },
        token || undefined,
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `请求失败: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('无法读取响应流');

      const decoder = new TextDecoder();
      let pending = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        pending += decoder.decode(value, { stream: true });
        const sseResult = consumeSseEvents(pending, (event) => {
          if (event.type === 'progress') {
            setProgress((prev) => ({ ...prev, [event.dimension]: event.status }));
          } else if (event.type === 'error') {
            message.error(event.message);
          }
        });
        pending = sseResult.remainder;
        if (sseResult.done) break;
      }

      await loadResult(taskId);
      fetchHistory();
    } catch (e: any) {
      message.error(e.message || '审查执行失败');
      setStep('upload');
    } finally {
      setReviewing(false);
    }
  };

  // AI 修复流式调用
  const handleApplyFix = async () => {
    if (!taskId) return;
    setApplyFixContent('');
    setApplyFixStreaming(true);
    setApplyFixDrawerOpen(true);
    try {
      const apiBase = (window as any).__API_BASE_URL__ || '';
      const authToken = token || localStorage.getItem('access_token') || '';
      const response = await fetch(`${apiBase}/api/review/apply-fix-stream/${taskId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify({
          chapter_id: '审查修复',
          current_content: '',
          issue_ids: selectedIssueIds,
        }),
      });
      if (!response.ok) throw new Error(`请求失败: ${response.status}`);
      const reader = response.body?.getReader();
      if (!reader) throw new Error('无法读取响应流');
      let full = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = new TextDecoder().decode(value);
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') continue;
          try {
            const parsed = JSON.parse(data);
            if (parsed.status === 'streaming' && parsed.full_content) {
              full = parsed.full_content;
              setApplyFixContent(full);
            }
          } catch { /* ignore */ }
        }
      }
    } catch (e: any) {
      message.error(e.message || 'AI 修复失败');
    } finally {
      setApplyFixStreaming(false);
    }
  };

  // 导出 Word
  const handleExport = async () => {
    if (!taskId) return;
    try {
      const blob = await reviewApi.exportWord(
        { task_id: taskId, dimensions },
        token || undefined,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `审查批注_${new Date().toISOString().slice(0, 10)}.docx`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch (e: any) {
      message.error(e.message || '导出失败');
    }
  };

  // 重新审查
  const handleReset = () => {
    setResult(null);
    setTaskId(null);
    setFileInfo(null);
    setProgress({});
    setStep('config');
  };

  // 复制到剪贴板
  const copyText = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => message.success('已复制到剪贴板'),
      () => message.error('复制失败，请手动复制'),
    );
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Spin size="large" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center bg-gray-50 px-6">
        <Card style={{ textAlign: 'center', padding: 40, maxWidth: 640 }}>
          <Typography.Text type="danger">找不到该项目</Typography.Text>
        </Card>
      </div>
    );
  }

  const summary = result?.summary;

  // 构建筛选后的结果列表
  const allIssues: Array<{ dimension: string; item: any; key: string }> = [];
  if (result?.responsiveness?.items) {
    result.responsiveness.items.forEach((item, i) => {
      allIssues.push({ dimension: 'responsiveness', item, key: `resp-${i}` });
    });
  }
  if (result?.compliance?.items) {
    result.compliance.items.forEach((item, i) => {
      allIssues.push({ dimension: 'compliance', item, key: `comp-${i}` });
    });
  }
  if (result?.consistency?.contradictions) {
    result.consistency.contradictions.forEach((item, i) => {
      allIssues.push({ dimension: 'consistency', item, key: `cons-${i}` });
    });
  }

  return (
    <div className="min-h-full bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <ContentPageHeader
          onBack={() => navigate(`/project/${projectId}/workspace`)}
          eyebrow={project.name}
          title="标书审查"
          description="AI 智能审查投标文件的响应性、合规性和一致性"
          actions={
            <Space>
              {step === 'report' && (
                <>
                  <Button icon={<ReloadOutlined />} onClick={handleReset}>
                    重新审查
                  </Button>
                  <Button
                    type="primary"
                    icon={<DownloadOutlined />}
                    onClick={handleExport}
                  >
                    导出 Word
                  </Button>
                </>
              )}
              <Button icon={<HistoryOutlined />} onClick={() => setHistoryOpen(true)}>
                审查历史
              </Button>
            </Space>
          }
        />

        {/* 前置条件不满足 */}
        {!canStart && step === 'config' && (
          <Alert
            type="warning"
            message="请先完成前置步骤"
            description={
              !project.file_content
                ? '请先上传招标文件'
                : '请先完成招标文件分析（项目概述和技术评分要求）'
            }
            showIcon
            action={
              <Button onClick={() => navigate(`/project/${projectId}/workspace`)}>
                前往工作台
              </Button>
            }
          />
        )}

        {/* Step 1: 配置审查 */}
        {step === 'config' && canStart && (
          <Card title="审查配置" bordered>
            <ReviewConfig
              dimensions={dimensions}
              onDimensionsChange={setDimensions}
              useKnowledge={useKnowledge}
              onKnowledgeChange={setUseKnowledge}
            />
            <BidFileUpload uploading={uploading} onUpload={handleUpload} />
          </Card>
        )}

        {/* Step 2: 文件已上传，待审查 */}
        {step === 'upload' && (
          <Card title="投标文件已就绪" bordered>
            {fileInfo && (
              <div style={{ marginBottom: 24 }}>
                <Space size="large">
                  <Statistic title="文件名" value={fileInfo.filename} />
                  <Statistic
                    title="文件大小"
                    value={(fileInfo.file_size / 1024 / 1024).toFixed(2)}
                    suffix="MB"
                  />
                  <Statistic title="段落数" value={fileInfo.paragraph_count} />
                  <Statistic title="章节数" value={fileInfo.heading_count} />
                </Space>
              </div>
            )}
            <div style={{ marginBottom: 24 }}>
              <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
                将执行以下维度的审查：
              </Typography.Text>
              <Space>
                {dimensions.map((d) => (
                  <Tag key={d} color="blue">{REVIEW_DIMENSION_LABELS[d]}</Tag>
                ))}
              </Space>
            </div>
            <Button
              type="primary"
              size="large"
              icon={<PlayCircleOutlined />}
              onClick={handleExecute}
            >
              开始审查
            </Button>
          </Card>
        )}

        {/* Step 3: 审查进度 */}
        {step === 'reviewing' && (
          <Card title="审查执行中" bordered>
            <ReviewProgress
              dimensions={dimensions}
              progress={progress}
              reviewing={reviewing}
            />
          </Card>
        )}

        {/* Step 4: 审查报告 */}
        {step === 'report' && result && (
          <>
            {summary && <ReviewSummaryCards summary={summary} />}

            <ReviewIssueList
              dimensions={dimensions}
              allIssues={allIssues}
              dimensionTab={dimensionTab}
              onDimensionTabChange={setDimensionTab}
              severityFilter={severityFilter}
              onSeverityFilterChange={setSeverityFilter}
              onCopy={copyText}
            />

            {/* AI 修复操作栏 */}
            {result.status === 'completed' && (
              <Card style={{ marginTop: 16 }}>
                <Space wrap>
                  <Button
                    type="primary"
                    onClick={handleApplyFix}
                    loading={applyFixStreaming}
                  >
                    AI 修改（流式）
                  </Button>
                  <Button
                    icon={<DownloadOutlined />}
                    onClick={handleExport}
                  >
                    导出带批注 Word
                  </Button>
                </Space>
                {selectedIssueIds.length > 0 && (
                  <div style={{ marginTop: 8, fontSize: 12, color: '#8c8c8c' }}>
                    已选 {selectedIssueIds.length} 个问题进行修复
                    <Button size="small" type="link" onClick={() => setSelectedIssueIds([])}>
                      清空选择
                    </Button>
                  </div>
                )}
              </Card>
            )}

            {/* AI 修复结果 Drawer */}
            <Drawer
              title="AI 修改结果"
              open={applyFixDrawerOpen}
              onClose={() => setApplyFixDrawerOpen(false)}
              width={600}
              extra={
                <Button
                  size="small"
                  onClick={() => { navigator.clipboard.writeText(applyFixContent); message.success('已复制'); }}
                  disabled={!applyFixContent}
                >
                  复制内容
                </Button>
              }
            >
              {applyFixStreaming && !applyFixContent && (
                <div style={{ textAlign: 'center', padding: 32 }}>
                  <Spin tip="AI 正在生成修改内容..." />
                </div>
              )}
              {applyFixContent && (
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: 14 }}>
                  {applyFixContent}
                </div>
              )}
            </Drawer>

            {result.status === 'failed' && (
              <Alert
                type="error"
                message="审查执行失败"
                description={result.error_message || '未知错误'}
                showIcon
                style={{ marginTop: 16 }}
                action={
                  <Button onClick={handleReset}>重新审查</Button>
                }
              />
            )}
          </>
        )}

        {/* 审查历史抽屉 */}
        <ReviewHistoryDrawer
          open={historyOpen}
          onClose={() => setHistoryOpen(false)}
          items={historyItems}
          onSelectItem={(tid) => {
            setHistoryOpen(false);
            loadResult(tid);
          }}
        />
      </div>
    </div>
  );
};

export default BidReview;
