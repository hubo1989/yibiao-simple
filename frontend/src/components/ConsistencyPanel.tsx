/**
 * 跨章节一致性检查面板组件
 */
import React from 'react';
import {
  XMarkIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  DocumentCheckIcon,
  ArrowPathIcon,
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
}

const ConsistencyPanel: React.FC<ConsistencyPanelProps> = ({
  isOpen,
  onClose,
  result,
  isLoading,
  onCheck,
}) => {
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
              <div className="divide-y divide-gray-100">
                {result.contradictions.map((item, index) => {
                  const severityCfg = severityConfig[item.severity];
                  const categoryCfg = categoryConfig[item.category];

                  return (
                    <div
                      key={index}
                      className={`p-4 ${severityCfg.bgColor} border-l-4 ${severityCfg.borderColor}`}
                    >
                      <div className="flex items-start gap-2 mb-3">
                        {getSeverityIcon(item.severity)}
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`text-xs font-medium px-2 py-0.5 rounded ${severityCfg.color}`}>
                              {severityCfg.label}
                            </span>
                            <span className="text-xs text-gray-500">
                              {categoryCfg.icon} {categoryCfg.label}
                            </span>
                          </div>
                          <p className="text-sm text-gray-800 font-medium">{item.description}</p>
                        </div>
                      </div>

                      {/* 涉及的章节对比 */}
                      <div className="grid grid-cols-2 gap-3 mb-3">
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
                        <div className="bg-white p-3 rounded border border-blue-200">
                          <p className="text-xs font-medium text-blue-600 mb-1">统一建议</p>
                          <p className="text-sm text-gray-700">{item.suggestion}</p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
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
        <div className="p-4 border-t border-gray-200 bg-gray-50">
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
