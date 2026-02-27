/**
 * 跨章节一致性检查面板组件
 */
import React, { useState } from 'react';
import {
  XMarkIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  DocumentCheckIcon,
  ArrowPathIcon,
  CheckIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';
import type {
  ContradictionItem,
  ConsistencyCheckResponse,
  ConsistencySeverity,
  ConsistencyCategory,
  OverallConsistency,
} from '../types/consistency';
import {
  CONSISTENCY_SEVERITY_CONFIG as severityConfig,
  CONSISTENCY_CATEGORY_CONFIG as categoryConfig,
  OVERALL_CONSISTENCY_CONFIG as overallConfig,
} from '../types/consistency';

interface ConsistencyPanelProps {
  isOpen: boolean;
  onClose: () => void;
  result: ConsistencyCheckResponse | null;
  isLoading: boolean;
  onCheck: () => void;
  onApplyFixes?: (selectedFixes: ContradictionItem[]) => Promise<string[]>; // 返回已修改的章节ID列表
}

const ConsistencyPanel: React.FC<ConsistencyPanelProps> = ({
  isOpen,
  onClose,
  result,
  isLoading,
  onCheck,
  onApplyFixes,
}) => {
  const [selectedFixes, setSelectedFixes] = useState<Set<number>>(new Set());
  const [appliedFixes, setAppliedFixes] = useState<Set<number>>(new Set());
  const [isApplying, setIsApplying] = useState(false);

  if (!isOpen) return null;

  const getSeverityIcon = (severity: ConsistencySeverity) => {
    switch (severity) {
      case 'critical':
        return <ExclamationTriangleIcon className="w-5 h-5 text-red-500" />;
      case 'warning':
        return <ExclamationTriangleIcon className="w-5 h-5 text-yellow-500" />;
      case 'info':
        return <InformationCircleIcon className="w-5 h-5 text-blue-500" />;
    }
  };

  const getOverallIcon = (overall: OverallConsistency) => {
    switch (overall) {
      case 'consistent':
        return <DocumentCheckIcon className="w-8 h-8 text-green-500" />;
      case 'minor_issues':
        return <ExclamationTriangleIcon className="w-8 h-8 text-yellow-500" />;
      case 'major_issues':
        return <ExclamationTriangleIcon className="w-8 h-8 text-red-500" />;
    }
  };

  // 全选/取消全选
  const handleSelectAll = () => {
    if (!result) return;
    const allIndexes = new Set(
      result.contradictions
        .map((_, index) => index)
        .filter(index => !appliedFixes.has(index)) // 只选择未应用的
    );
    setSelectedFixes(allIndexes);
  };

  const handleDeselectAll = () => {
    setSelectedFixes(new Set());
  };

  // 获取可选的修改数量（排除已应用的）
  const selectableCount = result?.contradictions.filter((_, i) => !appliedFixes.has(i)).length || 0;
  const isAllSelected = selectedFixes.size === selectableCount && selectableCount > 0;

  return (
    <div className="fixed inset-y-0 right-0 w-[480px] bg-white shadow-xl z-50 flex flex-col border-l border-gray-200">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">跨章节一致性检查</h3>
          <p className="text-sm text-gray-500">检测项目中的矛盾和不一致</p>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-gray-200 text-gray-500"
        >
          <XMarkIcon className="w-5 h-5" />
        </button>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-8 flex flex-col items-center justify-center">
            <ArrowPathIcon className="w-10 h-10 text-blue-500 animate-spin mb-4" />
            <p className="text-gray-600">正在进行一致性检查...</p>
            <p className="text-sm text-gray-400 mt-1">这可能需要几秒钟</p>
          </div>
        ) : result ? (
          <>
            {/* 总体评估 */}
            <div className={`p-6 ${overallConfig[result.overall_consistency].bgColor}`}>
              <div className="flex items-center gap-4">
                {getOverallIcon(result.overall_consistency)}
                <div>
                  <p className={`text-lg font-semibold ${overallConfig[result.overall_consistency].color}`}>
                    {overallConfig[result.overall_consistency].label}
                  </p>
                  <p className="text-sm text-gray-600">
                    发现 {result.contradiction_count} 个矛盾
                    {result.critical_count > 0 && (
                      <span className="text-red-600 ml-1">
                        (其中 {result.critical_count} 个严重)
                      </span>
                    )}
                  </p>
                </div>
              </div>
              {result.summary && (
                <p className="mt-4 text-sm text-gray-600">{result.summary}</p>
              )}
            </div>

            {/* 矛盾列表 */}
            {result.contradictions.length > 0 ? (
              <>
                {/* 全选操作栏 */}
                <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      onChange={isAllSelected ? handleDeselectAll : handleSelectAll}
                      className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                    />
                    <span className="ml-2 text-sm text-gray-600">
                      {isAllSelected ? '取消全选' : '全选'}
                    </span>
                  </label>
                  <span className="text-xs text-gray-500">
                    已选择 {selectedFixes.size} / {selectableCount} 项
                    {appliedFixes.size > 0 && ` (已应用 ${appliedFixes.size} 项)`}
                  </span>
                </div>

                <div className="divide-y divide-gray-100">
                  {result.contradictions.map((item, index) => {
                    const severityCfg = severityConfig[item.severity];
                    const categoryCfg = categoryConfig[item.category];
                    const isSelected = selectedFixes.has(index);
                    const isApplied = appliedFixes.has(index);

                    return (
                      <div
                        key={index}
                        className={`p-4 ${severityCfg.bgColor} border-l-4 ${severityCfg.borderColor} ${
                          isSelected ? 'ring-2 ring-blue-400' : ''
                        } ${isApplied ? 'opacity-60' : ''}`}
                      >
                        <div className="flex items-start gap-2 mb-3">
                          {/* 选择框或已应用标记 */}
                          {isApplied ? (
                            <div className="flex items-center mt-1">
                              <CheckCircleIcon className="w-5 h-5 text-green-500" />
                            </div>
                          ) : (
                            <label className="flex items-center cursor-pointer mt-1">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={(e) => {
                                  const newSet = new Set(selectedFixes);
                                  if (e.target.checked) {
                                    newSet.add(index);
                                  } else {
                                    newSet.delete(index);
                                  }
                                  setSelectedFixes(newSet);
                                }}
                                className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                              />
                            </label>
                          )}
                          {getSeverityIcon(item.severity)}
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-xs font-medium px-2 py-0.5 rounded ${severityCfg.color}`}>
                                {severityCfg.label}
                              </span>
                              <span className="text-xs text-gray-500">
                                {categoryCfg.icon} {categoryCfg.label}
                              </span>
                              {isApplied && (
                                <span className="text-xs font-medium px-2 py-0.5 rounded bg-green-100 text-green-700">
                                  已应用
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-gray-800 font-medium">{item.description}</p>
                          </div>
                        </div>

                      {/* 涉及的章节对比 */}
                      <div className="grid grid-cols-2 gap-3 mb-3 ml-6">
                        <div className="bg-white p-3 rounded border border-gray-200">
                          <p className="text-xs font-medium text-gray-500 mb-1 truncate" title={item.chapter_a}>
                            {item.chapter_a}
                          </p>
                          <p className="text-sm text-gray-700 line-clamp-3">{item.detail_a}</p>
                        </div>
                        <div className="bg-white p-3 rounded border border-gray-200">
                          <p className="text-xs font-medium text-gray-500 mb-1 truncate" title={item.chapter_b}>
                            {item.chapter_b}
                          </p>
                          <p className="text-sm text-gray-700 line-clamp-3">{item.detail_b}</p>
                        </div>
                      </div>

                      {/* 建议修改 */}
                      {item.suggestion && (
                        <div className="bg-white p-3 rounded border border-blue-200 ml-6">
                          <p className="text-xs font-medium text-blue-600 mb-1">统一建议</p>
                          <p className="text-sm text-gray-700">{item.suggestion}</p>
                        </div>
                      )}
                    </div>
                  );
                })}
                </div>
              </>
            ) : (
              <div className="p-8 text-center text-gray-500">
                <DocumentCheckIcon className="w-16 h-16 mx-auto mb-3 text-green-300" />
                <p className="font-medium">未发现矛盾</p>
                <p className="text-sm mt-1">各章节内容一致</p>
              </div>
            )}
          </>
        ) : (
          <div className="p-8 flex flex-col items-center justify-center text-gray-500">
            <DocumentCheckIcon className="w-16 h-16 mb-4 text-gray-300" />
            <p className="font-medium">尚未进行一致性检查</p>
            <p className="text-sm mt-1 text-center">
              检查将分析所有章节内容，找出数据、术语、时间线等方面的矛盾
            </p>
            <button
              onClick={onCheck}
              className="mt-4 inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
            >
              开始检查
            </button>
          </div>
        )}
      </div>

      {/* 底部操作区 */}
      {result && (
        <div className="p-4 border-t border-gray-200 bg-gray-50 space-y-2">
          {/* 应用修改按钮 */}
          {result.contradictions.length > 0 && onApplyFixes && selectableCount > 0 && (
            <button
              onClick={async () => {
                if (selectedFixes.size === 0) {
                  alert('请先选择要应用的修改');
                  return;
                }
                setIsApplying(true);
                try {
                  const fixesToApply = result.contradictions.filter((_, i) => selectedFixes.has(i));
                  const modifiedIds = await onApplyFixes(fixesToApply);
                  // 检查是否有成功的修改
                  if (!modifiedIds || modifiedIds.length === 0) {
                    throw new Error('所有修改都失败了');
                  }
                  // 标记已应用的修改
                  const newAppliedFixes = new Set(appliedFixes);
                  selectedFixes.forEach(index => newAppliedFixes.add(index));
                  setAppliedFixes(newAppliedFixes);
                  setSelectedFixes(new Set());
                  // 自动关闭面板
                  setTimeout(() => {
                    onClose();
                  }, 500);
                } catch (error) {
                  console.error('应用修改失败:', error);
                  alert('应用修改失败，请检查后端日志');
                } finally {
                  setIsApplying(false);
                }
              }}
              disabled={isApplying || selectedFixes.size === 0}
              className="w-full inline-flex items-center justify-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isApplying ? (
                <>
                  <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
                  应用中...
                </>
              ) : (
                <>
                  <CheckIcon className="w-4 h-4 mr-2" />
                  应用选中修改 ({selectedFixes.size})
                </>
              )}
            </button>
          )}
          {/* 已全部应用提示 */}
          {result.contradictions.length > 0 && selectableCount === 0 && (
            <div className="w-full inline-flex items-center justify-center px-4 py-2 bg-green-100 text-green-700 rounded-lg text-sm font-medium">
              <CheckCircleIcon className="w-4 h-4 mr-2" />
              所有修改已应用
            </div>
          )}
          {/* 重新检查按钮 */}
          <button
            onClick={onCheck}
            disabled={isLoading}
            className="w-full inline-flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
                检查中...
              </>
            ) : (
              <>
                <ArrowPathIcon className="w-4 h-4 mr-2" />
                重新检查
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
};

export default ConsistencyPanel;
