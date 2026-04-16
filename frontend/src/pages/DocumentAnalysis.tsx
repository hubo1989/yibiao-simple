import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { documentApi } from '../services/api';
import { MarkdownComponentProps } from '../utils/error';
import { useAuth } from '../contexts/AuthContext';
import { draftStorage } from '../utils/draftStorage';
import { getCurrentModel, getCurrentProviderConfigId } from '../utils/modelCache';
import { consumeSseEvents } from '../utils/sse';
import { ProCard } from '@ant-design/pro-components';
import { Button, Typography, Alert, message } from 'antd';
import { InboxOutlined, FileTextOutlined, LoadingOutlined, ArrowRightOutlined } from '@ant-design/icons';

interface DocumentAnalysisProps {
  fileContent: string;
  projectOverview: string;
  techRequirements: string;
  onFileUpload: (content: string) => void;
  onAnalysisComplete: (overview: string, requirements: string) => void;
  projectId?: string;
  onContinue?: () => void;
}

// Markdown 渲染组件定义移到模块级别，避免每次 render 重新创建对象引用
const markdownComponents = {
  p: ({ children }: MarkdownComponentProps) => <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.5', margin: '0 0 1em 0' }}>{children}</p>,
  ul: ({ children }: MarkdownComponentProps) => <ul style={{ paddingLeft: 20, marginBottom: '1em' }}>{children}</ul>,
  ol: ({ children }: MarkdownComponentProps) => <ol style={{ paddingLeft: 20, marginBottom: '1em' }}>{children}</ol>,
  li: ({ children }: MarkdownComponentProps) => <li style={{ lineHeight: '1.5' }}>{children}</li>,
  h1: ({ children }: MarkdownComponentProps) => <h1 style={{ fontSize: '1.25em', fontWeight: 600, margin: '1em 0 0.5em 0' }}>{children}</h1>,
  h2: ({ children }: MarkdownComponentProps) => <h2 style={{ fontSize: '1.1em', fontWeight: 600, margin: '1em 0 0.5em 0' }}>{children}</h2>,
  h3: ({ children }: MarkdownComponentProps) => <h3 style={{ fontSize: '1em', fontWeight: 600, margin: '1em 0 0.5em 0' }}>{children}</h3>,
  strong: ({ children }: MarkdownComponentProps) => <strong style={{ fontWeight: 600 }}>{children}</strong>,
  em: ({ children }: MarkdownComponentProps) => <em style={{ fontStyle: 'italic' }}>{children}</em>,
  blockquote: ({ children }: MarkdownComponentProps) => <blockquote style={{ borderLeft: '4px solid #1677ff', paddingLeft: 16, margin: '1em 0', color: 'rgba(0, 0, 0, 0.45)' }}>{children}</blockquote>,
  code: ({ children }: MarkdownComponentProps) => <code style={{ backgroundColor: 'rgba(0, 0, 0, 0.04)', padding: '0.2em 0.4em', borderRadius: 3, fontFamily: 'monospace' }}>{children}</code>,
  table: ({ children }: MarkdownComponentProps) => <table style={{ width: '100%', borderCollapse: 'collapse', margin: '1em 0' }}>{children}</table>,
  thead: ({ children }: MarkdownComponentProps) => <thead style={{ backgroundColor: '#fafafa' }}>{children}</thead>,
  th: ({ children }: MarkdownComponentProps) => <th style={{ border: '1px solid #f0f0f0', padding: '8px 16px', textAlign: 'left', fontWeight: 600 }}>{children}</th>,
  td: ({ children }: MarkdownComponentProps) => <td style={{ border: '1px solid #f0f0f0', padding: '8px 16px' }}>{children}</td>,
  text: ({ children }: MarkdownComponentProps) => <span style={{ whiteSpace: 'pre-wrap' }}>{children}</span>,
};

const streamingComponents = {
  ...markdownComponents,
  p: ({ children }: MarkdownComponentProps) => <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.3', margin: '0 0 0.5em 0', color: '#1677ff' }}>{children}</p>,
  text: ({ children }: MarkdownComponentProps) => <span style={{ whiteSpace: 'pre-wrap', color: '#1677ff' }}>{children}</span>,
};

const DocumentAnalysis: React.FC<DocumentAnalysisProps> = ({
  fileContent,
  projectOverview,
  techRequirements,
  onFileUpload,
  onAnalysisComplete,
  projectId,
  onContinue,
}) => {
  const { token } = useAuth();
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [msg, setMsg] = useState<{ type: 'success' | 'error' | 'info' | 'warning'; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [localOverview, setLocalOverview] = useState(projectOverview);
  const [localRequirements, setLocalRequirements] = useState(techRequirements);

  const normalizeLineBreaks = (text: string) => {
    if (!text) return text;
    return text
      .replace(/\\n/g, '\n')
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n');
  };

  const [currentAnalysisStep, setCurrentAnalysisStep] = useState<'overview' | 'requirements' | null>(null);
  const [streamingOverview, setStreamingOverview] = useState('');
  const [streamingRequirements, setStreamingRequirements] = useState('');
  const canContinue = Boolean(localOverview.trim() && localRequirements.trim());

  useEffect(() => {
    setLocalOverview(projectOverview);
  }, [projectOverview]);

  useEffect(() => {
    setLocalRequirements(techRequirements);
  }, [techRequirements]);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setUploadedFile(file);
      handleFileUpload(file);
    }
  };

  const handleFileUpload = async (file: File) => {
    try {
      setUploading(true);
      setMsg(null);

      const response = await documentApi.uploadFile(file);

      if (response.data.success && response.data.file_content) {
        draftStorage.clearAll();
        setLocalOverview('');
        setLocalRequirements('');
        setStreamingOverview('');
        setStreamingRequirements('');
        setCurrentAnalysisStep(null);
        onAnalysisComplete('', '');
        onFileUpload(response.data.file_content);
        message.success(response.data.message);
      } else {
        setMsg({ type: 'error', text: response.data.message });
      }
    } catch (error: unknown) {
      const detail = (error as any)?.response?.data?.detail;
      setMsg({ type: 'error', text: detail || '文件上传失败' });
    } finally {
      setUploading(false);
    }
  };

  const handleAnalysis = async () => {
    if (!fileContent) {
      setMsg({ type: 'error', text: '请先上传文档' });
      return;
    }

    if (!token) {
      setMsg({ type: 'error', text: '请先登录' });
      return;
    }

    try {
      setAnalyzing(true);
      setMsg(null);
      setStreamingOverview('');
      setStreamingRequirements('');

      let overviewResult = '';
      let requirementsResult = '';

      const decoder = new TextDecoder();

      const processStream = async (response: Response, onChunk: (chunk: string) => void) => {
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.detail || `请求失败: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('无法读取响应流');
        }

        try {
          let pending = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              break;
            }

            pending += decoder.decode(value, { stream: true });
            const { remainder, done: isStreamDone } = consumeSseEvents(pending, (parsed) => {
              if (parsed.chunk && typeof parsed.chunk === 'string') {
                onChunk(parsed.chunk);
              }
            });
            pending = remainder;

            if (isStreamDone) {
              return;
            }
          }

          pending += decoder.decode();
          const { done: isStreamDone } = consumeSseEvents(`${pending}\n\n`, (parsed) => {
            if (parsed.chunk && typeof parsed.chunk === 'string') {
              onChunk(parsed.chunk);
            }
          });
          if (isStreamDone) {
            return;
          }
        } catch (e: unknown) {
          const errorMessage = e instanceof Error ? e.message : '连接错误，请检查网络';
          throw new Error(errorMessage);
        }
      };

      const currentModel = getCurrentModel();
      const currentProviderConfigId = getCurrentProviderConfigId();

      if (projectId) {
        if (!uploadedFile) {
          setMsg({ type: 'error', text: '请先上传招标文件' });
          setAnalyzing(false);
          return;
        }
        await documentApi.uploadToProject(projectId, uploadedFile);

        setCurrentAnalysisStep('overview');
        const overviewResponse = await documentApi.analyzeProjectStream({
          project_id: projectId,
          analysis_type: 'overview',
          model_name: currentModel || undefined,
          provider_config_id: currentProviderConfigId || undefined,
        });

        await processStream(overviewResponse as any, (chunk) => {
          overviewResult += chunk;
          setStreamingOverview(normalizeLineBreaks(overviewResult));
        });

        setLocalOverview(normalizeLineBreaks(overviewResult));

        setCurrentAnalysisStep('requirements');
        const requirementsResponse = await documentApi.analyzeProjectStream({
          project_id: projectId,
          analysis_type: 'requirements',
          model_name: currentModel || undefined,
          provider_config_id: currentProviderConfigId || undefined,
        });

        await processStream(requirementsResponse as any, (chunk) => {
          requirementsResult += chunk;
          setStreamingRequirements(normalizeLineBreaks(requirementsResult));
        });

        setLocalRequirements(normalizeLineBreaks(requirementsResult));
      } else {
        throw new Error('缺少项目ID，请从项目列表进入');
      }

      if (!overviewResult || !requirementsResult) {
        throw new Error('分析结果为空，请重试');
      }

      onAnalysisComplete(overviewResult, requirementsResult);
      message.success('标书解析完成');

      setStreamingOverview('');
      setStreamingRequirements('');
      setCurrentAnalysisStep(null);

    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : '';
      if (errorMessage?.includes('401') || errorMessage?.includes('认证') || errorMessage?.includes('Unauthorized')) {
        setMsg({ type: 'error', text: '登录已过期，请重新登录' });
      } else {
        setMsg({ type: 'error', text: errorMessage || '标书解析失败' });
      }
      setStreamingOverview('');
      setStreamingRequirements('');
      setCurrentAnalysisStep(null);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="w-full pb-10">
      <div className="grid gap-6 xl:grid-cols-2">
        <ProCard title="文档上传" headerBordered className="h-full">
          <div
            className="flex min-h-[320px] flex-col items-center justify-center"
            style={{
              border: '2px dashed #d9d9d9',
              borderRadius: 16,
              padding: '56px 28px',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'border-color 0.3s',
            }}
            onClick={() => fileInputRef.current?.click()}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#1677ff')}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#d9d9d9')}
          >
            <InboxOutlined style={{ fontSize: 48, color: '#1677ff', marginBottom: 16 }} />
            <div>
              <Typography.Text strong style={{ fontSize: 16 }}>
                {uploadedFile ? uploadedFile.name : '点击选择文件或拖拽文件到这里'}
              </Typography.Text>
            </div>
            <Typography.Text type="secondary" style={{ marginTop: 8, display: 'block' }}>
              支持 PDF 和 Word 文档，最大 10MB
            </Typography.Text>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.doc"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
          </div>

          {uploading && (
            <div style={{ marginTop: 16, textAlign: 'center' }}>
              <Typography.Text type="secondary">
                <LoadingOutlined style={{ marginRight: 8 }} />
                正在上传和处理文件...
              </Typography.Text>
            </div>
          )}
        </ProCard>

        <ProCard title="解析操作" headerBordered className="h-full">
          <div className="flex min-h-[320px] h-full flex-col gap-4">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4">
              <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
                当前建议
              </Typography.Text>
              <Typography.Text type="secondary">
                上传招标文件后先完成解析，解析结果就绪后可以直接进入目录编辑。
              </Typography.Text>
            </div>

            <div>
              <Button
                type="primary"
                size="large"
                icon={analyzing ? <LoadingOutlined /> : <FileTextOutlined />}
                onClick={handleAnalysis}
                disabled={analyzing || !uploadedFile}
              >
                {analyzing ? (
                  currentAnalysisStep === 'overview' ? '正在分析项目概述...' :
                  currentAnalysisStep === 'requirements' ? '正在分析技术评分要求...' :
                  '正在解析标书...'
                ) : '解析标书'}
              </Button>
            </div>

            {analyzing && (((currentAnalysisStep === 'overview') && streamingOverview) || ((currentAnalysisStep === 'requirements') && streamingRequirements)) && (
              <Alert
                message={currentAnalysisStep === 'overview' ? '正在分析项目概述...' : '正在分析技术评分要求...'}
                description={
                  <div style={{ maxHeight: 250, overflowY: 'auto', marginTop: 8 }}>
                    <ReactMarkdown components={streamingComponents}>
                      {currentAnalysisStep === 'overview' ? streamingOverview : streamingRequirements}
                    </ReactMarkdown>
                  </div>
                }
                type="info"
                showIcon
              />
            )}

            {msg && (
              <Alert message={msg.text} type={msg.type} showIcon />
            )}

            <div className="mt-auto rounded-2xl border border-sky-100 bg-sky-50 px-5 py-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <Typography.Text strong style={{ display: 'block', marginBottom: 6 }}>
                    {canContinue ? '解析结果已准备好' : '下一步将在这里解锁'}
                  </Typography.Text>
                  <Typography.Text type="secondary">
                    {canContinue
                      ? '现在可以进入目录编辑，继续整理章节结构。'
                      : '完成项目概述和技术评分要求解析后，可直接进入目录编辑。'}
                  </Typography.Text>
                </div>

                {canContinue && onContinue ? (
                  <Button type="primary" icon={<ArrowRightOutlined />} onClick={onContinue}>
                    进入目录编辑
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        </ProCard>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <ProCard title="项目概述" headerBordered className="h-full">
          <div className="max-h-[420px] min-h-[320px] overflow-y-auto rounded-2xl bg-slate-50 p-5">
            <ReactMarkdown components={markdownComponents}>
              {localOverview || '项目概述将在这里显示...'}
            </ReactMarkdown>
          </div>
        </ProCard>

        <ProCard title="技术评分要求" headerBordered className="h-full">
          <div className="max-h-[420px] min-h-[320px] overflow-y-auto rounded-2xl bg-slate-50 p-5">
            <ReactMarkdown components={markdownComponents}>
              {localRequirements || '技术评分要求将在这里显示...'}
            </ReactMarkdown>
          </div>
        </ProCard>
      </div>
    </div>
  );
};

export default DocumentAnalysis;
