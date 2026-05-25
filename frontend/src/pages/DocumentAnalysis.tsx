import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { documentApi } from '../services/api';
import { MarkdownComponentProps } from '../utils/error';
import { useAuth } from '../contexts/AuthContext';
import { draftStorage } from '../utils/draftStorage';
import { getCurrentModel, getCurrentProviderConfigId } from '../utils/modelCache';
import { consumeSseEvents } from '../utils/sse';
import { ProCard } from '../components/ProCompat';
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
  p: ({ children }: MarkdownComponentProps) => <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.5', margin: '0 0 1em 0', color: '#e2dfe8' }}>{children}</p>,
  ul: ({ children }: MarkdownComponentProps) => <ul style={{ paddingLeft: 20, marginBottom: '1em', color: '#c8c4d4' }}>{children}</ul>,
  ol: ({ children }: MarkdownComponentProps) => <ol style={{ paddingLeft: 20, marginBottom: '1em', color: '#c8c4d4' }}>{children}</ol>,
  li: ({ children }: MarkdownComponentProps) => <li style={{ lineHeight: '1.5' }}>{children}</li>,
  h1: ({ children }: MarkdownComponentProps) => <h1 style={{ fontSize: '1.25em', fontWeight: 600, margin: '1em 0 0.5em 0', color: '#f1f0f5' }}>{children}</h1>,
  h2: ({ children }: MarkdownComponentProps) => <h2 style={{ fontSize: '1.1em', fontWeight: 600, margin: '1em 0 0.5em 0', color: '#f1f0f5' }}>{children}</h2>,
  h3: ({ children }: MarkdownComponentProps) => <h3 style={{ fontSize: '1em', fontWeight: 600, margin: '1em 0 0.5em 0', color: '#e2dfe8' }}>{children}</h3>,
  strong: ({ children }: MarkdownComponentProps) => <strong style={{ fontWeight: 600, color: '#f1f0f5' }}>{children}</strong>,
  em: ({ children }: MarkdownComponentProps) => <em style={{ fontStyle: 'italic' }}>{children}</em>,
  blockquote: ({ children }: MarkdownComponentProps) => <blockquote style={{ borderLeft: '4px solid #7c3aed', paddingLeft: 16, margin: '1em 0', color: '#8b85a0', background: 'rgba(124,58,237,0.05)', borderRadius: '0 8px 8px 0', padding: '12px 16px' }}>{children}</blockquote>,
  code: ({ children }: MarkdownComponentProps) => <code style={{ backgroundColor: 'rgba(124,58,237,0.15)', padding: '0.2em 0.4em', borderRadius: 4, fontFamily: 'monospace', color: '#a78bfa', fontSize: '0.9em' }}>{children}</code>,
  table: ({ children }: MarkdownComponentProps) => <table style={{ width: '100%', borderCollapse: 'collapse', margin: '1em 0', color: '#c8c4d4' }}>{children}</table>,
  thead: ({ children }: MarkdownComponentProps) => <thead style={{ backgroundColor: '#231f35' }}>{children}</thead>,
  th: ({ children }: MarkdownComponentProps) => <th style={{ border: '1px solid #2a2640', padding: '8px 16px', textAlign: 'left', fontWeight: 600, color: '#f1f0f5' }}>{children}</th>,
  td: ({ children }: MarkdownComponentProps) => <td style={{ border: '1px solid #2a2640', padding: '8px 16px' }}>{children}</td>,
  text: ({ children }: MarkdownComponentProps) => <span style={{ whiteSpace: 'pre-wrap' }}>{children}</span>,
};

const streamingComponents = {
  ...markdownComponents,
  p: ({ children }: MarkdownComponentProps) => <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.3', margin: '0 0 0.5em 0', color: '#a78bfa' }}>{children}</p>,
  text: ({ children }: MarkdownComponentProps) => <span style={{ whiteSpace: 'pre-wrap', color: '#a78bfa' }}>{children}</span>,
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
        // 如果已有文件内容且未选择新文件，跳过上传步骤
        if (uploadedFile && fileContent) {
          await documentApi.uploadToProject(projectId, uploadedFile);
        } else if (!fileContent) {
          setMsg({ type: 'error', text: '请先上传招标文件' });
          setAnalyzing(false);
          return;
        }

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
            style={{
              minHeight: 320,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              border: `2px dashed ${fileContent ? '#7c3aed' : '#2a2640'}`,
              borderRadius: 16,
              padding: '56px 28px',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              background: fileContent ? 'rgba(124,58,237,0.04)' : 'transparent',
            }}
            onClick={() => fileInputRef.current?.click()}
            onMouseEnter={(e) => { if (!fileContent) e.currentTarget.style.borderColor = '#7c3aed'; }}
            onMouseLeave={(e) => { if (!fileContent) e.currentTarget.style.borderColor = '#2a2640'; }}
          >
            {fileContent ? (
              <>
                <div style={{ width: 64, height: 64, borderRadius: 16, background: 'rgba(34,197,94,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
                  <span style={{ fontSize: 32 }}>✅</span>
                </div>
                <Typography.Text strong style={{ fontSize: 16, color: '#f1f0f5' }}>
                  {uploadedFile ? uploadedFile.name : '文件已加载'}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ marginTop: 8, display: 'block', color: '#22c55e' }}>
                  文件解析完成，可以开始分析
                </Typography.Text>
              </>
            ) : (
              <>
                <InboxOutlined style={{ fontSize: 48, color: '#7c3aed', marginBottom: 16 }} />
                <div>
                  <Typography.Text strong style={{ fontSize: 16, color: '#f1f0f5' }}>
                    点击选择文件或拖拽文件到这里
                  </Typography.Text>
                </div>
                <Typography.Text type="secondary" style={{ marginTop: 8, display: 'block', color: '#8b85a0' }}>
                  支持 PDF 和 Word 文档，最大 10MB
                </Typography.Text>
              </>
            )}
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
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10, color: '#a78bfa' }}>
                <div className="ai-thinking-dots"><span /><span /><span /></div>
                <span>正在上传和处理文件...</span>
              </div>
            </div>
          )}
        </ProCard>

        <ProCard title="解析操作" headerBordered className="h-full">
          <div style={{ minHeight: 320, height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ borderRadius: 16, border: '1px solid #2a2640', background: '#1a1825', padding: '20px' }}>
              <Typography.Text strong style={{ display: 'block', marginBottom: 8, color: '#f1f0f5' }}>
                当前建议
              </Typography.Text>
              <Typography.Text type="secondary" style={{ color: '#8b85a0' }}>
                上传招标文件后先完成解析，解析结果就绪后可以直接进入目录编辑。
              </Typography.Text>
            </div>

            <div>
              <Button
                type="primary"
                size="large"
                icon={analyzing ? <LoadingOutlined /> : <FileTextOutlined />}
                onClick={handleAnalysis}
                disabled={analyzing || !fileContent}
                style={{
                  ...(analyzing ? {
                    background: 'linear-gradient(135deg, #7c3aed, #6d28d9)',
                    borderColor: '#7c3aed',
                    boxShadow: '0 4px 15px rgba(124,58,237,0.4)',
                  } : {}),
                  height: 48,
                  fontSize: 15,
                  fontWeight: 500,
                }}
              >
                {analyzing ? (
                  currentAnalysisStep === 'overview' ? '正在分析项目概述...' :
                  currentAnalysisStep === 'requirements' ? '正在分析技术评分要求...' :
                  '正在解析标书...'
                ) : '解析标书'}
              </Button>
            </div>

            {analyzing && (((currentAnalysisStep === 'overview') && streamingOverview) || ((currentAnalysisStep === 'requirements') && streamingRequirements)) && (
              <div style={{
                borderRadius: 12, border: '1px solid rgba(167,139,250,0.2)',
                background: 'rgba(167,139,250,0.05)', padding: '12px 16px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: '#a78bfa', fontSize: 13 }}>
                  <div className="ai-thinking-dots" style={{ transform: 'scale(0.7)' }}><span /><span /><span /></div>
                  {currentAnalysisStep === 'overview' ? '正在分析项目概述...' : '正在分析技术评分要求...'}
                </div>
                <div style={{ maxHeight: 250, overflowY: 'auto', marginTop: 8 }}>
                  <ReactMarkdown components={streamingComponents}>
                    {currentAnalysisStep === 'overview' ? streamingOverview : streamingRequirements}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {msg && (
              <Alert message={msg.text} type={msg.type} showIcon />
            )}

            <div style={{ marginTop: 'auto', borderRadius: 16, border: canContinue ? '1px solid rgba(34,197,94,0.3)' : '1px solid #2a2640', background: canContinue ? 'rgba(34,197,94,0.05)' : '#1a1825', padding: '20px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                <div>
                  <Typography.Text strong style={{ display: 'block', marginBottom: 6, color: '#f1f0f5' }}>
                    {canContinue ? '✅ 解析结果已准备好' : '下一步将在这里解锁'}
                  </Typography.Text>
                  <Typography.Text type="secondary" style={{ color: '#8b85a0' }}>
                    {canContinue
                      ? '现在可以进入目录编辑，继续整理章节结构。'
                      : '完成项目概述和技术评分要求解析后，可直接进入目录编辑。'}
                  </Typography.Text>
                </div>

                {canContinue && onContinue ? (
                  <Button type="primary" icon={<ArrowRightOutlined />} onClick={onContinue}
                    style={{ background: 'linear-gradient(135deg, #22c55e, #16a34a)', borderColor: '#22c55e', boxShadow: '0 4px 15px rgba(34,197,94,0.3)' }}
                  >
                    进入目录编辑 →
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        </ProCard>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <ProCard title="项目概述" headerBordered className="h-full">
          <div style={{ maxHeight: 420, minHeight: 320, overflowY: 'auto', borderRadius: 16, background: '#1a1825', padding: 20 }}>
            <ReactMarkdown components={markdownComponents}>
              {localOverview || '项目概述将在这里显示...'}
            </ReactMarkdown>
          </div>
        </ProCard>

        <ProCard title="技术评分要求" headerBordered className="h-full">
          <div style={{ maxHeight: 420, minHeight: 320, overflowY: 'auto', borderRadius: 16, background: '#1a1825', padding: 20 }}>
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
