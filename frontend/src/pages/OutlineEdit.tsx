import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { OutlineData, OutlineItem } from '../types';
import { outlineApi, expandApi, consistencyApi, scoringApi } from '../services/api';
import type { ScoringCoverageResponse } from '../services/api';
import { getErrorMessage } from '../utils/error';
import { consumeSseEvents } from '../utils/sse';
import { useAuth } from '../contexts/AuthContext';
import ChapterStatusBadge from '../components/ChapterStatusBadge';
import RatingChecklistModal from '../components/outline-edit/RatingChecklistModal';
import OutlineEditModal from '../components/outline-edit/OutlineEditModal';
import type { ChapterStatus } from '../types/chapter';
import type { RatingChecklistResponse } from '../types/bid';
import { getCurrentModel, getCurrentProviderConfigId } from '../utils/modelCache';
import { ProCard } from '@ant-design/pro-components';
import { Button, Space, Upload, Alert, message, Typography, Tree, Spin, Tag, Modal } from 'antd';
import {
  PlusOutlined,
  UploadOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  EditOutlined,
  DeleteOutlined,
  ArrowRightOutlined,
  FolderOpenOutlined,
  NodeExpandOutlined,
  CompressOutlined,
  OrderedListOutlined,
  BranchesOutlined,
  CheckCircleFilled
} from '@ant-design/icons';
import type { DataNode } from 'antd/es/tree';

interface OutlineEditProps {
  projectOverview: string;
  techRequirements: string;
  outlineData: OutlineData | null;
  onOutlineGenerated: (outline: OutlineData) => void;
  projectId: string;
  onContinue?: () => void;
}

const OutlineEdit: React.FC<OutlineEditProps> = ({
  projectOverview,
  techRequirements,
  outlineData,
  onOutlineGenerated,
  projectId,
  onContinue,
}) => {
  const { token } = useAuth();
  const [generatingL1, setGeneratingL1] = useState(false);
  const [generatingL2L3, setGeneratingL2L3] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [msg, setMsg] = useState<{ type: 'success' | 'error' | 'warning' | 'info'; text: string } | null>(null);
  const [streamingContent, setStreamingContent] = useState('');
  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [expandFile, setExpandFile] = useState<File | null>(null);
  const [uploadedExpand, setUploadedExpand] = useState(false);
  const [streamingStageLabel, setStreamingStageLabel] = useState('');
  const [showRatingChecklist, setShowRatingChecklist] = useState(false);
  const [isLoadingRatingChecklist, setIsLoadingRatingChecklist] = useState(false);
  const [ratingChecklist, setRatingChecklist] = useState<RatingChecklistResponse | null>(null);
  const [scoringCoverage, setScoringCoverage] = useState<ScoringCoverageResponse | null>(null);

  const outlineStats = useMemo(() => {
    const stats = {
      total: 0,
      topLevel: outlineData?.outline?.length || 0,
      generated: 0,
      leaf: 0,
    };

    const walk = (items: OutlineItem[]) => {
      items.forEach((item) => {
        stats.total += 1;
        if (item.status === 'generated' || item.content || (item.children && item.children.length > 0)) {
          stats.generated += 1;
        }
        if (!item.children || item.children.length === 0) {
          stats.leaf += 1;
        } else {
          walk(item.children);
        }
      });
    };

    if (outlineData?.outline?.length) {
      walk(outlineData.outline);
    }

    return stats;
  }, [outlineData]);

  const topLevelPreview = useMemo(
    () => (outlineData?.outline || []).slice(0, 4),
    [outlineData]
  );

  const hasOutline = Boolean(outlineData?.outline?.length);
  const canContinue = hasOutline && Boolean(onContinue);
  const isBusy = generatingL1 || generatingL2L3;

  const fetchRatingChecklist = async () => {
    if (!projectId) {
      message.warning('缺少项目 ID，无法生成评分响应清单');
      return;
    }

    setIsLoadingRatingChecklist(true);
    try {
      const result = await consistencyApi.generateRatingChecklist(projectId);
      setRatingChecklist(result);
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '评分响应清单生成失败，请重试'));
    } finally {
      setIsLoadingRatingChecklist(false);
    }
  };

  const handleOpenRatingChecklist = () => {
    setShowRatingChecklist(true);
    if (!ratingChecklist && !isLoadingRatingChecklist) {
      void fetchRatingChecklist();
    }
  };

  const collectOutlineIds = (items: OutlineItem[]): Set<string> => {
    const ids = new Set<string>();
    const walk = (nodes: OutlineItem[]) => {
      nodes.forEach((node) => {
        ids.add(node.id);
        if (node.children?.length) {
          walk(node.children);
        }
      });
    };
    walk(items);
    return ids;
  };

  useEffect(() => {
    if (outlineData?.outline?.length && expandedItems.size === 0) {
      setExpandedItems(collectOutlineIds(outlineData.outline));
    }
  }, [expandedItems.size, outlineData]);

  // 加载评分标准覆盖率（静默）
  useEffect(() => {
    if (!projectId) return;
    scoringApi.list(projectId).then(items => {
      if (items.length > 0) {
        return scoringApi.coverage(projectId).then(setScoringCoverage);
      }
    }).catch(() => {/* 静默忽略 */});
  }, [projectId]);

  const handleExpandUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setUploadedExpand(true);
      setMsg(null);

      const response = await expandApi.uploadExpandFile(file);
      const data = response.data;

      if (data.success) {
        setExpandFile(file);
        message.success(`方案扩写文件上传成功：${file.name}`);
      } else {
        throw new Error(data.message || '文件上传失败');
      }
    } catch (error: unknown) {
      const err = error as any;
      const responseMessage = err?.response?.data?.message;
      const errorMessage = error instanceof Error ? error.message : '';
      setMsg({ type: 'error', text: responseMessage || errorMessage || '文件上传失败' });
    } finally {
      // NOTE: keeping uploadedExpand state active to disable further uploads 
    }
  };

  const handleGenerateL1Outline = async () => {
    if (!projectOverview || !techRequirements) {
      setMsg({ type: 'error', text: '请先完成文档分析' });
      return;
    }

    try {
      setGeneratingL1(true);
      setMsg(null);
      setStreamingContent('');
      setStreamingStageLabel('正在生成一级目录');

      if (!projectId) {
        throw new Error('缺少项目ID，请从项目列表进入');
      }

      const currentModel = getCurrentModel();
      const currentProviderConfigId = getCurrentProviderConfigId();
      const response = await outlineApi.generateProjectOutlineL1Stream({
        project_id: projectId,
        model_name: currentModel || undefined,
        provider_config_id: currentProviderConfigId || undefined,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error((error as { detail?: string }).detail || `请求失败: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法读取响应流');
      }

      let result = '';
      const decoder = new TextDecoder();
      let pending = '';
      const appendOutlineChunk = (parsed: { chunk?: string }) => {
        if (parsed.chunk) {
          result += parsed.chunk;
          setStreamingContent(result);
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        pending += decoder.decode(value, { stream: true });
        const { remainder, done: streamDone } = consumeSseEvents(pending, appendOutlineChunk);
        pending = remainder;

        if (streamDone) {
          break;
        }
      }

      pending += decoder.decode();
      consumeSseEvents(`${pending}\n\n`, appendOutlineChunk);

      try {
        let cleanResult = result.trim();
        if (cleanResult.includes('```json')) {
          const jsonMatch = cleanResult.match(/```json\s*([\s\S]*?)\s*```/);
          if (jsonMatch) {
            cleanResult = jsonMatch[1];
          }
        } else if (cleanResult.includes('```')) {
          const jsonMatch = cleanResult.match(/```\s*([\s\S]*?)\s*```/);
          if (jsonMatch) {
            cleanResult = jsonMatch[1];
          }
        }
        
        const outlineJson = JSON.parse(cleanResult);
        // AI 可能返回 [{...}, ...] 数组或 {outline: [...]} 对象
        const rawItems: unknown[] = Array.isArray(outlineJson)
          ? outlineJson
          : (outlineJson.outline ?? []);
        // AI prompt 返回 {rating_item, new_title, chapter_role, avoid_overlap}
        // 前端 OutlineItem 需要 {id, title, description, rating_item, chapter_role, avoid_overlap}
        const normalizedItems: OutlineItem[] = rawItems.map((raw: any, idx: number) => ({
          id: raw.id ?? String(idx + 1),
          title: raw.title ?? raw.new_title ?? raw.rating_item ?? '',
          description: raw.description ?? raw.chapter_role ?? '',
          rating_item: raw.rating_item,
          chapter_role: raw.chapter_role,
          avoid_overlap: raw.avoid_overlap,
          children: raw.children,
        }));
        const outlineData: OutlineData = { outline: normalizedItems };
        onOutlineGenerated(outlineData);
        message.success('一级目录生成完成');
        setStreamingContent('');

        const allIds = new Set<string>();
        const collectIds = (items: OutlineItem[]) => {
          items.forEach(item => {
            allIds.add(item.id);
            if (item.children) {
              collectIds(item.children);
            }
          });
        };
        collectIds(outlineData.outline || []);
        setExpandedItems(allIds);

      } catch (parseError) {
        throw new Error('解析一级目录结构失败');
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : '一级目录生成失败';
      setMsg({ type: 'error', text: errorMessage });
      setStreamingContent('');
    } finally {
      setGeneratingL1(false);
      setStreamingStageLabel('');
    }
  };

  const handleGenerateL2L3Outline = async () => {
    if (!projectOverview || !techRequirements) {
      setMsg({ type: 'error', text: '请先完成文档分析' });
      return;
    }

    if (!outlineData?.outline?.length) {
      setMsg({ type: 'error', text: '请先生成一级目录' });
      return;
    }

    try {
      setGeneratingL2L3(true);
      setMsg(null);
      setStreamingContent('');
      setStreamingStageLabel('正在生成二三级目录');

      if (!projectId) {
        throw new Error('缺少项目ID，请从项目列表进入');
      }

      const currentModel = getCurrentModel();
      const currentProviderConfigId = getCurrentProviderConfigId();
      const response = await outlineApi.generateProjectOutlineL2L3Stream({
        project_id: projectId,
        model_name: currentModel || undefined,
        provider_config_id: currentProviderConfigId || undefined,
        outline_data: outlineData,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error((error as { detail?: string }).detail || `请求失败: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法读取响应流');
      }

      const decoder = new TextDecoder();
      let pending = '';
      let updatedOutline = outlineData ? [...outlineData.outline] : [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        pending += decoder.decode(value, { stream: true });
        const { remainder, done: streamDone } = consumeSseEvents(pending, (parsed) => {
          if (parsed.type === 'chapter') {
            const chapterIndex = parsed.index as number;
            if (chapterIndex < updatedOutline.length) {
              updatedOutline[chapterIndex] = {
                ...updatedOutline[chapterIndex],
                children: (parsed.data as any)?.children || [],
                status: 'generated'
              };
            } else {
              updatedOutline.push({
                ...(parsed.data as any),
                status: 'generated'
              });
            }

            const tempOutline = { outline: updatedOutline };
            onOutlineGenerated(tempOutline);
            setStreamingContent(`正在生成第 ${(parsed.index as number) + 1}/${parsed.total} 章...`);
          }

          if (parsed.type === 'complete') {
            onOutlineGenerated(parsed.data as OutlineData);
            setStreamingContent('');
          }

          if (parsed.error) {
            throw new Error((parsed.message as string) || '生成失败');
          }
        });
        pending = remainder;

        if (streamDone) {
          break;
        }
      }

      if (updatedOutline.length > 0) {
        const outlineJson = { outline: updatedOutline };
        onOutlineGenerated(outlineJson);
        message.success('二三级目录生成完成');

        const allIds = new Set<string>();
        const collectIds = (items: OutlineItem[]) => {
          items.forEach(item => {
            allIds.add(item.id);
            if (item.children) {
              collectIds(item.children);
            }
          });
        };
        collectIds(outlineJson.outline || []);
        setExpandedItems(allIds);
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : '二三级目录生成失败';
      setMsg({ type: 'error', text: errorMessage });
      setStreamingContent('');
    } finally {
      setGeneratingL2L3(false);
      setStreamingStageLabel('');
    }
  };

  const startEditing = (item: OutlineItem) => {
    setEditingItem(item.id);
    setEditTitle(item.title);
    setEditDescription(item.description);
  };

  const cancelEditing = () => {
    setEditingItem(null);
    setEditTitle('');
    setEditDescription('');
  };

  const saveEdit = () => {
    if (!outlineData || !editingItem) return;

    const updateItem = (items: OutlineItem[]): OutlineItem[] => {
      return items.map(item => {
        if (item.id === editingItem) {
          return {
            ...item,
            title: editTitle.trim(),
            description: editDescription.trim()
          };
        }
        if (item.children) {
          return {
            ...item,
            children: updateItem(item.children)
          };
        }
        return item;
      });
    };

    const updatedData = {
      ...outlineData,
      outline: updateItem(outlineData.outline)
    };

    onOutlineGenerated(updatedData);
    cancelEditing();
    message.success('目录项更新成功');
  };

  const reorderItems = (items: OutlineItem[], parentPrefix: string = ''): OutlineItem[] => {
    return items.map((item, index) => {
      const newId = parentPrefix ? `${parentPrefix}.${index + 1}` : `${index + 1}`;
      return {
        ...item,
        id: newId,
        children: item.children ? reorderItems(item.children, newId) : undefined
      };
    });
  };

  const deleteItem = (itemId: string) => {
    if (!outlineData) return;

    if (!window.confirm('确定要删除这个目录项吗？')) return;

    const deleteFromItems = (items: OutlineItem[]): OutlineItem[] => {
      return items.filter(item => {
        if (item.id === itemId) return false;
        if (item.children) {
          item.children = deleteFromItems(item.children);
        }
        return true;
      });
    };

    const filteredItems = deleteFromItems(outlineData.outline);
    const reorderedItems = reorderItems(filteredItems);

    const updatedData = {
      ...outlineData,
      outline: reorderedItems
    };

    onOutlineGenerated(updatedData);
    message.success('目录项删除成功');
  };

  const addChildItem = (parentId: string) => {
    if (!outlineData) return;

    const findParentAndGetNextId = (items: OutlineItem[], targetParentId: string): string | null => {
      for (const item of items) {
        if (item.id === targetParentId) {
          const existingChildren = item.children || [];
          let maxChildNum = 0;
          
          existingChildren.forEach(child => {
            const childIdParts = child.id.split('.');
            const lastPart = childIdParts[childIdParts.length - 1];
            const num = parseInt(lastPart);
            if (!isNaN(num)) {
              maxChildNum = Math.max(maxChildNum, num);
            }
          });
          
          return `${parentId}.${maxChildNum + 1}`;
        }
        
        if (item.children) {
          const result = findParentAndGetNextId(item.children, targetParentId);
          if (result) return result;
        }
      }
      return null;
    };

    const newId = findParentAndGetNextId(outlineData.outline, parentId) || `${parentId}.1`;
    const newItem: OutlineItem = {
      id: newId,
      title: '新目录项',
      description: '请编辑描述'
    };

    const addToItems = (items: OutlineItem[]): OutlineItem[] => {
      return items.map(item => {
        if (item.id === parentId) {
          return {
            ...item,
            children: [...(item.children || []), newItem]
          };
        }
        if (item.children) {
          return {
            ...item,
            children: addToItems(item.children)
          };
        }
        return item;
      });
    };

    const updatedData = {
      ...outlineData,
      outline: addToItems(outlineData.outline)
    };

    onOutlineGenerated(updatedData);
    
    setExpandedItems(prev => {
      const newSet = new Set(prev);
      newSet.add(parentId);
      return newSet;
    });
    
    setTimeout(() => {
      startEditing(newItem);
    }, 100);
    
    message.success('子目录添加成功');
  };

  const addRootItem = () => {
    if (!outlineData) return;

    let maxRootNum = 0;
    outlineData.outline.forEach(item => {
      const idParts = item.id.split('.');
      const firstPart = idParts[0];
      const num = parseInt(firstPart);
      if (!isNaN(num)) {
        maxRootNum = Math.max(maxRootNum, num);
      }
    });

    const newId = `${maxRootNum + 1}`;
    const newItem: OutlineItem = {
      id: newId,
      title: '新目录项',
      description: '请编辑描述'
    };

    const updatedData = {
      ...outlineData,
      outline: [...outlineData.outline, newItem]
    };

    onOutlineGenerated(updatedData);
    
    setTimeout(() => {
      startEditing(newItem);
    }, 100);
    
    message.success('目录项添加成功');
  };

  const convertToTreeData = (items: OutlineItem[]): DataNode[] => {
    return items.map(item => {
      const isLeaf = !item.children || item.children.length === 0;
      return {
        key: item.id,
        title: (
          <div className="outline-tree-node group flex w-full items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-sky-200 hover:bg-sky-50/30">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Typography.Text strong>{`${item.id} ${item.title}`}</Typography.Text>
                <ChapterStatusBadge
                  status={(
                    item.status ||
                    (item.content ? 'generated' :
                     (item.children && item.children.length > 0 ? 'generated' : 'pending'))
                  ) as ChapterStatus}
                  size="sm"
                />
                {isLeaf ? <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">叶子节点</span> : null}
              </div>
              <Typography.Text type="secondary" className="mt-1 block">
                {item.description || '暂无描述'}
              </Typography.Text>
            </div>

            <Space className="outline-tree-actions shrink-0" style={{ visibility: editingItem === item.id ? 'hidden' : undefined }}>
              <Button type="text" icon={<EditOutlined />} size="small" onClick={(e) => { e.stopPropagation(); startEditing(item); }} title="编辑" />
              <Button type="text" icon={<PlusOutlined />} size="small" onClick={(e) => { e.stopPropagation(); addChildItem(item.id); }} title="添加子目录" style={{ color: '#16a34a' }} />
              <Button type="text" danger icon={<DeleteOutlined />} size="small" onClick={(e) => { e.stopPropagation(); deleteItem(item.id); }} title="删除" />
            </Space>
          </div>
        ),
        children: item.children ? convertToTreeData(item.children) : undefined,
      };
    });
  };

  const treeData = outlineData?.outline ? convertToTreeData(outlineData.outline) : [];

  return (
    <div className="w-full pb-16">
      <style>{`
        .outline-tree-node:hover .outline-tree-actions {
          visibility: visible !important;
        }
        .outline-tree-actions {
          visibility: hidden;
        }
        .outline-tree-panel .ant-tree-list-holder-inner > .ant-tree-treenode {
          padding: 6px 0;
        }
        .outline-tree-panel .ant-tree-indent-unit {
          width: 18px;
        }
      `}</style>

      {/* 评分标准提示条 */}
      {scoringCoverage && scoringCoverage.total > 0 && (
        <Alert
          style={{ marginBottom: 16, borderRadius: 10 }}
          type="info"
          showIcon
          message={
            <span>
              已加载 <strong>{scoringCoverage.total}</strong> 个评分项（总分{' '}
              <strong>{scoringCoverage.total_score}</strong> 分），生成目录时将自动参考评分权重。
              {scoringCoverage.unbound > 0 && (
                <span style={{ marginLeft: 8, color: '#faad14' }}>
                  ⚠ 还有 {scoringCoverage.unbound} 项未绑定章节
                </span>
              )}
            </span>
          }
        />
      )}

      <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <ProCard
          title="目录生成流程"
          subTitle="按顺序补充资料、生成目录并进入正文写作。"
          headerBordered
          className="h-full"
        >
          <div className="flex flex-col gap-4">
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-sm font-semibold text-emerald-700">
                  1
                </span>
                <div className="min-w-0 flex-1">
                  <Typography.Text strong className="block">补充技术方案</Typography.Text>
                  <Typography.Text type="secondary" className="mt-1 block">
                    可选上传现有方案，帮助目录生成更贴近你的投标材料。
                  </Typography.Text>
                  <div className="mt-4">
                    <Upload
                      accept=".pdf,.doc,.docx"
                      showUploadList={false}
                      customRequest={({ file }) => handleExpandUpload({ target: { files: [file] } } as any)}
                      disabled={uploadedExpand || isBusy}
                    >
                      <Button
                        size="large"
                        icon={uploadedExpand ? <CheckCircleOutlined /> : <UploadOutlined />}
                        disabled={uploadedExpand || isBusy}
                      >
                        {uploadedExpand ? '已上传方案扩写' : '上传补充文件'}
                      </Button>
                    </Upload>
                  </div>
                  {expandFile ? (
                    <div className="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                      已上传：{expandFile.name}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-sky-100 text-sm font-semibold text-sky-700">
                  2
                </span>
                <div className="min-w-0 flex-1">
                  <Typography.Text strong className="block">生成一级目录</Typography.Text>
                  <Typography.Text type="secondary" className="mt-1 block">
                    先搭出章节主骨架，确认投标结构和核心模块。
                  </Typography.Text>
                  <div className="mt-4">
                    <Button
                      type="primary"
                      size="large"
                      onClick={handleGenerateL1Outline}
                      disabled={isBusy || !projectOverview || !techRequirements}
                      icon={generatingL1 ? <LoadingOutlined /> : <OrderedListOutlined />}
                    >
                      {generatingL1 ? '正在生成一级目录...' : '开始生成'}
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-violet-100 text-sm font-semibold text-violet-700">
                  3
                </span>
                <div className="min-w-0 flex-1">
                  <Typography.Text strong className="block">生成二三级目录</Typography.Text>
                  <Typography.Text type="secondary" className="mt-1 block">
                    在一级目录基础上细化章节层级，形成可直接写作的完整结构。
                  </Typography.Text>
                  <div className="mt-4">
                    <Button
                      size="large"
                      onClick={handleGenerateL2L3Outline}
                      disabled={isBusy || !projectOverview || !techRequirements || !hasOutline}
                      icon={generatingL2L3 ? <LoadingOutlined /> : <BranchesOutlined />}
                      className="!border-violet-200 !text-violet-700 hover:!border-violet-300 hover:!text-violet-800"
                    >
                      {generatingL2L3 ? '正在细化目录...' : '继续细化'}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </ProCard>

        <div className="flex flex-col gap-6">
          <ProCard
            title="目录状态总览"
            subTitle="这里汇总当前结构、生成进度和下一步入口。"
            headerBordered
            className="h-full"
            extra={(
              <Button onClick={handleOpenRatingChecklist} disabled={!projectId}>
                评分响应清单
              </Button>
            )}
          >
            <div className="grid gap-4 md:grid-cols-4">
              <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
                <Typography.Text type="secondary">一级章节</Typography.Text>
                <div className="mt-2 text-3xl font-semibold text-slate-900">{outlineStats.topLevel}</div>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
                <Typography.Text type="secondary">总目录项</Typography.Text>
                <div className="mt-2 text-3xl font-semibold text-slate-900">{outlineStats.total}</div>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
                <Typography.Text type="secondary">已成型节点</Typography.Text>
                <div className="mt-2 text-3xl font-semibold text-slate-900">{outlineStats.generated}</div>
              </div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
                <Typography.Text type="secondary">可写章节</Typography.Text>
                <div className="mt-2 text-3xl font-semibold text-slate-900">{outlineStats.leaf}</div>
              </div>
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
              <div className="rounded-3xl border border-slate-200 bg-white px-5 py-5">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <Typography.Text strong className="block">当前目录预览</Typography.Text>
                    <Typography.Text type="secondary">
                      先确认一级结构，再决定是否继续展开细分章节。
                    </Typography.Text>
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
                    {hasOutline ? '已生成结构' : '尚未生成'}
                  </span>
                </div>

                {topLevelPreview.length > 0 ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    {topLevelPreview.map((item) => (
                      <div key={item.id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-500">
                            {item.id}
                          </span>
                          <Typography.Text strong>{item.title}</Typography.Text>
                        </div>
                        <Typography.Text type="secondary" className="mt-2 block">
                          {item.description || '生成后可继续补充说明。'}
                        </Typography.Text>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
                    <FolderOpenOutlined className="text-2xl text-slate-400" />
                    <Typography.Text className="mt-3 block text-base font-medium text-slate-700">
                      先生成一级目录，结构会在这里展开
                    </Typography.Text>
                    <Typography.Text type="secondary" className="mt-2 block">
                      目录生成完成后，你可以直接在下方树形结构里继续编辑和补充。
                    </Typography.Text>
                  </div>
                )}
              </div>

              <div className="rounded-[28px] border border-sky-100 bg-[linear-gradient(180deg,#f3f9ff_0%,#eef7ff_100%)] px-5 py-5">
                <Typography.Text strong className="block text-slate-900">下一步入口</Typography.Text>
                <Typography.Text type="secondary" className="mt-2 block">
                  目录结构确认后，直接进入正文编辑。步骤导航也可以随时切换。
                </Typography.Text>

                <div className="mt-5 flex flex-col gap-3">
                  <div className="rounded-2xl bg-white/80 px-4 py-3">
                    <Typography.Text strong className="block">
                      {canContinue ? '目录结构已可用于写作' : '正文编辑暂未解锁'}
                    </Typography.Text>
                    <Typography.Text type="secondary" className="mt-1 block">
                      {canContinue
                        ? '继续写章节正文，系统会沿用当前 Provider 和模型设置。'
                        : '至少生成一级目录后，再进入正文编辑会更顺畅。'}
                    </Typography.Text>
                  </div>

                  {canContinue ? (
                    <Button type="primary" size="large" icon={<ArrowRightOutlined />} onClick={onContinue}>
                      进入正文编辑
                    </Button>
                  ) : (
                    <Button size="large" disabled icon={<ArrowRightOutlined />}>
                      完成目录生成后可进入
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {!projectOverview && !techRequirements ? (
              <Alert
                className="mt-5"
                message="请先在“标书解析”步骤完成文档分析，再生成目录。"
                type="warning"
                showIcon
              />
            ) : null}

            {(isBusy && streamingContent) ? (
              <div className="mt-5 rounded-3xl border border-sky-200 bg-sky-50 px-5 py-4">
                <div className="flex items-center gap-2 text-sm font-medium text-sky-700">
                  <CheckCircleFilled />
                  {streamingStageLabel || '正在生成目录'}
                </div>
                <pre className="mt-3 max-h-[220px] overflow-y-auto whitespace-pre-wrap break-words text-sm leading-6 text-sky-900">
                  {streamingContent}
                </pre>
              </div>
            ) : null}

            {msg ? (
              <Alert className="mt-5" message={msg.text} type={msg.type} showIcon />
            ) : null}
          </ProCard>

          <ProCard
            title="目录结构与编辑"
            subTitle="生成后可直接增删目录项、修改标题和说明。"
            headerBordered
            extra={
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  icon={<NodeExpandOutlined />}
                  onClick={() => setExpandedItems(outlineData?.outline ? collectOutlineIds(outlineData.outline) : new Set())}
                  disabled={!hasOutline}
                >
                  展开全部
                </Button>
                <Button icon={<CompressOutlined />} onClick={() => setExpandedItems(new Set())} disabled={!hasOutline}>
                  收起全部
                </Button>
                <Button type="primary" icon={<PlusOutlined />} onClick={addRootItem} disabled={!hasOutline}>
                  添加目录项
                </Button>
              </div>
            }
          >
            {hasOutline ? (
              <div className="outline-tree-panel max-h-[720px] overflow-y-auto rounded-[28px] border border-slate-200 bg-slate-50 p-4">
                <Tree
                  treeData={treeData}
                  defaultExpandAll
                  expandedKeys={Array.from(expandedItems)}
                  onExpand={(keys) => setExpandedItems(new Set(keys as string[]))}
                  blockNode
                  selectable={false}
                  showLine={{ showLeafIcon: false }}
                />
              </div>
            ) : (
              <div className="rounded-[28px] border border-dashed border-slate-300 bg-slate-50 px-6 py-16 text-center">
                <OrderedListOutlined className="text-3xl text-slate-400" />
                <Typography.Text className="mt-3 block text-base font-medium text-slate-700">
                  目录结构还没有生成
                </Typography.Text>
                <Typography.Text type="secondary" className="mt-2 block">
                  先在左侧按顺序生成目录，完成后这里会变成可编辑的结构树。
                </Typography.Text>
                <div className="mt-5">
                  <Button
                    type="primary"
                    onClick={handleGenerateL1Outline}
                    disabled={isBusy || !projectOverview || !techRequirements}
                    icon={generatingL1 ? <LoadingOutlined /> : <OrderedListOutlined />}
                  >
                    从一级目录开始
                  </Button>
                </div>
              </div>
            )}
          </ProCard>
        </div>
      </div>

      <RatingChecklistModal
        visible={showRatingChecklist}
        isLoading={isLoadingRatingChecklist}
        data={ratingChecklist}
        onRefresh={() => {
          void fetchRatingChecklist();
        }}
        onClose={() => setShowRatingChecklist(false)}
      />

      <OutlineEditModal
        visible={!!editingItem}
        title={editTitle}
        description={editDescription}
        onTitleChange={setEditTitle}
        onDescriptionChange={setEditDescription}
        onOk={saveEdit}
        onCancel={cancelEditing}
      />
    </div>
  );
};

export default OutlineEdit;
