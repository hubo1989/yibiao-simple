/**
 * 内容编辑页面 - 完整标书预览和生成
 */
import React, { useState, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { OutlineData, OutlineItem } from '../types';
import {
  DocumentTextIcon,
  PlayIcon,
  DocumentArrowDownIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowUpIcon,
  ChatBubbleLeftIcon,
  DocumentCheckIcon,
} from '@heroicons/react/24/outline';
import { contentApi, documentApi, proofreadApi, chapterApi, ChapterContentRequest } from '../services/api';
import { saveAs } from 'file-saver';
import { draftStorage } from '../utils/draftStorage';
import ChapterStatusBadge from '../components/ChapterStatusBadge';
import ProofreadPanel from '../components/ProofreadPanel';
import type { ChapterStatus } from '../types/chapter';
import type { ProofreadResult, ProofreadIssue } from '../types/proofread';

interface ContentEditProps {
  outlineData: OutlineData | null;
  selectedChapter: string;
  onChapterSelect: (chapterId: string) => void;
  projectId?: string;
  onToggleComments?: (chapterId: string) => void;
  onToggleConsistency?: () => void;
}

interface GenerationProgress {
  total: number;
  completed: number;
  current: string;
  failed: string[];
  generating: Set<string>; // 正在生成的项目ID集合
}


const ContentEdit: React.FC<ContentEditProps> = ({
  outlineData,
  selectedChapter,
  onChapterSelect,
  projectId,
  onToggleComments,
  onToggleConsistency,
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

  // 校对相关状态
  const [showProofreadPanel, setShowProofreadPanel] = useState(false);
  const [proofreadChapterId, setProofreadChapterId] = useState<string | null>(null);
  const [proofreadChapterTitle, setProofreadChapterTitle] = useState('');
  const [proofreadResult, setProofreadResult] = useState<ProofreadResult | null>(null);
  const [isProofreading, setIsProofreading] = useState(false);
  const [proofreadStreamingText, setProofreadStreamingText] = useState('');

  // 收集所有叶子节点
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

  // 获取章节的上级章节信息
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

  // 获取章节的同级章节信息
  const getSiblingChapters = useCallback((targetId: string, items: OutlineItem[]): OutlineItem[] => {
    // 直接在当前级别查找
    if (items.some(item => item.id === targetId)) {
      return items;
    }
    
    // 递归在子级别查找
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
    if (outlineData) {
      const leaves = collectLeafItems(outlineData.outline);
      // 恢复本地缓存的正文内容（仅对叶子节点生效）
      const filtered = draftStorage.filterContentByOutlineLeaves(outlineData.outline);
      const mergedLeaves = leaves.map((leaf) => {
        const cached = filtered[leaf.id];
        return cached ? { ...leaf, content: cached } : leaf;
      });

      // 目录变更时，顺手清理掉无效的旧缓存（只保留当前叶子节点）
      draftStorage.saveContentById(filtered);

      setLeafItems(mergedLeaves);
      setProgress(prev => ({ ...prev, total: leaves.length }));
    }
  }, [outlineData, collectLeafItems]);

  // 监听页面滚动，控制回到顶部按钮的显示
  useEffect(() => {
    // 现在主内容区为内部滚动容器（App.tsx: #app-main-scroll），不能只监听 window
    const scrollContainer = document.getElementById('app-main-scroll');

    const handleScroll = () => {
      const scrollTop = scrollContainer
        ? scrollContainer.scrollTop
        : (window.pageYOffset || document.documentElement.scrollTop);
      setShowScrollToTop(scrollTop > 300);
    };

    // 初始化计算一次，避免刷新后位置不对
    handleScroll();

    const target: any = scrollContainer || window;
    target.addEventListener('scroll', handleScroll);
    return () => target.removeEventListener('scroll', handleScroll);
  }, []);

  // 获取叶子节点的实时内容
  const getLeafItemContent = (itemId: string): string | undefined => {
    const leafItem = leafItems.find(leaf => leaf.id === itemId);
    return leafItem?.content;
  };

  // 检查是否为叶子节点
  const isLeafNode = (item: OutlineItem): boolean => {
    return !item.children || item.children.length === 0;
  };

  // 根据内容状态确定章节状态
  const getChapterStatus = (item: OutlineItem, isGenerating: boolean): ChapterStatus => {
    if (isGenerating) return 'generated';
    if (!isLeafNode(item)) {
      // 非叶子节点根据子节点状态判断
      return 'pending';
    }
    const content = getLeafItemContent(item.id) || item.content;
    if (content) return 'generated';
    return 'pending';
  };

  // 触发章节校对
  const handleProofreadChapter = async (chapterId: string, chapterTitle: string) => {
    setProofreadChapterId(chapterId);
    setProofreadChapterTitle(chapterTitle);
    setProofreadResult(null);
    setProofreadStreamingText('');
    setShowProofreadPanel(true);
    setIsProofreading(true);

    try {
      const response = await proofreadApi.proofreadChapter(chapterId);
      if (!response.ok) {
        throw new Error('校对请求失败');
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
              // 忽略JSON解析错误
            }
          }
        }
      }
    } catch (error) {
      console.error('校对失败:', error);
      alert('校对失败，请重试');
    } finally {
      setIsProofreading(false);
    }
  };

  // 接受校对建议
  const handleApplySuggestion = async (issue: ProofreadIssue) => {
    if (!proofreadChapterId) return;

    try {
      // 获取当前章节内容
      const chapterData = await chapterApi.get(proofreadChapterId);
      let content = chapterData.content || '';

      // 简单实现：将建议附加到内容末尾（实际场景中可能需要更智能的替换）
      // 这里我们用一个占位符标记修改
      const suggestionNote = `\n\n<!-- 校对建议：${issue.suggestion} -->`;

      // 更新章节内容
      await chapterApi.updateContent(
        proofreadChapterId,
        content + suggestionNote,
        `应用校对建议：${issue.issue}`
      );

      // 更新本地状态
      setLeafItems(prevItems =>
        prevItems.map(item =>
          item.id === proofreadChapterId
            ? { ...item, content: content + suggestionNote }
            : item
        )
      );

      alert('建议已应用到内容中');
    } catch (error) {
      console.error('应用建议失败:', error);
      alert('应用建议失败');
    }
  };

  // 手动编辑内容
  const handleEditContent = (issue: ProofreadIssue) => {
    // 提示用户去编辑
    alert(`请根据以下建议手动编辑内容：\n\n${issue.suggestion}`);
  };

  // 关闭校对面板
  const handleCloseProofreadPanel = () => {
    setShowProofreadPanel(false);
    setProofreadChapterId(null);
    setProofreadResult(null);
    setProofreadStreamingText('');
  };

  // 渲染目录结构
  const renderOutline = (items: OutlineItem[], level: number = 1): React.ReactElement[] => {
    return items.map((item) => {
      const isLeaf = isLeafNode(item);
      const currentContent = isLeaf ? getLeafItemContent(item.id) : item.content;
      const isGeneratingThis = progress.generating.has(item.id);
      const chapterStatus = getChapterStatus(item, isGeneratingThis);

      return (
        <div key={item.id} className={`mb-${level === 1 ? '8' : '4'}`}>
          {/* 标题和状态 */}
          <div className="flex items-center space-x-3 mb-2">
            <div className={`text-${level === 1 ? 'xl' : level === 2 ? 'lg' : 'base'} font-${level === 1 ? 'bold' : 'semibold'} text-gray-900`}>
              {item.id} {item.title}
            </div>
            <ChapterStatusBadge status={chapterStatus} />
            {isLeaf && currentContent && (
              <button
                onClick={() => handleProofreadChapter(item.id, item.title)}
                disabled={isProofreading}
                className="inline-flex items-center px-2 py-1 text-xs text-purple-600 hover:text-purple-800 hover:bg-purple-50 rounded disabled:opacity-50"
                title="AI 校对"
              >
                <DocumentCheckIcon className="w-3 h-3 mr-1" />
                校对
              </button>
            )}
            {isLeaf && onToggleComments && (
              <button
                onClick={() => onToggleComments(item.id)}
                className="inline-flex items-center px-2 py-1 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
                title="查看批注"
              >
                <ChatBubbleLeftIcon className="w-3 h-3 mr-1" />
                批注
              </button>
            )}
          </div>

          {/* 描述 */}
          <div className="text-sm text-gray-600 mb-4">
            {item.description}
          </div>

          {/* 内容（仅叶子节点） */}
          {isLeaf && (
            <div className="border-l-4 border-blue-200 pl-4 mb-6">
              {currentContent ? (
                <div className="prose max-w-none">
                  <ReactMarkdown>{currentContent}</ReactMarkdown>
                </div>
              ) : (
                <div className="text-gray-400 italic py-4">
                  <DocumentTextIcon className="inline w-4 h-4 mr-2" />
                  {isGeneratingThis ? (
                    <span className="text-blue-600">正在生成内容...</span>
                  ) : (
                    '内容待生成...'
                  )}
                </div>
              )}
            </div>
          )}

          {/* 子章节 */}
          {item.children && item.children.length > 0 && (
            <div className={`ml-${level * 4} mt-4`}>
              {renderOutline(item.children, level + 1)}
            </div>
          )}
        </div>
      );
    });
  };

  // 生成单个章节内容
  const generateItemContent = async (item: OutlineItem, projectOverview: string): Promise<OutlineItem> => {
    if (!outlineData) throw new Error('缺少目录数据');
    
    // 将当前项目添加到正在生成的集合中
    setProgress(prev => ({ 
      ...prev, 
      current: item.title,
      generating: new Set([...Array.from(prev.generating), item.id])
    }));
    
    try {
      // 获取上级章节和同级章节信息
      const parentChapters = getParentChapters(item.id, outlineData.outline);
      const siblingChapters = getSiblingChapters(item.id, outlineData.outline);

      const request: ChapterContentRequest = {
        chapter: item,
        parent_chapters: parentChapters,
        sibling_chapters: siblingChapters,
        project_overview: projectOverview
      };

      const response = await contentApi.generateChapterContentStream(request);

      if (!response.ok) throw new Error('生成失败');

      const reader = response.body?.getReader();
      if (!reader) throw new Error('无法读取响应');

      let content = '';
      const updatedItem = { ...item };
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = new TextDecoder().decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;
            
            try {
              const parsed = JSON.parse(data);
              
              if (parsed.status === 'streaming' && parsed.full_content) {
                // 实时更新内容
                content = parsed.full_content;
                updatedItem.content = content;
                // 本地持久化（刷新后可恢复）
                draftStorage.upsertChapterContent(item.id, content);
                
                // 实时更新叶子节点数据以触发重新渲染
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
                // 本地持久化（最终结果）
                draftStorage.upsertChapterContent(item.id, content);
              } else if (parsed.status === 'error') {
                throw new Error(parsed.message);
              }
            } catch (e) {
              // 忽略JSON解析错误
            }
          }
        }
      }

      return updatedItem;
    } catch (error) {
      setProgress(prev => ({
        ...prev,
        failed: [...prev.failed, item.title]
      }));
      throw error;
    } finally {
      // 从正在生成的集合中移除当前项目
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

  // 开始生成所有内容
  const handleGenerateContent = async () => {
    if (!outlineData || leafItems.length === 0) return;

    setIsGenerating(true);
    setProgress({
      total: leafItems.length,
      completed: 0,
      current: '',
      failed: [],
      generating: new Set<string>()
    });

    try {
      // 使用5个并发线程生成内容
      const concurrency = 5;
      const updatedItems = [...leafItems];
      
      for (let i = 0; i < leafItems.length; i += concurrency) {
        const batch = leafItems.slice(i, i + concurrency);
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
              return item; // 返回原始项目
            })
        );

        await Promise.all(promises);
      }

      // 更新状态
      setLeafItems(updatedItems);
      
      // 这里需要更新整个outlineData，但由于我们只有props，需要通过回调通知父组件
      // 暂时只更新本地状态
      
    } catch (error) {
      console.error('生成内容时出错:', error);
    } finally {
      setIsGenerating(false);
      setProgress(prev => ({ ...prev, current: '', generating: new Set<string>() }));
    }
  };

  // 获取叶子节点的最新内容（包括生成的内容）
  const getLatestContent = (item: OutlineItem): string => {
    if (!item.children || item.children.length === 0) {
      // 叶子节点，从 leafItems 获取最新内容
      const leafItem = leafItems.find(leaf => leaf.id === item.id);
      return leafItem?.content || item.content || '';
    }
    return item.content || '';
  };

  // 解析Markdown内容为Word段落
  // （已提取到文件顶层，供后续导出Word等复用）

  // 滚动到页面顶部
  const scrollToTop = () => {
    const scrollContainer = document.getElementById('app-main-scroll');
    if (scrollContainer) {
      scrollContainer.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // 导出Word文档
  const handleExportWord = async () => {
    if (!outlineData) return;

    try {
      // 构建带有最新内容的导出数据（leafItems 中存的是实时内容）
      const buildExportOutline = (items: OutlineItem[]): OutlineItem[] => {
        return items.map(item => {
          const latestContent = getLatestContent(item);
          const exportedItem: OutlineItem = {
            ...item,
            content: latestContent,
          };
          if (item.children && item.children.length > 0) {
            exportedItem.children = buildExportOutline(item.children);
          }
          return exportedItem;
        });
      };

      const exportPayload = {
        project_name: outlineData.project_name,
        project_overview: outlineData.project_overview,
        outline: buildExportOutline(outlineData.outline),
      };

      const response = await documentApi.exportWord(exportPayload);
      if (!response.ok) {
        throw new Error('导出失败');
      }
      const blob = await response.blob();
      saveAs(blob, `${outlineData.project_name || '标书文档'}.docx`);
      
    } catch (error) {
      console.error('导出失败:', error);
      alert('导出失败，请重试');
    }
  };

  if (!outlineData) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">暂无内容</h3>
            <p className="mt-1 text-sm text-gray-500">
              请先在"目录编辑"步骤中生成目录结构
            </p>
          </div>
        </div>
      </div>
    );
  }

  const completedItems = leafItems.filter(item => item.content).length;

  return (
    <div className="max-w-6xl mx-auto">
      {/* 顶部工具栏 */}
      <div className="bg-white rounded-lg shadow mb-6">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">标书内容</h2>
              <p className="text-sm text-gray-500 mt-1">
                共 {leafItems.length} 个章节，已生成 {completedItems} 个
                {progress.failed.length > 0 && (
                  <span className="text-red-500 ml-2">失败 {progress.failed.length} 个</span>
                )}
              </p>
            </div>
            
            <div className="flex items-center space-x-3">
              {onToggleConsistency && (
                <button
                  onClick={onToggleConsistency}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500"
                  title="跨章节一致性检查"
                >
                  <DocumentCheckIcon className="w-4 h-4 mr-2" />
                  一致性检查
                </button>
              )}
              <button
                onClick={handleGenerateContent}
                disabled={isGenerating}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <PlayIcon className="w-4 h-4 mr-2" />
                {isGenerating ? '生成中...' : '生成标书'}
              </button>

              <button
                onClick={handleExportWord}
                disabled={isGenerating}
                className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <DocumentArrowDownIcon className="w-4 h-4 mr-2" />
                导出Word
              </button>
            </div>
          </div>
          
          {/* 进度条 */}
          {isGenerating && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-sm text-gray-600 mb-2">
                <span>正在生成: {progress.current}</span>
                <span>{progress.completed} / {progress.total}</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${(progress.completed / progress.total) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 文档内容 */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-8">
          <div className="prose max-w-none">
            {/* 文档标题 */}
            <h1 className="text-3xl font-bold text-gray-900 mb-8">
              {outlineData.project_name || '投标技术文件'}
            </h1>
            
            {/* 项目概述 */}
            {outlineData.project_overview && (
              <div className="bg-blue-50 border-l-4 border-blue-400 p-6 mb-8">
                <h2 className="text-lg font-semibold text-blue-900 mb-2">项目概述</h2>
                <p className="text-blue-800">{outlineData.project_overview}</p>
              </div>
            )}

            {/* 目录结构和内容 */}
            <div className="space-y-8">
              {renderOutline(outlineData.outline)}
            </div>
          </div>
        </div>
      </div>

      {/* 底部统计 */}
      <div className="mt-6 bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between text-sm text-gray-600">
          <div className="flex items-center space-x-6">
            <div className="flex items-center">
              <CheckCircleIcon className="w-4 h-4 text-green-500 mr-1" />
              <span>已完成: {completedItems}</span>
            </div>
            <div className="flex items-center">
              <DocumentTextIcon className="w-4 h-4 text-gray-400 mr-1" />
              <span>待生成: {leafItems.length - completedItems}</span>
            </div>
            {progress.failed.length > 0 && (
              <div className="flex items-center">
                <ExclamationCircleIcon className="w-4 h-4 text-red-500 mr-1" />
                <span className="text-red-600">失败: {progress.failed.length}</span>
              </div>
            )}
          </div>
          <div>
            <span>总字数: {leafItems.reduce((sum, item) => sum + (item.content?.length || 0), 0)}</span>
          </div>
        </div>
      </div>

      {/* 回到顶部按钮 */}
      {showScrollToTop && (
        <button
          onClick={scrollToTop}
          className="fixed bottom-24 right-6 bg-blue-600 hover:bg-blue-700 text-white rounded-full p-3 shadow-lg transition-all duration-300 hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 z-[60]"
          aria-label="回到顶部"
        >
          <ArrowUpIcon className="w-5 h-5" />
        </button>
      )}

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
    </div>
  );
};

export default ContentEdit;