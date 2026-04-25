import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { OutlineData, OutlineItem } from '../types';
import {
  contentApi,
  proofreadApi,
  chapterApi,
  outlineApi,
  consistencyApi,
  materialApi,
  materialSmartApi,
  scoringApi,
  chapterTemplateApi,
  ChapterContentRequest,
} from '../services/api';
import type { ChapterTemplate } from '../services/api';
import type { SmartMatchResult, SmartMatchRecommendation } from '../services/api';
import type { ScoringCriteriaItem } from '../services/api';
import ExportDialog from '../components/ExportDialog';
import { getErrorMessage, ApiError } from '../utils/error';

import { draftStorage } from '../utils/draftStorage';
import { getCurrentModel, getCurrentProviderConfigId } from '../utils/modelCache';
import ChapterStatusBadge from '../components/ChapterStatusBadge';
import ProofreadPanel from '../components/ProofreadPanel';
import MaterialMarkerModal from '../components/content-edit/MaterialMarkerModal';
import MaterialSuggestPanel from '../components/content-edit/MaterialSuggestPanel';
import ReverseEnhanceModal from '../components/content-edit/ReverseEnhanceModal';
import ClauseResponseModal from '../components/content-edit/ClauseResponseModal';
import ConsistencyPanel from '../components/content-edit/ConsistencyPanel';
import type { ChapterStatus } from '../types/chapter';
import type { ChapterMaterialBinding } from '../types/material';
import type { ProofreadResult, ProofreadIssue } from '../types/proofread';
import type { ChapterReverseEnhanceResponse, ClauseResponseResult } from '../types/bid';
import type { ConsistencyCheckResult } from '../services/api';
import { ProCard } from '@ant-design/pro-components';
import { 
  Button, 
  Space, 
  Typography, 
  Progress, 
  Card, 
  Tag,
  Tooltip,
  FloatButton,
  message,
  Modal,
  Alert,
  Input,
  Spin,
  Form,
  Select,
  List,
  Badge,
} from 'antd';
import { 
  FileTextOutlined,
  PlayCircleOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  MessageOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
  RightOutlined,
  DownOutlined,
  LoadingOutlined,
  BulbOutlined,
  ProfileOutlined,
  PaperClipOutlined,
  StopOutlined,
  ThunderboltOutlined,
  TagOutlined,
  LinkOutlined,
  BookOutlined,
  SaveOutlined,
} from '@ant-design/icons';

interface ContentEditProps {
  outlineData: OutlineData | null;
  selectedChapter: string;
  onChapterSelect: (chapterId: string) => void;
  projectId?: string;
  onToggleComments?: (chapterId: string) => void;
  onToggleConsistency?: (chapterSummaries: { chapter_number: string; title: string; summary: string }[]) => void;
  highlightedChapters?: Set<string>;
}

interface GenerationProgress {
  total: number;
  completed: number;
  current: string;
  failed: string[];
  generating: Set<string>;
}

const ContentEdit: React.FC<ContentEditProps> = ({
  outlineData,
  selectedChapter,
  onChapterSelect,
  projectId,
  onToggleComments,
  onToggleConsistency,
  highlightedChapters,
}) => {

  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState<GenerationProgress>({
    total: 0,
    completed: 0,
    current: '',
    failed: [],
    generating: new Set<string>()
  });
  const [leafItems, setLeafItems] = useState<OutlineItem[]>([]);
  const [showScrollToTop, setShowScrollToTop] = useState(false);
  const [collapsedChapters, setCollapsedChapters] = useState<Set<string>>(new Set());

  const [showProofreadPanel, setShowProofreadPanel] = useState(false);
  const [proofreadChapterId, setProofreadChapterId] = useState<string | null>(null);
  const [proofreadChapterNumber, setProofreadChapterNumber] = useState<string | null>(null);
  const [proofreadChapterTitle, setProofreadChapterTitle] = useState('');
  const [proofreadResult, setProofreadResult] = useState<ProofreadResult | null>(null);
  const [isProofreading, setIsProofreading] = useState(false);
  const [proofreadStreamingText, setProofreadStreamingText] = useState('');
  const [chapterIdMap, setChapterIdMap] = useState<Record<string, string>>({});
  const [showReverseEnhanceModal, setShowReverseEnhanceModal] = useState(false);
  const [reverseEnhanceTarget, setReverseEnhanceTarget] = useState<{ chapterNumber: string; title: string } | null>(null);
  const [reverseEnhanceResult, setReverseEnhanceResult] = useState<ChapterReverseEnhanceResponse | null>(null);
  const [isReverseEnhancing, setIsReverseEnhancing] = useState(false);
  const [showClauseResponseModal, setShowClauseResponseModal] = useState(false);
  const [clauseText, setClauseText] = useState('');
  const [clauseKnowledgeContext, setClauseKnowledgeContext] = useState('');
  const [clauseResponseResult, setClauseResponseResult] = useState<ClauseResponseResult | null>(null);
  const [isGeneratingClauseResponse, setIsGeneratingClauseResponse] = useState(false);
  // 一致性校验状态
  const [showConsistencyPanel, setShowConsistencyPanel] = useState(false);
  const [isConsistencyChecking, setIsConsistencyChecking] = useState(false);
  const [consistencyResult, setConsistencyResult] = useState<ConsistencyCheckResult | null>(null);
  const [consistencyLastCheckedAt, setConsistencyLastCheckedAt] = useState<string | undefined>(undefined);

  const [showMaterialMarkerModal, setShowMaterialMarkerModal] = useState(false);
  const [materialMarkerBindings, setMaterialMarkerBindings] = useState<ChapterMaterialBinding[]>([]);
  const [materialMarkerTarget, setMaterialMarkerTarget] = useState<{ chapterNumber: string; title: string } | null>(null);
  const [selectedBindingId, setSelectedBindingId] = useState<string>('');
  const [showSuggestPanel, setShowSuggestPanel] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [suggestItems, setSuggestItems] = useState<Array<import('../types/material').MaterialAsset & { score: number }>>([]);
  const [pendingGenerateItem, setPendingGenerateItem] = useState<{ item: OutlineItem; projectOverview: string } | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [itemsToGenerateCount, setItemsToGenerateCount] = useState(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  // 章节ID -> 绑定的评分项列表（用于章节卡片上显示评分标签）
  const [chapterScoringMap, setChapterScoringMap] = useState<Record<string, ScoringCriteriaItem[]>>({});

  // 素材智能匹配面板
  const [smartMatchResults, setSmartMatchResults] = useState<SmartMatchResult[]>([]);
  const [smartMatchLoading, setSmartMatchLoading] = useState(false);
  const [autoBindLoading, setAutoBindLoading] = useState(false);
  // 章节ID -> 推荐素材列表（展开时懒查询）
  const [chapterMatchMap, setChapterMatchMap] = useState<Record<string, SmartMatchRecommendation[]>>({});
  // 当前展开推荐面板的章节ID
  const [expandedMatchChapter, setExpandedMatchChapter] = useState<string | null>(null);
  const [matchChapterLoading, setMatchChapterLoading] = useState<string | null>(null);

  // 知识库（章节模板）相关 state
  const [templatePickerVisible, setTemplatePickerVisible] = useState(false);
  const [templatePickerTarget, setTemplatePickerTarget] = useState<{ chapterNumber: string; chapterId: string; title: string } | null>(null);
  const [templateList, setTemplateList] = useState<ChapterTemplate[]>([]);
  const [templateListLoading, setTemplateListLoading] = useState(false);
  const [templateKeyword, setTemplateKeyword] = useState('');
  const [saveTemplateVisible, setSaveTemplateVisible] = useState(false);
  const [saveTemplateTarget, setSaveTemplateTarget] = useState<{ chapterNumber: string; chapterId: string; title: string } | null>(null);
  const [saveTemplateForm] = Form.useForm();
  const [saveTemplateLoading, setSaveTemplateLoading] = useState(false);

  // 加载评分标准，建立 chapterId -> items 映射（静默加载）
  useEffect(() => {
    if (!projectId) return;
    scoringApi.list(projectId).then(items => {
      const map: Record<string, ScoringCriteriaItem[]> = {};
      for (const sc of items) {
        if (sc.bound_chapter_id) {
          if (!map[sc.bound_chapter_id]) map[sc.bound_chapter_id] = [];
          map[sc.bound_chapter_id].push(sc);
        }
      }
      setChapterScoringMap(map);
    }).catch(() => {/* 静默忽略 */});
  }, [projectId]);

  const loadProjectChapterMap = useCallback(async (): Promise<Record<string, string>> => {
    if (!projectId) {
      setChapterIdMap({});
      return {};
    }

    const response = await outlineApi.getProjectChapters(projectId);
    const nextMap = response.chapters.reduce<Record<string, string>>((acc, chapter) => {
      acc[chapter.chapter_number] = chapter.id;
      return acc;
    }, {});
    setChapterIdMap(nextMap);
    return nextMap;
  }, [projectId]);

  const getProjectChapterId = useCallback(
    async (chapterNumber: string): Promise<string | null> => {
      if (chapterIdMap[chapterNumber]) {
        return chapterIdMap[chapterNumber];
      }

      const refreshedMap = await loadProjectChapterMap();
      return refreshedMap[chapterNumber] || null;
    },
    [chapterIdMap, loadProjectChapterMap]
  );

  const ensureChapterContentPersisted = useCallback(
    async (chapterNumber: string, chapterTitle: string, currentContent: string): Promise<string> => {
      if (!currentContent.trim()) {
        throw new Error('章节内容为空，无法执行该操作');
      }

      const projectChapterId = await getProjectChapterId(chapterNumber);
      if (!projectChapterId) {
        throw new Error(`未找到章节 ${chapterNumber} 的数据库记录`);
      }

      const latestChapter = await chapterApi.get(projectChapterId);
      if ((latestChapter.content || '').trim() !== currentContent.trim()) {
        await chapterApi.updateContent(
          projectChapterId,
          currentContent,
          `同步正文后执行：${chapterNumber} ${chapterTitle}`
        );
      }

      return projectChapterId;
    },
    [getProjectChapterId]
  );

  const handleOpenMaterialMarkerModal = useCallback(
    async (item: OutlineItem) => {
      if (!projectId) {
        message.warning('仅项目模式支持素材占位标记');
        return;
      }
      const projectChapterId = await getProjectChapterId(item.id);
      if (!projectChapterId) {
        message.warning(`未找到章节 ${item.id} 的数据库记录`);
        return;
      }
      try {
        const bindings = await materialApi.listBindings(projectId, projectChapterId);
        setMaterialMarkerBindings(bindings);
        setSelectedBindingId(bindings.length > 0 ? bindings[0].id : '');
        setMaterialMarkerTarget({ chapterNumber: item.id, title: item.title });
        setShowMaterialMarkerModal(true);
      } catch (error: unknown) {
        const detail = (error as any)?.response?.data?.detail;
        message.error(detail || '加载素材绑定失败');
      }
    },
    [getProjectChapterId, projectId]
  );

  /** 为单个章节拉取推荐素材（切换展开） */
  const handleToggleSmartMatch = useCallback(async (chapterDbId: string) => {
    if (!projectId) return;
    if (expandedMatchChapter === chapterDbId) {
      setExpandedMatchChapter(null);
      return;
    }
    setExpandedMatchChapter(chapterDbId);
    if (chapterMatchMap[chapterDbId]) return; // 已加载过
    setMatchChapterLoading(chapterDbId);
    try {
      const results = await materialSmartApi.match(projectId, chapterDbId);
      const recommendations = results[0]?.recommended_materials ?? [];
      setChapterMatchMap(prev => ({ ...prev, [chapterDbId]: recommendations }));
    } catch {
      setChapterMatchMap(prev => ({ ...prev, [chapterDbId]: [] }));
    } finally {
      setMatchChapterLoading(null);
    }
  }, [projectId, expandedMatchChapter, chapterMatchMap]);

  /** 一键绑定单条推荐素材 */
  const handleBindRecommendedMaterial = useCallback(async (chapterDbId: string, materialId: string, materialName: string) => {
    if (!projectId) return;
    try {
      await materialApi.createBinding(projectId, chapterDbId, {
        material_asset_id: materialId,
      });
      message.success(`已绑定素材：${materialName}`);
      // 刷新该章节的推荐列表（清除缓存，重新加载）
      setChapterMatchMap(prev => {
        const next = { ...prev };
        delete next[chapterDbId];
        return next;
      });
      setExpandedMatchChapter(null);
    } catch (error: unknown) {
      const detail = (error as any)?.response?.data?.detail;
      message.error(detail || '绑定素材失败');
    }
  }, [projectId]);

  /** 批量一键自动绑定 */
  const handleAutoBind = useCallback(async () => {
    if (!projectId) {
      message.warning('缺少项目 ID，无法自动绑定');
      return;
    }
    setAutoBindLoading(true);
    try {
      const result = await materialSmartApi.autoBind(projectId);
      message.success(
        `智能绑定完成：新绑定 ${result.bound_count} 个章节，跳过 ${result.skipped_count} 个`,
      );
      // 清空本地推荐缓存，强制刷新
      setChapterMatchMap({});
      setExpandedMatchChapter(null);
    } catch (error: unknown) {
      const detail = (error as any)?.response?.data?.detail;
      message.error(detail || '自动绑定失败');
    } finally {
      setAutoBindLoading(false);
    }
  }, [projectId]);

  const handleInsertMaterialMarker = useCallback(async () => {
    if (!materialMarkerTarget || !selectedBindingId) {
      message.warning('请选择要插入的素材绑定');
      return;
    }

    const chapterNumber = materialMarkerTarget.chapterNumber;
    const targetItem = leafItems.find((item) => item.id === chapterNumber);
    if (!targetItem) {
      message.warning('未找到目标章节内容');
      return;
    }

    const marker = `[INSERT_MATERIAL:${selectedBindingId}]`;
    const nextContent = `${targetItem.content || ''}\n\n${marker}`.trim();
    setLeafItems((prevItems) =>
      prevItems.map((item) => (item.id === chapterNumber ? { ...item, content: nextContent } : item))
    );
    draftStorage.saveContentById({ [chapterNumber]: nextContent });

    if (projectId) {
      const projectChapterId = await getProjectChapterId(chapterNumber);
      if (projectChapterId) {
        await chapterApi.updateContent(projectChapterId, nextContent, `插入素材标记 ${selectedBindingId}`);
      }
    }

    setShowMaterialMarkerModal(false);
    message.success('素材占位标记已插入');
  }, [getProjectChapterId, leafItems, materialMarkerTarget, projectId, selectedBindingId]);

  const highlightConsistencyFixes = (content: string): React.ReactNode => {
    if (!content) return null;

    const marker = '【一致性修改】';
    if (!content.includes(marker)) {
      return <ReactMarkdown>{content}</ReactMarkdown>;
    }

    const parts: React.ReactNode[] = [];
    let keyIndex = 0;
    let remainingContent = content;

    while (remainingContent.includes(marker)) {
      const markerIndex = remainingContent.indexOf(marker);

      if (markerIndex > 0) {
        const normalContent = remainingContent.substring(0, markerIndex);
        parts.push(<ReactMarkdown key={`normal-${keyIndex}`}>{normalContent}</ReactMarkdown>);
      }

      const afterMarker = remainingContent.substring(markerIndex + marker.length);
      let endIndex = afterMarker.indexOf('\n');
      if (endIndex === -1) {
        endIndex = afterMarker.length;
      }

      const fixContent = afterMarker.substring(0, endIndex);
      remainingContent = afterMarker.substring(endIndex);

      parts.push(
        <div key={`fix-${keyIndex}`} style={{ backgroundColor: '#fffbe6', borderLeft: '4px solid #faad14', padding: '12px', margin: '8px 0', borderRadius: '0 4px 4px 0' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start' }}>
            <span style={{ color: '#d48806', fontWeight: 500, fontSize: 14, marginRight: 8 }}>一致性修改:</span>
            <span style={{ color: '#ad6800', fontSize: 14 }}>{fixContent}</span>
          </div>
        </div>
      );

      keyIndex++;
    }

    if (remainingContent.trim()) {
      const cleanRemaining = remainingContent.replace(/^[\s-]*/, '');
      if (cleanRemaining.trim()) {
        parts.push(<ReactMarkdown key={`remaining-${keyIndex}`}>{cleanRemaining}</ReactMarkdown>);
      }
    }

    return <>{parts}</>;
  };

  const collectLeafItems = useCallback((items: OutlineItem[]): OutlineItem[] => {
    let leaves: OutlineItem[] = [];
    items.forEach(item => {
      if (!item.children || item.children.length === 0) {
        leaves.push(item);
      } else {
        leaves = leaves.concat(collectLeafItems(item.children));
      }
    });
    return leaves;
  }, []);

  const getParentChapters = useCallback((targetId: string, items: OutlineItem[], parents: OutlineItem[] = []): OutlineItem[] => {
    for (const item of items) {
      if (item.id === targetId) {
        return parents;
      }
      if (item.children && item.children.length > 0) {
        const found = getParentChapters(targetId, item.children, [...parents, item]);
        if (found.length > 0 || item.children.some(child => child.id === targetId)) {
          return found.length > 0 ? found : [...parents, item];
        }
      }
    }
    return [];
  }, []);

  const getSiblingChapters = useCallback((targetId: string, items: OutlineItem[]): OutlineItem[] => {
    if (items.some(item => item.id === targetId)) {
      return items;
    }
    
    for (const item of items) {
      if (item.children && item.children.length > 0) {
        const siblings = getSiblingChapters(targetId, item.children);
        if (siblings.length > 0) {
          return siblings;
        }
      }
    }
    
    return [];
  }, []);

  useEffect(() => {
    console.log('[ContentEdit] outlineData changed:', {
      hasData: !!outlineData,
      outlineLength: outlineData?.outline?.length,
      firstItem: outlineData?.outline?.[0] ? { id: outlineData.outline[0].id, title: outlineData.outline[0].title } : null,
    });
    if (outlineData) {
      const leaves = collectLeafItems(outlineData.outline);
      console.log('[ContentEdit] leafItems collected:', leaves.length, 'first:', leaves[0]?.id, leaves[0]?.title);
      const filtered = draftStorage.filterContentByOutlineLeaves(outlineData.outline);
      const mergedLeaves = leaves.map((leaf) => {
        const cached = filtered[leaf.id];
        return cached ? { ...leaf, content: cached } : leaf;
      });

      draftStorage.saveContentById(filtered);

      setLeafItems(mergedLeaves);
      setProgress(prev => ({ ...prev, total: leaves.length }));
    }
  }, [outlineData, collectLeafItems]);

  useEffect(() => {
    if (!projectId) {
      setChapterIdMap({});
      return;
    }

    loadProjectChapterMap().catch((error) => {
      console.error('加载项目章节映射失败:', error);
    });
  }, [projectId, outlineData, loadProjectChapterMap]);

  useEffect(() => {
    const scrollContainer = document.getElementById('app-main-scroll');

    const handleScroll = () => {
      const scrollTop = scrollContainer
        ? scrollContainer.scrollTop
        : (window.pageYOffset || document.documentElement.scrollTop);
      setShowScrollToTop(scrollTop > 300);
    };

    handleScroll();
    const target = scrollContainer || window;
    target.addEventListener('scroll', handleScroll);
    return () => target.removeEventListener('scroll', handleScroll);
  }, []);

  const getLeafItemContent = (itemId: string): string | undefined => {
    const leafItem = leafItems.find(leaf => leaf.id === itemId);
    return leafItem?.content;
  };

  const isLeafNode = (item: OutlineItem): boolean => {
    return !item.children || item.children.length === 0;
  };

  const getChapterStatus = (item: OutlineItem, isGenerating: boolean): ChapterStatus => {
    if (isGenerating) return 'generating';
    if (!isLeafNode(item)) {
      return 'pending';
    }
    const leafItem = leafItems.find(leaf => leaf.id === item.id);
    if (leafItem?.generationError) return 'error';
    const content = getLeafItemContent(item.id) || item.content;
    if (content) return 'generated';
    return 'pending';
  };

  const handleProofreadChapter = async (
    chapterNumber: string,
    chapterTitle: string,
    currentContent: string
  ) => {
    setProofreadChapterId(null);
    setProofreadChapterNumber(chapterNumber);
    setProofreadChapterTitle(chapterTitle);
    setProofreadResult(null);
    setProofreadStreamingText('');
    setShowProofreadPanel(true);
    setIsProofreading(true);

    try {
      const chapterId = await ensureChapterContentPersisted(chapterNumber, chapterTitle, currentContent);
      setProofreadChapterId(chapterId);

      const response = await proofreadApi.proofreadChapter(chapterId);

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error((error as { detail?: string }).detail || `请求失败: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('无法读取响应');

      let fullContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = new TextDecoder().decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            try {
              const parsed = JSON.parse(data);

              if (parsed.chunk) {
                fullContent += parsed.chunk;
                setProofreadStreamingText(fullContent);
              } else if (parsed.done && parsed.result) {
                setProofreadResult(parsed.result);
                setProofreadStreamingText('');
              } else if (parsed.error) {
                throw new Error(parsed.error);
              }
            } catch {
              // Ignore
            }
          }
        }
      }
    } catch (error) {
      console.error('校对失败:', error);
      message.error(getErrorMessage(error, '校对失败，请重试'));
      setShowProofreadPanel(false);
    } finally {
      setIsProofreading(false);
    }
  };

  const handleApplySuggestion = async (issue: ProofreadIssue) => {
    if (!proofreadChapterId || !proofreadChapterNumber) return;

    try {
      const chapterData = await chapterApi.get(proofreadChapterId);
      let content = chapterData.content || '';

      const suggestionNote = `\n\n<!-- 校对建议：${issue.suggestion} -->`;

      await chapterApi.updateContent(
        proofreadChapterId,
        content + suggestionNote,
        `应用校对建议：${issue.issue}`
      );

      setLeafItems(prevItems =>
        prevItems.map(item =>
          item.id === proofreadChapterNumber
            ? { ...item, content: content + suggestionNote }
            : item
        )
      );

      message.success('建议已应用到内容中');
    } catch (error) {
      console.error('应用建议失败:', error);
      message.error('应用建议失败');
    }
  };

  const handleEditContent = (issue: ProofreadIssue) => {
    window.alert(`请根据以下建议手动编辑内容：\n\n${issue.suggestion}`);
  };

  const handleCloseProofreadPanel = () => {
    setShowProofreadPanel(false);
    setProofreadChapterId(null);
    setProofreadChapterNumber(null);
    setProofreadResult(null);
    setProofreadStreamingText('');
  };

  const buildReverseEnhanceSummary = (result: ChapterReverseEnhanceResponse) => {
    const actionLines = result.enhancement_actions.map((action, index) => {
      const evidenceSuffix = action.evidence_needed ? `；建议补充：${action.evidence_needed}` : '';
      return `${index + 1}. [${action.priority}] ${action.problem} -> ${action.action}${evidenceSuffix}`;
    });

    return [
      `覆盖评估：${result.coverage_assessment}`,
      result.matched_points.length ? `已覆盖评分点：${result.matched_points.join('；')}` : '',
      result.missing_points.length ? `待补强评分点：${result.missing_points.join('；')}` : '',
      actionLines.length ? `补强动作：\n${actionLines.join('\n')}` : '',
      `总结：${result.summary}`,
    ]
      .filter(Boolean)
      .join('\n\n');
  };

  const copyText = async (text: string, successMessage: string) => {
    try {
      await navigator.clipboard.writeText(text);
      message.success(successMessage);
    } catch (error) {
      console.error('复制失败:', error);
      message.error('复制失败，请手动复制');
    }
  };

  const handleReverseEnhance = async (item: OutlineItem, currentContent: string) => {
    if (!projectId) {
      message.warning('缺少项目 ID，暂时无法执行反向补强');
      return;
    }

    if (!currentContent.trim()) {
      message.warning('当前章节还没有正文内容，无法执行反向补强');
      return;
    }

    setReverseEnhanceTarget({ chapterNumber: item.id, title: item.title });
    setReverseEnhanceResult(null);
    setShowReverseEnhanceModal(true);
    setIsReverseEnhancing(true);

    try {
      const chapterId = await ensureChapterContentPersisted(item.id, item.title, currentContent);
      const result = await consistencyApi.reverseEnhanceChapter(projectId, chapterId);
      setReverseEnhanceResult(result);
    } catch (error) {
      console.error('反向补强失败:', error);
      message.error(getErrorMessage(error, '反向补强失败，请重试'));
    } finally {
      setIsReverseEnhancing(false);
    }
  };

  const handleGenerateClauseResponse = async () => {
    if (!projectId) {
      message.warning('缺少项目 ID，暂时无法生成逐条响应');
      return;
    }

    if (!clauseText.trim()) {
      message.warning('请先输入技术参数或条款原文');
      return;
    }

    setIsGeneratingClauseResponse(true);
    try {
      const result = await consistencyApi.generateClauseResponse(projectId, {
        clause_text: clauseText.trim(),
        knowledge_context: clauseKnowledgeContext.trim() || undefined,
      });
      setClauseResponseResult(result);
    } catch (error) {
      console.error('条款逐条响应生成失败:', error);
      message.error(getErrorMessage(error, '条款逐条响应生成失败，请重试'));
    } finally {
      setIsGeneratingClauseResponse(false);
    }
  };

  // ============ 知识库（章节模板）相关 handlers ============

  const handleOpenTemplatePicker = async (item: OutlineItem) => {
    if (!projectId) {
      message.warning('仅项目模式支持套用模板');
      return;
    }
    const chapterId = await getProjectChapterId(item.id);
    if (!chapterId) {
      message.warning(`未找到章节 ${item.id} 的数据库记录`);
      return;
    }
    setTemplatePickerTarget({ chapterNumber: item.id, chapterId, title: item.title });
    setTemplateKeyword('');
    setTemplatePickerVisible(true);
    setTemplateListLoading(true);
    try {
      // 用章节标题智能搜索推荐模板
      const results = await chapterTemplateApi.search(item.title);
      setTemplateList(results);
    } catch {
      setTemplateList([]);
    } finally {
      setTemplateListLoading(false);
    }
  };

  const handleTemplateSearch = async (kw: string) => {
    setTemplateKeyword(kw);
    setTemplateListLoading(true);
    try {
      const results = kw.trim()
        ? await chapterTemplateApi.search(kw.trim())
        : await chapterTemplateApi.list();
      setTemplateList(results);
    } catch {
      setTemplateList([]);
    } finally {
      setTemplateListLoading(false);
    }
  };

  const handleApplyTemplate = async (tpl: ChapterTemplate) => {
    if (!templatePickerTarget) return;
    try {
      const result = await chapterTemplateApi.apply(tpl.id, templatePickerTarget.chapterId);
      // 刷新本地 leafItems 内容
      setLeafItems(prev =>
        prev.map(i =>
          i.id === templatePickerTarget.chapterNumber
            ? { ...i, content: result.content }
            : i
        )
      );
      message.success(`已套用模板「${tpl.name}」`);
      setTemplatePickerVisible(false);
    } catch (error: unknown) {
      const detail = (error as any)?.message;
      message.error(detail || '套用模板失败');
    }
  };

  const handleOpenSaveTemplate = async (item: OutlineItem, currentContent: string) => {
    if (!currentContent.trim()) {
      message.warning('章节内容为空，无法保存为模板');
      return;
    }
    if (!projectId) {
      message.warning('仅项目模式支持保存模板');
      return;
    }
    const chapterId = await getProjectChapterId(item.id);
    if (!chapterId) {
      message.warning(`未找到章节 ${item.id} 的数据库记录`);
      return;
    }
    setSaveTemplateTarget({ chapterNumber: item.id, chapterId, title: item.title });
    saveTemplateForm.setFieldsValue({
      name: `${item.id} ${item.title}`,
      category: undefined,
      tags: [],
    });
    setSaveTemplateVisible(true);
  };

  const handleConfirmSaveTemplate = async () => {
    if (!saveTemplateTarget) return;
    try {
      const values = await saveTemplateForm.validateFields();
      setSaveTemplateLoading(true);
      await chapterTemplateApi.fromChapter(saveTemplateTarget.chapterId, {
        name: values.name,
        category: values.category,
        tags: values.tags || [],
      });
      message.success('已保存为章节模板');
      setSaveTemplateVisible(false);
      saveTemplateForm.resetFields();
    } catch (error: unknown) {
      if ((error as any)?.errorFields) return;
      const detail = (error as any)?.message;
      message.error(detail || '保存模板失败');
    } finally {
      setSaveTemplateLoading(false);
    }
  };

  const TEMPLATE_CATEGORIES = ['技术方案', '项目经验', '团队配置', '质量保障', '安全方案', '服务方案', '投标报价', '其他'];

  const handleRunConsistencyCheck = async () => {
    if (!projectId) {
      message.warning('仅项目模式支持全文一致性校验');
      return;
    }
    setShowConsistencyPanel(true);
    setIsConsistencyChecking(true);
    try {
      const result = await consistencyApi.check(projectId);
      setConsistencyResult(result);
      setConsistencyLastCheckedAt(new Date().toLocaleString('zh-CN'));
    } catch (error) {
      message.error(getErrorMessage(error, '一致性校验失败，请重试'));
    } finally {
      setIsConsistencyChecking(false);
    }
  };

  const renderOutline = (items: OutlineItem[], level: number = 1): React.ReactElement[] => {
    return items.map((item) => {
      const isLeaf = isLeafNode(item);
      const leafItem = isLeaf ? leafItems.find(i => i.id === item.id) : null;
      const currentContent = isLeaf ? (leafItem?.content || getLeafItemContent(item.id)) : item.content;
      const generationError = leafItem?.generationError;
      const isGeneratingThis = progress.generating.has(item.id);
      const chapterStatus = getChapterStatus(item, isGeneratingThis);
      const isHighlighted = highlightedChapters?.has(item.id);
      const isCollapsed = collapsedChapters.has(item.id);
      const hasChildren = item.children && item.children.length > 0;

      return (
        <div key={item.id} style={{ marginBottom: level === 1 ? 24 : 16 }}>
          <div 
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: 8,
              padding: isHighlighted ? '8px 12px' : 0,
              backgroundColor: isHighlighted ? '#f6ffed' : 'transparent',
              borderRadius: isHighlighted ? 8 : 0,
            }}
          >
            {!isLeaf && hasChildren && (
              <Button
                type="text"
                size="small"
                icon={isCollapsed ? <RightOutlined style={{ fontSize: 12, color: '#bfbfbf' }} /> : <DownOutlined style={{ fontSize: 12, color: '#bfbfbf' }} />}
                onClick={() => {
                  setCollapsedChapters(prev => {
                    const newSet = new Set(prev);
                    if (newSet.has(item.id)) {
                      newSet.delete(item.id);
                    } else {
                      newSet.add(item.id);
                    }
                    return newSet;
                  });
                }}
                style={{ padding: 0, minWidth: 24 }}
              />
            )}
            
            <Typography.Text 
              strong={level <= 2}
              style={{ 
                fontSize: level === 1 ? 18 : level === 2 ? 16 : 14,
                color: isHighlighted ? '#389e0d' : undefined,
                flex: 1
              }}
            >
              {item.id} {item.title}
              {isHighlighted && (
                <Tag color="success" style={{ marginLeft: 8 }}>已修改</Tag>
              )}
            </Typography.Text>
            
            {isLeaf && <ChapterStatusBadge status={chapterStatus} />}
            
            {isLeaf && currentContent && !generationError && (
              <Tooltip title="AI 校对">
                <Button
                  type="text"
                  size="small"
                  icon={<SafetyCertificateOutlined />}
                  onClick={() => {
                    void handleProofreadChapter(item.id, item.title, currentContent);
                  }}
                  disabled={isProofreading}
                  style={{ color: '#722ed1' }}
                >
                  校对
                </Button>
              </Tooltip>
            )}

            {isLeaf && currentContent && !generationError && projectId && (
              <Tooltip title="插入已绑定的素材占位标记">
                <Button
                  type="text"
                  size="small"
                  icon={<PaperClipOutlined />}
                  onClick={() => {
                    void handleOpenMaterialMarkerModal(item);
                  }}
                  style={{ color: '#0f766e' }}
                >
                  插入素材
                </Button>
              </Tooltip>
            )}

            {isLeaf && projectId && (() => {
              const chapterDbId = chapterIdMap[item.id];
              if (!chapterDbId) return null;
              const isExpanded = expandedMatchChapter === chapterDbId;
              const isLoadingThis = matchChapterLoading === chapterDbId;
              return (
                <Tooltip title="根据章节主题推荐相关素材">
                  <Button
                    type="text"
                    size="small"
                    icon={isLoadingThis ? <LoadingOutlined /> : <TagOutlined />}
                    onClick={() => { void handleToggleSmartMatch(chapterDbId); }}
                    style={{ color: isExpanded ? '#1677ff' : '#6b7280' }}
                  >
                    推荐素材
                  </Button>
                </Tooltip>
              );
            })()}

            {isLeaf && currentContent && !generationError && projectId && (
              <Tooltip title="根据评分点分析本章覆盖情况并给出补强建议">
                <Button
                  type="text"
                  size="small"
                  icon={<BulbOutlined />}
                  onClick={() => {
                    void handleReverseEnhance(item, currentContent);
                  }}
                  disabled={isReverseEnhancing}
                  style={{ color: '#d97706' }}
                >
                  反向补强
                </Button>
              </Tooltip>
            )}
            
            {isLeaf && onToggleComments && (
              <Tooltip title="查看批注">
                <Button
                  type="text"
                  size="small"
                  icon={<MessageOutlined />}
                  onClick={() => {
                    void (async () => {
                      const chapterId = await getProjectChapterId(item.id);
                      if (!chapterId) {
                        message.warning(`未找到章节 ${item.id} 的批注记录`);
                        return;
                      }
                      onToggleComments(chapterId);
                    })();
                  }}
                  style={{ color: '#8c8c8c' }}
                >
                  批注
                </Button>
              </Tooltip>
            )}

            {isLeaf && projectId && (
              <Tooltip title="从知识库套用章节模板">
                <Button
                  type="text"
                  size="small"
                  icon={<BookOutlined />}
                  onClick={() => {
                    void handleOpenTemplatePicker(item);
                  }}
                  style={{ color: '#1677ff' }}
                >
                  套用模板
                </Button>
              </Tooltip>
            )}

            {isLeaf && currentContent && !generationError && projectId && (
              <Tooltip title="将本章节保存为可复用模板">
                <Button
                  type="text"
                  size="small"
                  icon={<SaveOutlined />}
                  onClick={() => {
                    void handleOpenSaveTemplate(item, currentContent);
                  }}
                  style={{ color: '#52c41a' }}
                >
                  存为模板
                </Button>
              </Tooltip>
            )}
          </div>

          <Typography.Text type="secondary" style={{ display: 'block', marginLeft: !isLeaf && hasChildren ? 32 : 0, marginTop: 4, marginBottom: 8, fontSize: 13 }}>
            {item.description}
          </Typography.Text>

          {(item.rating_item || item.chapter_role || item.avoid_overlap) && (
            <div style={{ marginLeft: !isLeaf && hasChildren ? 32 : 0, marginBottom: 12 }}>
              <Space wrap size={[8, 8]}>
                {item.rating_item && <Tag color="blue">评分点：{item.rating_item}</Tag>}
                {item.chapter_role && <Tag color="purple">职责：{item.chapter_role}</Tag>}
                {item.avoid_overlap && <Tag color="gold">去重边界：{item.avoid_overlap}</Tag>}
              </Space>
            </div>
          )}
          {/* 评分标准绑定标签 */}
          {(() => {
            const chapterDbId = chapterIdMap[item.id];
            const boundScoring = chapterDbId ? (chapterScoringMap[chapterDbId] || []) : [];
            if (boundScoring.length === 0) return null;
            return (
              <div style={{ marginLeft: !isLeaf && hasChildren ? 32 : 0, marginBottom: 8 }}>
                <Space wrap size={[6, 6]}>
                  {boundScoring.map(sc => (
                    <Tag
                      key={sc.id}
                      color={(sc.max_score ?? 0) >= 8 ? 'volcano' : 'geekblue'}
                      style={{ fontSize: 11 }}
                    >
                      📊 {sc.item}{sc.max_score != null ? ` ${sc.max_score}分` : ''}
                    </Tag>
                  ))}
                </Space>
              </div>
            );
          })()}

          {isLeaf && (
            <div 
              style={{ 
                borderLeft: `3px solid ${generationError ? '#ffccc7' : '#91caff'}`,
                paddingLeft: 16,
                marginLeft: !isLeaf && hasChildren ? 32 : 0,
                marginBottom: 16,
                backgroundColor: generationError ? '#fff1f0' : undefined,
                padding: generationError ? '12px 16px' : undefined,
                borderRadius: generationError ? '0 4px 4px 0' : 0,
              }}
            >
              {generationError ? (
                <div>
                  <Typography.Text type="danger" strong style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                    <ExclamationCircleOutlined style={{ marginRight: 8 }} />
                    生成失败
                  </Typography.Text>
                  <Typography.Text type="danger" style={{ display: 'block', marginBottom: 12, fontSize: 13, backgroundColor: 'rgba(255, 77, 79, 0.1)', padding: 8, borderRadius: 4 }}>
                    {generationError}
                  </Typography.Text>
                  <Button
                    type="primary"
                    danger
                    size="small"
                    icon={isGeneratingThis ? <LoadingOutlined /> : <SyncOutlined />}
                    onClick={() => regenerateItemContent(item)}
                    disabled={isGeneratingThis}
                  >
                    {isGeneratingThis ? '重新生成中...' : '重新生成'}
                  </Button>
                </div>
              ) : currentContent ? (
                <div>
                  <div className="markdown-body" style={{ fontSize: 14 }}>
                    {highlightConsistencyFixes(currentContent)}
                  </div>
                  <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #f0f0f0' }}>
                    <Button
                      type="default"
                      size="small"
                      icon={isGeneratingThis ? <LoadingOutlined /> : <SyncOutlined />}
                      onClick={() => regenerateItemContent(item)}
                      disabled={isGeneratingThis}
                    >
                      {isGeneratingThis ? '重新生成中...' : '重新生成'}
                    </Button>
                  </div>
                </div>
              ) : (
                <Typography.Text type="secondary" italic style={{ padding: '16px 0', display: 'block' }}>
                  <FileTextOutlined style={{ marginRight: 8 }} />
                  {isGeneratingThis ? (
                    <span style={{ color: '#1677ff' }}>正在生成内容...</span>
                  ) : (
                    '内容待生成...'
                  )}
                </Typography.Text>
              )}
            </div>
          )}

          {/* 推荐素材内联面板 */}
          {isLeaf && projectId && (() => {
            const chapterDbId = chapterIdMap[item.id];
            if (!chapterDbId || expandedMatchChapter !== chapterDbId) return null;
            const recommendations = chapterMatchMap[chapterDbId] ?? [];
            const isLoadingThis = matchChapterLoading === chapterDbId;
            return (
              <div style={{
                marginLeft: 0,
                marginBottom: 16,
                border: '1px solid #bae6fd',
                borderRadius: 8,
                backgroundColor: '#f0f9ff',
                padding: '12px 16px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                  <TagOutlined style={{ color: '#0284c7', marginRight: 6 }} />
                  <Typography.Text strong style={{ color: '#0284c7', fontSize: 13 }}>
                    推荐素材
                  </Typography.Text>
                  {isLoadingThis && <Spin size="small" style={{ marginLeft: 8 }} />}
                </div>
                {!isLoadingThis && recommendations.length === 0 && (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    暂无匹配的素材推荐，可先上传相关素材后重试
                  </Typography.Text>
                )}
                {recommendations.map(rec => (
                  <div key={rec.material_id} style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '6px 10px',
                    marginBottom: 6,
                    backgroundColor: '#fff',
                    borderRadius: 6,
                    border: '1px solid #e0f2fe',
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Typography.Text style={{ fontSize: 13, fontWeight: 500 }} ellipsis>
                        {rec.material_name}
                      </Typography.Text>
                      <div style={{ display: 'flex', gap: 8, marginTop: 2, flexWrap: 'wrap' }}>
                        <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>{rec.category}</Tag>
                        <Tag color="green" style={{ fontSize: 11, margin: 0 }}>
                          相关度 {Math.round(rec.relevance_score)}
                        </Tag>
                        {rec.reason && (
                          <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                            {rec.reason}
                          </Typography.Text>
                        )}
                      </div>
                    </div>
                    <Button
                      type="primary"
                      size="small"
                      icon={<LinkOutlined />}
                      onClick={() => { void handleBindRecommendedMaterial(chapterDbId, rec.material_id, rec.material_name); }}
                      style={{ marginLeft: 12, flexShrink: 0 }}
                    >
                      绑定
                    </Button>
                  </div>
                ))}
              </div>
            );
          })()}

          {hasChildren && !isCollapsed && (
            <div style={{ marginLeft: 24, marginTop: 8 }}>
              {renderOutline(item.children!, level + 1)}
            </div>
          )}
        </div>
      );
    });
  };

  const generateItemContent = async (item: OutlineItem, projectOverview: string): Promise<OutlineItem> => {
    if (!outlineData) throw new Error('缺少目录数据');
    
    setProgress(prev => ({ 
      ...prev, 
      current: item.title,
      generating: new Set([...Array.from(prev.generating), item.id])
    }));
    
    try {
      const parentChapters = getParentChapters(item.id, outlineData.outline);
      const siblingChapters = getSiblingChapters(item.id, outlineData.outline);

      const request: ChapterContentRequest = {
        chapter: item,
        parent_chapters: parentChapters,
        sibling_chapters: siblingChapters,
        project_overview: projectOverview,
        model_name: getCurrentModel() || undefined,
        provider_config_id: getCurrentProviderConfigId() || undefined,
        use_knowledge: true,
        confirmed_material_ids: item._confirmedMaterialIds || [],
      };

      const response = await contentApi.generateChapterContentStream(request, abortControllerRef.current?.signal);

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error((error as { detail?: string }).detail || `请求失败: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('无法读取响应');

      let content = '';
      const updatedItem = { ...item };
      let sseBuffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        sseBuffer += new TextDecoder().decode(value);
        const parts = sseBuffer.split('\n\n');
        sseBuffer = parts.pop() || '';

        for (const part of parts) {
          const lines = part.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;
              
              try {
                const parsed = JSON.parse(data);
                
                if (parsed.status === 'error') {
                  throw new Error(parsed.message || '生成失败');
                }

                if (parsed.status === 'knowledge_retrieved' && parsed.count > 0) {
                  message.info(`已检索知识库 ${parsed.count} 条参考`, 2);
                }

                if (parsed.status === 'streaming' && parsed.full_content) {
                  content = parsed.full_content;
                  updatedItem.content = content;
                  draftStorage.upsertChapterContent(item.id, content);
                  
                  setLeafItems(prevItems => {
                    const newItems = [...prevItems];
                    const index = newItems.findIndex(i => i.id === item.id);
                    if (index !== -1) {
                      newItems[index] = { ...updatedItem };
                    }
                    return newItems;
                  });
                } else if (parsed.status === 'completed' && parsed.content) {
                  content = parsed.content;
                  updatedItem.content = content;
                  draftStorage.upsertChapterContent(item.id, content);
                  if (projectId) {
                    chapterApi.updateContent(`${projectId}_${item.id}`, content).catch(() => {});
                  }
                }
              } catch (e) {
                if (e instanceof Error && e.message !== data.slice(0, 100)) {
                  // Re-throw application errors (e.g. parsed.status === 'error')
                  // but not JSON syntax errors
                  if (!(e instanceof SyntaxError)) {
                    throw e;
                  }
                }
                console.warn('[ContentEdit] SSE JSON parse failed, skipping:', data.slice(0, 100));
              }
            }
          }
        }
      }

      return updatedItem;
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : '生成失败';
      const updatedItem = { ...item, content: undefined, generationError: errorMessage };
      draftStorage.clearChapterContent(item.id);
      setLeafItems(prevItems => {
        const newItems = [...prevItems];
        const index = newItems.findIndex(i => i.id === item.id);
        if (index !== -1) {
          newItems[index] = updatedItem;
        }
        return newItems;
      });
      setProgress(prev => ({
        ...prev,
        failed: [...prev.failed, item.title]
      }));
      return updatedItem;
    } finally {
      setProgress(prev => {
        const newGenerating = new Set(Array.from(prev.generating));
        newGenerating.delete(item.id);
        return {
          ...prev,
          generating: newGenerating
        };
      });
    }
  };

  const regenerateItemContent = async (item: OutlineItem) => {
    if (!item || !outlineData) return;

    // 先拉素材推荐
    if (projectId) {
      setSuggestLoading(true);
      setShowSuggestPanel(true);
      setPendingGenerateItem({ item, projectOverview: outlineData.project_overview || '' });
      try {
        const result = await materialApi.suggestForChapter({
          project_id: projectId,
          chapter_title: item.title || '',
          chapter_content: item.content || '',
          top_k: 5,
        });
        setSuggestItems(result?.suggestions || []);
      } catch {
        setSuggestItems([]);
      } finally {
        setSuggestLoading(false);
      }
      // 实际生成在用户确认/跳过后触发（_doRegenerate）
      return;
    }

    // 无项目ID时直接生成
    const cleanItem = { ...item, generationError: undefined, content: undefined };
    await generateItemContent(cleanItem, outlineData.project_overview || '');
  };

  const _doRegenerate = async (confirmedMaterialIds: string[]) => {
    if (!pendingGenerateItem || !outlineData) return;
    const { item } = pendingGenerateItem;
    setLeafItems(prevItems => {
      const newItems = [...prevItems];
      const index = newItems.findIndex(i => i.id === item.id);
      if (index !== -1) {
        newItems[index] = { ...newItems[index], generationError: undefined, content: undefined };
      }
      return newItems;
    });
    const cleanItem = { ...item, generationError: undefined, content: undefined, _confirmedMaterialIds: confirmedMaterialIds };
    setPendingGenerateItem(null);
    await generateItemContent(cleanItem, outlineData.project_overview || '');
  };

  const handleGenerateContent = () => {
    console.log('[ContentEdit] handleGenerateContent called', {
      hasOutlineData: !!outlineData,
      outlineLength: outlineData?.outline?.length,
      leafItemsLength: leafItems.length,
    });
    if (!outlineData || leafItems.length === 0) {
      console.warn('[ContentEdit] Early return: outlineData or leafItems empty');
      return;
    }

    const itemsToGenerate = leafItems.filter(item => 
      !item.content || item.generationError
    );
    
    if (itemsToGenerate.length === 0) {
      message.info('所有章节内容已生成完成，无需重新生成。');
      return;
    }

    setItemsToGenerateCount(itemsToGenerate.length);
    setShowGenerateModal(true);
  };

  const handleConfirmGenerate = async () => {
    setShowGenerateModal(false);
    if (!outlineData) return;

    const itemsToGenerate = leafItems.filter(item =>
      !item.content || item.generationError
    );
    if (itemsToGenerate.length === 0) return;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsGenerating(true);
    setProgress({
      total: itemsToGenerate.length,
      completed: 0,
      current: '',
      failed: [],
      generating: new Set<string>()
    });

    try {
      const concurrency = 1;
      const updatedItems = [...leafItems];
      const delayBetweenRequests = 5000; 
      
      for (let i = 0; i < itemsToGenerate.length; i += concurrency) {
        if (abortControllerRef.current?.signal.aborted) break;

        const batch = itemsToGenerate.slice(i, i + concurrency);
        const promises = batch.map(item => 
          generateItemContent(item, outlineData.project_overview || '')
            .then(updatedItem => {
              const index = updatedItems.findIndex(ui => ui.id === updatedItem.id);
              if (index !== -1) {
                updatedItems[index] = updatedItem;
              }
              setProgress(prev => ({ ...prev, completed: prev.completed + 1 }));
              return updatedItem;
            })
            .catch(error => {
              console.error(`生成内容失败 ${item.title}:`, error);
              setProgress(prev => ({ ...prev, completed: prev.completed + 1 }));
              return item; 
            })
        );

        await Promise.all(promises);
        
        if (i + concurrency < itemsToGenerate.length) {
          await new Promise(resolve => setTimeout(resolve, delayBetweenRequests));
        }
      }

      setLeafItems(updatedItems);
      if (!abortControllerRef.current?.signal.aborted) {
        message.success('标书生成完成');
      }
    } catch (error) {
      console.error('生成内容时出错:', error);
      message.error('部分内容生成出错，请查看日志或重试');
    } finally {
      setIsGenerating(false);
      abortControllerRef.current = null;
      setProgress(prev => ({ ...prev, current: '', generating: new Set<string>() }));
    }
  };

  const handleStopGeneration = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsGenerating(false);
    setProgress(prev => ({ ...prev, current: '', generating: new Set<string>() }));
    message.info('已停止生成');
  };

  const getLatestContent = (item: OutlineItem): string => {
    if (!item.children || item.children.length === 0) {
      const leafItem = leafItems.find(leaf => leaf.id === item.id);
      return leafItem?.content || item.content || '';
    }
    return item.content || '';
  };

  const [showExportDialog, setShowExportDialog] = useState(false);

  const buildExportOutline = useCallback((items: OutlineItem[]): OutlineItem[] => {
    const getContent = (item: OutlineItem): string => {
      if (!item.children || item.children.length === 0) {
        const leafItem = leafItems.find(leaf => leaf.id === item.id);
        return leafItem?.content || item.content || '';
      }
      return item.content || '';
    };
    return items.map(item => {
      const latestContent = getContent(item);
      const exportedItem: OutlineItem = { ...item, content: latestContent };
      if (item.children && item.children.length > 0) {
        exportedItem.children = buildExportOutline(item.children);
      }
      return exportedItem;
    });
  }, [leafItems]);

  if (!outlineData) {
    return (
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        <ProCard>
          <div style={{ textAlign: 'center', padding: '48px 0' }}>
            <FileTextOutlined style={{ fontSize: 48, color: '#bfbfbf', marginBottom: 16 }} />
            <Typography.Title level={5} style={{ color: '#595959', margin: 0 }}>暂无内容</Typography.Title>
            <Typography.Text type="secondary" style={{ marginTop: 8, display: 'block' }}>
              请先在"目录编辑"步骤中生成目录结构
            </Typography.Text>
          </div>
        </ProCard>
      </div>
    );
  }

  const completedItems = leafItems.filter(item => item.content && !item.generationError).length;
  const failedItems = leafItems.filter(item => item.generationError).length;

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', paddingBottom: 64 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 顶部工具栏 */}
        <ProCard
          title="标书内容"
          headerBordered
          extra={
            <Space>
              {projectId && (
                <Button
                  icon={<ThunderboltOutlined />}
                  loading={autoBindLoading}
                  onClick={() => { void handleAutoBind(); }}
                  title="根据章节关键词自动匹配并绑定最佳素材"
                >
                  智能绑定素材
                </Button>
              )}
              {projectId && (
                <Button
                  icon={<ProfileOutlined />}
                  onClick={() => setShowClauseResponseModal(true)}
                  title="生成技术参数/条款逐条响应"
                >
                  条款逐条响应
                </Button>
              )}
              {onToggleConsistency && (
                <Button
                  icon={<SafetyCertificateOutlined />}
                  onClick={() => {
                    const chapterSummaries = leafItems
                      .filter(item => item.content && !item.generationError)
                      .map(item => ({
                        chapter_number: item.id,
                        title: item.title,
                        summary: item.content || '',
                        chapter_id: item.id,
                      }));
                    onToggleConsistency(chapterSummaries);
                  }}
                  title="跨章节一致性检查"
                >
                  一致性检查
                </Button>
              )}
              {projectId && (
                <Badge
                  count={
                    consistencyResult
                      ? consistencyResult.issues.filter(i => i.severity === 'error').length
                      : 0
                  }
                  color="#cf1322"
                  offset={[-4, 4]}
                >
                  <Button
                    icon={<SafetyCertificateOutlined />}
                    onClick={() => {
                      if (showConsistencyPanel) {
                        setShowConsistencyPanel(false);
                      } else {
                        void handleRunConsistencyCheck();
                      }
                    }}
                    title="全文一致性校验（AI 交叉检查）"
                    style={
                      consistencyResult &&
                      consistencyResult.issues.filter(i => i.severity === 'error').length > 0
                        ? { borderColor: '#cf1322', color: '#cf1322' }
                        : {}
                    }
                  >
                    全文校验
                  </Button>
                </Badge>
              )}
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleGenerateContent}
                disabled={isGenerating}
                style={{ backgroundColor: '#1677ff' }}
                loading={isGenerating}
              >
                生成标书
              </Button>

              <Button
                icon={<DownloadOutlined />}
                onClick={() => setShowExportDialog(true)}
                disabled={isGenerating}
              >
                导出文档
              </Button>
            </Space>
          }
        >
          <Space size="middle" style={{ marginBottom: isGenerating ? 16 : 0, width: '100%' }}>
            <Typography.Text type="secondary">
              共 {leafItems.length} 个章节，已生成 {completedItems} 个
              {failedItems > 0 && (
                <Typography.Text type="danger" style={{ marginLeft: 8 }}>失败 {failedItems} 个</Typography.Text>
              )}
            </Typography.Text>
          </Space>
          
          {/* 进度条 */}
          {isGenerating && (
            <div style={{
              marginTop: 8,
              backgroundColor: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              padding: '12px 16px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
                  <LoadingOutlined style={{ color: '#1677ff', fontSize: 14, flexShrink: 0 }} />
                  <Typography.Text
                    style={{ fontSize: 13, color: '#374151', flex: 1, minWidth: 0 }}
                    ellipsis={{ tooltip: progress.current }}
                  >
                    {progress.current || '准备中...'}
                  </Typography.Text>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0, marginLeft: 12 }}>
                  <span style={{
                    fontSize: 13,
                    fontWeight: 500,
                    color: '#6b7280',
                    backgroundColor: '#e5e7eb',
                    borderRadius: 20,
                    padding: '2px 10px',
                    letterSpacing: '0.02em',
                  }}>
                    {progress.completed} / {progress.total}
                  </span>
                  <Tooltip title="停止生成">
                    <Button
                      type="text"
                      size="small"
                      icon={<StopOutlined />}
                      onClick={handleStopGeneration}
                      style={{
                        color: '#9ca3af',
                        padding: '0 6px',
                        height: 26,
                        borderRadius: 6,
                        transition: 'color 0.15s',
                      }}
                      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = '#ef4444'; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = '#9ca3af'; }}
                    />
                  </Tooltip>
                </div>
              </div>
              <Progress
                percent={Math.round((progress.completed / progress.total) * 100)}
                status="active"
                strokeColor={{ '0%': '#3b82f6', '100%': '#1677ff' }}
                trailColor="#dbeafe"
                strokeWidth={6}
                showInfo={false}
                style={{ margin: 0 }}
              />
            </div>
          )}
        </ProCard>

        {/* 文档内容 */}
        <ProCard>
          <div style={{ padding: '0 24px' }}>
            {/* 文档标题 */}
            <Typography.Title level={2} style={{ textAlign: 'center', marginBottom: 32 }}>
              {outlineData.project_name || '投标技术文件'}
            </Typography.Title>
            
            {/* 项目概述 */}
            {outlineData.project_overview && (
              <Card 
                size="small" 
                title={<span style={{ color: '#0958d9' }}><FileTextOutlined style={{ marginRight: 8 }} />项目概述</span>} 
                styles={{ header: { backgroundColor: '#e6f4ff', borderColor: '#91caff' } }}
                style={{ marginBottom: 32, borderColor: '#91caff' }}
              >
                <Typography.Text style={{ color: '#003eb3' }}>{outlineData.project_overview}</Typography.Text>
              </Card>
            )}

            {/* 目录结构和内容 */}
            <div style={{ paddingBottom: 24 }}>
              {renderOutline(outlineData.outline)}
            </div>
          </div>
        </ProCard>

        {/* 底部统计 */}
        <ProCard style={{ padding: '12px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Space size="large">
              <span style={{ color: '#52c41a' }}><CheckCircleOutlined style={{ marginRight: 4 }} /> 已完成: {completedItems}</span>
              <span style={{ color: '#8c8c8c' }}><FileTextOutlined style={{ marginRight: 4 }} /> 待生成: {leafItems.length - completedItems}</span>
              {progress.failed.length > 0 && (
                <span style={{ color: '#ff4d4f' }}><ExclamationCircleOutlined style={{ marginRight: 4 }} /> 失败: {progress.failed.length}</span>
              )}
            </Space>
            <Typography.Text type="secondary">
              总字数: {leafItems.reduce((sum, item) => sum + (item.content?.length || 0), 0)}
            </Typography.Text>
          </div>
        </ProCard>
      </Space>

      {/* 回到顶部按钮 */}
      {showScrollToTop && (
        <FloatButton.BackTop 
          target={() => document.getElementById('app-main-scroll') || window}
          visibilityHeight={300}
        />
      )}

      <MaterialSuggestPanel
        visible={showSuggestPanel}
        loading={suggestLoading}
        suggestions={suggestItems}
        onConfirm={(ids) => { setShowSuggestPanel(false); void _doRegenerate(ids); }}
        onSkip={() => { setShowSuggestPanel(false); void _doRegenerate([]); }}
        onCancel={() => { setShowSuggestPanel(false); setPendingGenerateItem(null); }}
      />

      <MaterialMarkerModal
        visible={showMaterialMarkerModal}
        target={materialMarkerTarget}
        selectedBindingId={selectedBindingId}
        bindings={materialMarkerBindings}
        onSelectBinding={setSelectedBindingId}
        onOk={() => { void handleInsertMaterialMarker(); }}
        onCancel={() => setShowMaterialMarkerModal(false)}
      />

      <ReverseEnhanceModal
        visible={showReverseEnhanceModal}
        target={reverseEnhanceTarget}
        isLoading={isReverseEnhancing}
        result={reverseEnhanceResult}
        onCopy={() => { void copyText(buildReverseEnhanceSummary(reverseEnhanceResult!), '补强建议已复制'); }}
        onClose={() => setShowReverseEnhanceModal(false)}
      />

      <ClauseResponseModal
        visible={showClauseResponseModal}
        clauseText={clauseText}
        knowledgeContext={clauseKnowledgeContext}
        isLoading={isGeneratingClauseResponse}
        result={clauseResponseResult}
        onClauseTextChange={setClauseText}
        onKnowledgeContextChange={setClauseKnowledgeContext}
        onGenerate={() => { void handleGenerateClauseResponse(); }}
        onCopy={() => { void copyText(clauseResponseResult!.content, '逐条响应内容已复制'); }}
        onClose={() => setShowClauseResponseModal(false)}
      />

      {/* 校对结果面板 */}
      <ProofreadPanel
        isOpen={showProofreadPanel}
        onClose={handleCloseProofreadPanel}
        proofreadResult={proofreadResult}
        isLoading={isProofreading}
        streamingText={proofreadStreamingText}
        onApplySuggestion={handleApplySuggestion}
        onEditContent={handleEditContent}
        chapterTitle={proofreadChapterTitle}
      />

      {/* 生成确认弹窗 */}
      <Modal
        title={null}
        open={showGenerateModal}
        onOk={() => { void handleConfirmGenerate(); }}
        onCancel={() => setShowGenerateModal(false)}
        okText="开始生成"
        cancelText="取消"
        okButtonProps={{ type: 'primary', size: 'middle' }}
        width={400}
        centered
      >
        <div style={{ padding: '8px 0 4px' }}>
          <div style={{ textAlign: 'center', marginBottom: 20 }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 48,
              height: 48,
              borderRadius: '50%',
              backgroundColor: '#eff6ff',
              marginBottom: 12,
            }}>
              <PlayCircleOutlined style={{ fontSize: 22, color: '#1677ff' }} />
            </div>
            <Typography.Title level={5} style={{ margin: 0, color: '#111827' }}>
              生成标书内容
            </Typography.Title>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            backgroundColor: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            padding: '14px 20px',
            marginBottom: 16,
          }}>
            <span style={{ fontSize: 28, fontWeight: 700, color: '#1677ff', lineHeight: 1 }}>
              {itemsToGenerateCount}
            </span>
            <span style={{ fontSize: 14, color: '#6b7280' }}>个章节待生成</span>
          </div>

          <Typography.Text type="secondary" style={{ fontSize: 13, display: 'block', textAlign: 'center' }}>
            将生成所有空内容及失败章节，过程中可随时停止
          </Typography.Text>
        </div>
      </Modal>

      {/* 导出文档弹窗 */}
      <ExportDialog
        visible={showExportDialog}
        onClose={() => setShowExportDialog(false)}
        projectName={outlineData?.project_name || '标书文档'}
        projectOverview={outlineData?.project_overview}
        projectId={projectId}
        getExportOutline={() => outlineData ? buildExportOutline(outlineData.outline) : []}
        consistencyResult={consistencyResult}
      />

      {/* 全文一致性校验面板 */}
      <ConsistencyPanel
        isOpen={showConsistencyPanel}
        onClose={() => setShowConsistencyPanel(false)}
        onRecheck={() => { void handleRunConsistencyCheck(); }}
        isChecking={isConsistencyChecking}
        result={consistencyResult}
        lastCheckedAt={consistencyLastCheckedAt}
        onJumpToChapter={(chapterId, chapterTitle) => {
          // 通过 chapter_id 映射找到 chapter_number，并滚动到对应章节
          const chapterNumber = Object.entries(chapterIdMap).find(
            ([, id]) => id === chapterId
          )?.[0];
          if (chapterNumber) {
            onChapterSelect(chapterNumber);
            const el = document.getElementById(`chapter-${chapterNumber}`);
            if (el) {
              el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          } else {
            message.info(`章节：${chapterTitle}`);
          }
        }}
      />

      {/* 套用模板弹窗 */}
      <Modal
        title={
          <Space>
            <BookOutlined style={{ color: '#1677ff' }} />
            <span>从知识库套用章节模板</span>
            {templatePickerTarget && (
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                — {templatePickerTarget.chapterNumber} {templatePickerTarget.title}
              </Typography.Text>
            )}
          </Space>
        }
        open={templatePickerVisible}
        onCancel={() => setTemplatePickerVisible(false)}
        footer={null}
        width={680}
        destroyOnClose
      >
        <div style={{ marginBottom: 12 }}>
          <Input.Search
            placeholder="搜索模板名称、分类或标签"
            value={templateKeyword}
            onChange={(e) => setTemplateKeyword(e.target.value)}
            onSearch={(v) => void handleTemplateSearch(v)}
            onPressEnter={(e) => void handleTemplateSearch((e.target as HTMLInputElement).value)}
            allowClear
            onClear={() => void handleTemplateSearch('')}
          />
        </div>
        <Spin spinning={templateListLoading}>
          {templateList.length === 0 && !templateListLoading ? (
            <div style={{ textAlign: 'center', padding: '32px 0', color: '#8c8c8c' }}>
              暂无匹配的模板
            </div>
          ) : (
            <List
              dataSource={templateList}
              style={{ maxHeight: 480, overflowY: 'auto' }}
              renderItem={(tpl) => (
                <List.Item
                  key={tpl.id}
                  style={{ cursor: 'pointer', padding: '10px 8px', borderRadius: 6 }}
                  actions={[
                    <Button
                      key="apply"
                      type="primary"
                      size="small"
                      onClick={() => void handleApplyTemplate(tpl)}
                    >
                      套用
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space size={[4, 4]} wrap>
                        <Typography.Text strong>{tpl.name}</Typography.Text>
                        {tpl.category && (
                          <Tag color="blue" style={{ fontSize: 11 }}>
                            {tpl.category}
                          </Tag>
                        )}
                        {tpl.tags.slice(0, 2).map((t) => (
                          <Tag key={t} style={{ fontSize: 11 }}>
                            {t}
                          </Tag>
                        ))}
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={2} style={{ width: '100%' }}>
                        {tpl.source_project_name && (
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            来源：{tpl.source_project_name}
                          </Typography.Text>
                        )}
                        <Typography.Text
                          type="secondary"
                          style={{ fontSize: 12 }}
                          ellipsis
                        >
                          {tpl.content.slice(0, 80)}…
                        </Typography.Text>
                        <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                          已使用 {tpl.usage_count} 次 · {new Date(tpl.created_at).toLocaleDateString()}
                        </Typography.Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Spin>
      </Modal>

      {/* 存为模板弹窗 */}
      <Modal
        title={
          <Space>
            <SaveOutlined style={{ color: '#52c41a' }} />
            <span>保存为章节模板</span>
          </Space>
        }
        open={saveTemplateVisible}
        onOk={() => void handleConfirmSaveTemplate()}
        onCancel={() => {
          setSaveTemplateVisible(false);
          saveTemplateForm.resetFields();
        }}
        okText="保存"
        cancelText="取消"
        confirmLoading={saveTemplateLoading}
        width={480}
        destroyOnClose
      >
        <Form form={saveTemplateForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item
            name="name"
            label="模板名称"
            rules={[{ required: true, message: '请输入模板名称' }]}
          >
            <Input placeholder="如：安全方案-中标版" maxLength={200} showCount />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Select placeholder="选择分类（可选）" allowClear>
              {TEMPLATE_CATEGORIES.map((c) => (
                <Select.Option key={c} value={c}>{c}</Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select
              mode="tags"
              placeholder="输入标签后按 Enter（可选）"
              tokenSeparators={[',']}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ContentEdit;
