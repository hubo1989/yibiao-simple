/**
 * 校对结果面板组件 - 侧边栏展示 AI 校对问题列表
 */
import React, { useState } from 'react';
import {
  XMarkIcon,
  CheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  DocumentTextIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';
import type {
  ProofreadIssue,
  ProofreadResult,
  IssueSeverity,
  IssueCategory,
  ISSUE_SEVERITY_CONFIG,
  ISSUE_CATEGORY_CONFIG,
} from '../types/proofread';
import {
  ISSUE_SEVERITY_CONFIG as severityConfig,
  ISSUE_CATEGORY_CONFIG as categoryConfig,
} from '../types/proofread';

interface ProofreadPanelProps {
  isOpen: boolean;
  onClose: () => void;
  proofreadResult: ProofreadResult | null;
  isLoading: boolean;
  streamingText: string;
  onApplySuggestion: (issue: ProofreadIssue) => void;
  onEditContent: (issue: ProofreadIssue) => void;
  chapterTitle: string;
}

const ProofreadPanel: React.FC<ProofreadPanelProps> = ({
  isOpen,
  onClose,
  proofreadResult,
  isLoading,
  streamingText,
  onApplySuggestion,
  onEditContent,
  chapterTitle,
}) => {
  const [filterSeverity, setFilterSeverity] = useState<IssueSeverity | 'all'>('all');
  const [expandedIssues, setExpandedIssues] = useState<Set<number>>(new Set());

  if (!isOpen) return null;

  const filteredIssues = proofreadResult?.issues.filter((issue) => {
    if (filterSeverity === 'all') return true;
    return issue.severity === filterSeverity;
  }) || [];

  const toggleIssueExpand = (index: number) => {
    setExpandedIssues((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const getSeverityIcon = (severity: IssueSeverity) => {
    switch (severity) {
      case 'critical':
        return <ExclamationTriangleIcon className="w-5 h-5 text-red-500" />;
      case 'warning':
        return <ExclamationTriangleIcon className="w-5 h-5 text-yellow-500" />;
      case 'info':
        return <InformationCircleIcon className="w-5 h-5 text-blue-500" />;
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-white shadow-xl z-50 flex flex-col border-l border-gray-200">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">AI 校对结果</h3>
          <p className="text-sm text-gray-500 truncate">{chapterTitle}</p>
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
          <div className="p-4">
            <div className="flex items-center justify-center mb-4">
              <ArrowPathIcon className="w-6 h-6 text-blue-500 animate-spin mr-2" />
              <span className="text-gray-600">正在校对...</span>
            </div>
            {streamingText && (
              <div className="mt-4 p-3 bg-gray-50 rounded-lg text-sm text-gray-600 max-h-60 overflow-y-auto whitespace-pre-wrap">
                {streamingText}
              </div>
            )}
          </div>
        ) : proofreadResult ? (
          <>
            {/* 统计摘要 */}
            <div className="p-4 border-b border-gray-200 bg-gray-50">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700">发现问题</span>
                <span className="text-sm font-bold text-gray-900">
                  {proofreadResult.issue_count} 个
                </span>
              </div>
              <div className="flex gap-2 text-xs">
                <span className="px-2 py-1 rounded-full bg-red-100 text-red-700">
                  严重: {proofreadResult.critical_count}
                </span>
                <span className="px-2 py-1 rounded-full bg-yellow-100 text-yellow-700">
                  警告: {proofreadResult.issues.filter((i) => i.severity === 'warning').length}
                </span>
                <span className="px-2 py-1 rounded-full bg-blue-100 text-blue-700">
                  提示: {proofreadResult.issues.filter((i) => i.severity === 'info').length}
                </span>
              </div>
              {proofreadResult.summary && (
                <p className="mt-3 text-sm text-gray-600">{proofreadResult.summary}</p>
              )}
              {proofreadResult.status_changed && (
                <p className="mt-2 text-xs text-yellow-600 bg-yellow-50 px-2 py-1 rounded">
                  章节状态已更新为「校对中」
                </p>
              )}
            </div>

            {/* 筛选器 */}
            <div className="p-3 border-b border-gray-200">
              <select
                value={filterSeverity}
                onChange={(e) => setFilterSeverity(e.target.value as IssueSeverity | 'all')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">全部问题</option>
                <option value="critical">严重问题</option>
                <option value="warning">一般问题</option>
                <option value="info">轻微问题</option>
              </select>
            </div>

            {/* 问题列表 */}
            <div className="divide-y divide-gray-100">
              {filteredIssues.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  <DocumentTextIcon className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                  <p>没有找到符合条件的问题</p>
                </div>
              ) : (
                filteredIssues.map((issue, index) => {
                  const severityCfg = severityConfig[issue.severity];
                  const categoryCfg = categoryConfig[issue.category];
                  const isExpanded = expandedIssues.has(index);

                  return (
                    <div
                      key={index}
                      className={`p-4 ${severityCfg.bgColor} border-l-4 ${severityCfg.borderColor}`}
                    >
                      {/* 问题头部 */}
                      <div
                        className="flex items-start justify-between cursor-pointer"
                        onClick={() => toggleIssueExpand(index)}
                      >
                        <div className="flex items-start gap-2 flex-1">
                          {getSeverityIcon(issue.severity)}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-xs font-medium px-2 py-0.5 rounded ${severityCfg.bgColor} ${severityCfg.color}`}>
                                {severityCfg.label}
                              </span>
                              <span className="text-xs text-gray-500">
                                {categoryCfg.icon} {categoryCfg.label}
                              </span>
                            </div>
                            <p className="text-sm text-gray-800 font-medium line-clamp-2">
                              {issue.issue}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">
                              位置: {issue.position}
                            </p>
                          </div>
                        </div>
                        {isExpanded ? (
                          <ChevronUpIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                        ) : (
                          <ChevronDownIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
                        )}
                      </div>

                      {/* 展开内容 */}
                      {isExpanded && (
                        <div className="mt-3 pt-3 border-t border-gray-200">
                          <div className="mb-3">
                            <p className="text-xs font-medium text-gray-500 mb-1">修改建议</p>
                            <p className="text-sm text-gray-700 bg-white p-2 rounded border border-gray-200">
                              {issue.suggestion}
                            </p>
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onApplySuggestion(issue);
                              }}
                              className="flex-1 inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium rounded bg-blue-600 text-white hover:bg-blue-700"
                            >
                              <CheckIcon className="w-4 h-4 mr-1" />
                              接受建议
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onEditContent(issue);
                              }}
                              className="flex-1 inline-flex items-center justify-center px-3 py-1.5 text-xs font-medium rounded border border-gray-300 text-gray-700 hover:bg-gray-50"
                            >
                              手动编辑
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </>
        ) : (
          <div className="p-8 text-center text-gray-500">
            <DocumentTextIcon className="w-12 h-12 mx-auto mb-2 text-gray-300" />
            <p>尚未进行校对</p>
            <p className="text-sm mt-1">点击章节旁的「校对」按钮开始</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProofreadPanel;
