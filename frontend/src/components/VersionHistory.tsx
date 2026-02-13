/**
 * 版本历史组件
 * 侧边栏抽屉，显示版本列表、版本预览和 Diff 对比
 */
import React, { useState, useEffect, useCallback } from 'react';
import { XMarkIcon, ClockIcon, ArrowPathIcon, DocumentTextIcon } from '@heroicons/react/24/outline';
import { versionApi } from '../services/api';
import type {
  VersionSummary,
  VersionResponse,
  VersionDiffResponse,
  ChapterChange,
  ChangeType,
} from '../types/version';
import { CHANGE_TYPE_LABELS, CHANGE_TYPE_COLORS } from '../types/version';

interface VersionHistoryProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  chapterId?: string;
}

const VersionHistory: React.FC<VersionHistoryProps> = ({
  projectId,
  isOpen,
  onClose,
  chapterId,
}) => {
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 预览状态
  const [previewVersion, setPreviewVersion] = useState<VersionResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Diff 对比状态
  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
  const [diffResult, setDiffResult] = useState<VersionDiffResponse | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  // 回滚确认状态
  const [rollbackConfirm, setRollbackConfirm] = useState<VersionSummary | null>(null);
  const [rollbackLoading, setRollbackLoading] = useState(false);

  const loadVersions = useCallback(async () => {
    if (!projectId) return;

    try {
      setLoading(true);
      setError(null);
      const result = await versionApi.list(projectId, {
        chapter_id: chapterId,
        limit: 50,
      });
      setVersions(result.items);
      setTotal(result.total);
    } catch (err) {
      setError('加载版本历史失败');
      console.error('加载版本历史失败:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId, chapterId]);

  useEffect(() => {
    if (isOpen) {
      loadVersions();
      // 重置状态
      setPreviewVersion(null);
      setSelectedVersions([]);
      setDiffResult(null);
    }
  }, [isOpen, loadVersions]);

  const handleVersionSelect = (versionId: string) => {
    if (selectedVersions.includes(versionId)) {
      setSelectedVersions(selectedVersions.filter(id => id !== versionId));
    } else if (selectedVersions.length < 2) {
      setSelectedVersions([...selectedVersions, versionId]);
    } else {
      // 已选2个，替换第一个
      setSelectedVersions([selectedVersions[1], versionId]);
    }
    // 清除 diff 结果
    setDiffResult(null);
  };

  const handlePreview = async (versionId: string) => {
    try {
      setPreviewLoading(true);
      setPreviewVersion(null);
      const version = await versionApi.get(projectId, versionId);
      setPreviewVersion(version);
    } catch (err) {
      console.error('加载版本详情失败:', err);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleDiff = async () => {
    if (selectedVersions.length !== 2) return;

    try {
      setDiffLoading(true);
      const result = await versionApi.diff(projectId, selectedVersions[0], selectedVersions[1]);
      setDiffResult(result);
    } catch (err) {
      console.error('对比版本失败:', err);
    } finally {
      setDiffLoading(false);
    }
  };

  const handleRollback = async () => {
    if (!rollbackConfirm) return;

    try {
      setRollbackLoading(true);
      await versionApi.rollback(projectId, rollbackConfirm.id, true);
      // 重新加载版本列表
      await loadVersions();
      setRollbackConfirm(null);
      setPreviewVersion(null);
      setDiffResult(null);
      setSelectedVersions([]);
    } catch (err) {
      console.error('回滚失败:', err);
    } finally {
      setRollbackLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderDiffContent = (oldContent: string | null, newContent: string | null) => {
    if (!oldContent && !newContent) return null;

    // 简单的行级 diff 显示
    const oldLines = (oldContent || '').split('\n');
    const newLines = (newContent || '').split('\n');
    const maxLines = Math.max(oldLines.length, newLines.length);

    const diffLines: Array<{ type: 'unchanged' | 'added' | 'removed'; content: string }> = [];

    // 简单 diff 算法：逐行比较
    const seenNew = new Set<number>();
    for (let i = 0; i < oldLines.length; i++) {
      const oldLine = oldLines[i];
      const newIndex = newLines.findIndex((l, idx) => l === oldLine && !seenNew.has(idx));
      if (newIndex >= 0) {
        seenNew.add(newIndex);
        diffLines.push({ type: 'unchanged', content: oldLine });
      } else {
        diffLines.push({ type: 'removed', content: oldLine });
      }
    }

    for (let i = 0; i < newLines.length; i++) {
      if (!seenNew.has(i)) {
        diffLines.push({ type: 'added', content: newLines[i] });
      }
    }

    return (
      <div className="font-mono text-xs whitespace-pre-wrap">
        {diffLines.slice(0, 100).map((line, idx) => (
          <div
            key={idx}
            className={`px-2 ${
              line.type === 'added'
                ? 'bg-green-100 text-green-800'
                : line.type === 'removed'
                ? 'bg-red-100 text-red-800 line-through'
                : 'text-gray-600'
            }`}
          >
            {line.type === 'added' && '+ '}
            {line.type === 'removed' && '- '}
            {line.type === 'unchanged' && '  '}
            {line.content}
          </div>
        ))}
        {diffLines.length > 100 && (
          <div className="px-2 text-gray-500 text-center py-2">
            ... 省略 {diffLines.length - 100} 行
          </div>
        )}
      </div>
    );
  };

  const renderChapterChange = (change: ChapterChange) => (
    <div key={change.chapter_id} className="border-b border-gray-200 py-3 last:border-b-0">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
              change.type === 'added'
                ? 'bg-green-100 text-green-800'
                : change.type === 'deleted'
                ? 'bg-red-100 text-red-800'
                : 'bg-yellow-100 text-yellow-800'
            }`}
          >
            {change.type === 'added' ? '新增' : change.type === 'deleted' ? '删除' : '修改'}
          </span>
          <span className="font-medium text-gray-900">
            {change.chapter_number} {change.title}
          </span>
        </div>
      </div>
      {(change.title_changed || change.content_changed) && (
        <div className="mt-2 space-y-2">
          {change.title_changed && (
            <div>
              <p className="text-xs text-gray-500 mb-1">标题变更：</p>
              <div className="text-sm">
                <span className="text-red-600 line-through">{change.old_title}</span>
                {' → '}
                <span className="text-green-600">{change.new_title}</span>
              </div>
            </div>
          )}
          {change.content_changed && (
            <div>
              <p className="text-xs text-gray-500 mb-1">内容变更：</p>
              <div className="border rounded-md overflow-hidden bg-gray-50">
                {renderDiffContent(change.old_content, change.new_content)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );

  if (!isOpen) return null;

  return (
    <>
      {/* 遮罩层 */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-40"
        onClick={onClose}
      />

      {/* 侧边栏 */}
      <div className="fixed right-0 top-0 h-full w-[600px] bg-white shadow-xl z-50 flex flex-col">
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">版本历史</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* 内容区域 */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : error ? (
            <div className="p-4 text-center text-red-600">{error}</div>
          ) : versions.length === 0 ? (
            <div className="p-4 text-center text-gray-500">暂无版本历史</div>
          ) : (
            <div className="p-4 space-y-4">
              {/* Diff 操作栏 */}
              {selectedVersions.length > 0 && (
                <div className="bg-blue-50 p-3 rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-blue-700">
                      已选择 {selectedVersions.length} 个版本
                      {selectedVersions.length === 2 && ' (点击"对比"查看差异)'}
                    </span>
                    <button
                      onClick={handleDiff}
                      disabled={selectedVersions.length !== 2 || diffLoading}
                      className="px-3 py-1 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
                    >
                      {diffLoading ? '对比中...' : '对比'}
                    </button>
                  </div>
                </div>
              )}

              {/* Diff 结果 */}
              {diffResult && (
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                  <h3 className="font-medium text-gray-900 mb-3">版本对比结果</h3>
                  <div className="text-sm text-gray-600 mb-3">
                    <p>V{diffResult.v1.version_number} ↔ V{diffResult.v2.version_number}</p>
                    <p className="mt-1">
                      总变更: {diffResult.diff.total_changes} 项
                      (新增 {diffResult.diff.added}, 删除 {diffResult.diff.deleted}, 修改 {diffResult.diff.modified})
                    </p>
                  </div>
                  <div className="max-h-80 overflow-y-auto">
                    {diffResult.diff.changes.map(renderChapterChange)}
                  </div>
                </div>
              )}

              {/* 版本预览 */}
              {previewVersion && (
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-medium text-gray-900">
                      版本 V{previewVersion.version_number} 预览
                    </h3>
                    <button
                      onClick={() => setPreviewVersion(null)}
                      className="text-sm text-gray-500 hover:text-gray-700"
                    >
                      关闭
                    </button>
                  </div>
                  <div className="text-sm text-gray-600 mb-2">
                    <p>变更类型: {CHANGE_TYPE_LABELS[previewVersion.change_type as ChangeType]}</p>
                    {previewVersion.change_summary && (
                      <p className="mt-1">摘要: {previewVersion.change_summary}</p>
                    )}
                  </div>
                  <div className="mt-3 p-3 bg-white rounded border max-h-60 overflow-y-auto">
                    <pre className="text-xs whitespace-pre-wrap">
                      {JSON.stringify(previewVersion.snapshot_data, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {/* 版本列表 */}
              <div className="space-y-2">
                {versions.map((version) => (
                  <div
                    key={version.id}
                    className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                      selectedVersions.includes(version.id)
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-3">
                        <input
                          type="checkbox"
                          checked={selectedVersions.includes(version.id)}
                          onChange={() => handleVersionSelect(version.id)}
                          className="mt-1 h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                        />
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="font-medium text-gray-900">
                              V{version.version_number}
                            </span>
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                                CHANGE_TYPE_COLORS[version.change_type as ChangeType]
                              }`}
                            >
                              {CHANGE_TYPE_LABELS[version.change_type as ChangeType]}
                            </span>
                          </div>
                          {version.change_summary && (
                            <p className="mt-1 text-sm text-gray-600 line-clamp-1">
                              {version.change_summary}
                            </p>
                          )}
                          <div className="mt-1 flex items-center space-x-3 text-xs text-gray-500">
                            <span className="flex items-center">
                              <ClockIcon className="w-3 h-3 mr-1" />
                              {formatDate(version.created_at)}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePreview(version.id);
                          }}
                          disabled={previewLoading}
                          className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                          title="预览"
                        >
                          <DocumentTextIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setRollbackConfirm(version);
                          }}
                          className="p-1 text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded"
                          title="回滚到此版本"
                        >
                          <ArrowPathIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* 分页信息 */}
              {total > versions.length && (
                <div className="text-center text-sm text-gray-500 py-2">
                  显示 {versions.length} / {total} 条记录
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 回滚确认弹窗 */}
      {rollbackConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-60 flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">确认回滚</h3>
            <p className="text-gray-600 mb-4">
              确定要回滚到版本 <span className="font-medium">V{rollbackConfirm.version_number}</span> 吗？
            </p>
            <p className="text-sm text-gray-500 mb-4">
              回滚前会自动创建当前状态的快照，以便需要时恢复。
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setRollbackConfirm(null)}
                disabled={rollbackLoading}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleRollback}
                disabled={rollbackLoading}
                className="px-4 py-2 text-sm font-medium text-white bg-orange-600 rounded-md hover:bg-orange-700 disabled:bg-gray-400"
              >
                {rollbackLoading ? '回滚中...' : '确认回滚'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default VersionHistory;
