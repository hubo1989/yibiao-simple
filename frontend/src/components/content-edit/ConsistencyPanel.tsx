/**
 * 全文一致性校验面板
 * 展示 AI 跨章节矛盾检查结果
 */
import React from 'react';
import {
  Button,
  Space,
  Typography,
  Tag,
  Spin,
  Alert,
  Divider,
  Badge,
  Tooltip,
} from 'antd';
import {
  SyncOutlined,
  CloseOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import type { ConsistencyCheckResult, ConsistencyIssue } from '../../services/api';

interface ConsistencyPanelProps {
  /** 面板是否可见 */
  isOpen: boolean;
  /** 关闭回调 */
  onClose: () => void;
  /** 重新检查回调 */
  onRecheck: () => void;
  /** 是否正在检查 */
  isChecking: boolean;
  /** 检查结果 */
  result: ConsistencyCheckResult | null;
  /** 上次检查时间（可选，展示用） */
  lastCheckedAt?: string;
  /** 点击章节跳转回调（传入 chapter_id） */
  onJumpToChapter?: (chapterId: string, chapterTitle: string) => void;
}

// ==================== 辅助配置 ====================

const SEVERITY_CONFIG: Record<ConsistencyIssue['severity'], {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  icon: React.ReactNode;
  tagColor: string;
}> = {
  error: {
    label: '严重矛盾',
    color: '#cf1322',
    bgColor: '#fff1f0',
    borderColor: '#ffccc7',
    icon: <ExclamationCircleOutlined style={{ color: '#cf1322' }} />,
    tagColor: 'error',
  },
  warning: {
    label: '可能不一致',
    color: '#d46b08',
    bgColor: '#fff7e6',
    borderColor: '#ffd591',
    icon: <WarningOutlined style={{ color: '#d46b08' }} />,
    tagColor: 'warning',
  },
  info: {
    label: '轻微差异',
    color: '#0958d9',
    bgColor: '#e6f4ff',
    borderColor: '#91caff',
    icon: <InfoCircleOutlined style={{ color: '#0958d9' }} />,
    tagColor: 'processing',
  },
};

const CATEGORY_LABEL: Record<string, string> = {
  data: '数据矛盾',
  terminology: '术语不一致',
  timeline: '时间线矛盾',
  commitment: '承诺冲突',
  scope: '范围矛盾',
};

const OVERALL_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  consistent: {
    label: '全文一致',
    color: '#389e0d',
    icon: <CheckCircleOutlined style={{ color: '#389e0d' }} />,
  },
  minor_issues: {
    label: '存在轻微问题',
    color: '#d46b08',
    icon: <WarningOutlined style={{ color: '#d46b08' }} />,
  },
  major_issues: {
    label: '存在严重矛盾',
    color: '#cf1322',
    icon: <ExclamationCircleOutlined style={{ color: '#cf1322' }} />,
  },
};

// ==================== 子组件：单个 Issue 卡片 ====================

const IssueCard: React.FC<{
  issue: ConsistencyIssue;
  index: number;
  onJump?: (chapterId: string, title: string) => void;
}> = ({ issue, index, onJump }) => {
  const cfg = SEVERITY_CONFIG[issue.severity] ?? SEVERITY_CONFIG.info;

  return (
    <div
      style={{
        border: `1px solid ${cfg.borderColor}`,
        borderLeft: `4px solid ${cfg.color}`,
        borderRadius: 6,
        backgroundColor: cfg.bgColor,
        padding: '12px 16px',
        marginBottom: 12,
      }}
    >
      {/* 标题行 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 600, color: '#1f2937', fontSize: 13, minWidth: 28 }}>
          #{String(index + 1).padStart(2, '0')}
        </span>
        {cfg.icon}
        <Tag color={cfg.tagColor} style={{ margin: 0 }}>{cfg.label}</Tag>
        <Tag color="default" style={{ margin: 0, fontSize: 11 }}>
          {CATEGORY_LABEL[issue.category] ?? issue.category}
        </Tag>
        <Typography.Text style={{ fontSize: 13, color: '#374151', flex: 1 }}>
          {issue.description}
        </Typography.Text>
      </div>

      {/* 涉及章节 */}
      <div style={{ marginBottom: 8 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          涉及章节：
        </Typography.Text>
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          {[
            { ref: issue.chapter_a, id: issue.chapter_id_a, text: issue.detail_a },
            { ref: issue.chapter_b, id: issue.chapter_id_b, text: issue.detail_b },
          ].map((loc, i) => (
            <div
              key={i}
              style={{
                backgroundColor: 'rgba(255,255,255,0.7)',
                border: '1px solid rgba(0,0,0,0.06)',
                borderRadius: 4,
                padding: '6px 10px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>{loc.ref || `章节 ${i + 1}`}</Tag>
                {onJump && loc.id && (
                  <Tooltip title="跳转到该章节">
                    <Typography.Link
                      style={{ fontSize: 11 }}
                      onClick={() => onJump(loc.id!, loc.ref)}
                    >
                      定位
                    </Typography.Link>
                  </Tooltip>
                )}
              </div>
              {loc.text && (
                <Typography.Text
                  style={{
                    fontSize: 12,
                    color: '#6b7280',
                    fontStyle: 'italic',
                    display: 'block',
                    marginTop: 2,
                  }}
                >
                  "{loc.text}"
                </Typography.Text>
              )}
            </div>
          ))}
        </Space>
      </div>

      {/* 修改建议 */}
      {issue.suggestion && (
        <div
          style={{
            backgroundColor: 'rgba(255,255,255,0.5)',
            borderRadius: 4,
            padding: '6px 10px',
            borderLeft: '3px solid #d9d9d9',
          }}
        >
          <Typography.Text type="secondary" style={{ fontSize: 11 }}>建议：</Typography.Text>
          <Typography.Text style={{ fontSize: 12, color: '#374151' }}>{issue.suggestion}</Typography.Text>
        </div>
      )}
    </div>
  );
};

// ==================== 主组件 ====================

const ConsistencyPanel: React.FC<ConsistencyPanelProps> = ({
  isOpen,
  onClose,
  onRecheck,
  isChecking,
  result,
  lastCheckedAt,
  onJumpToChapter,
}) => {
  if (!isOpen) return null;

  const errorCount = result?.issues.filter(i => i.severity === 'error').length ?? 0;
  const warningCount = result?.issues.filter(i => i.severity === 'warning').length ?? 0;
  const infoCount = result?.issues.filter(i => i.severity === 'info').length ?? 0;
  const overallCfg = result ? (OVERALL_CONFIG[result.overall_consistency] ?? OVERALL_CONFIG.consistent) : null;

  return (
    <div
      style={{
        position: 'fixed',
        right: 0,
        top: 0,
        bottom: 0,
        width: 440,
        backgroundColor: '#ffffff',
        borderLeft: '1px solid #e2e8f0',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.08)',
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* 顶部标题栏 */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid #f0f0f0',
          flexShrink: 0,
          backgroundColor: '#fafafa',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Typography.Text strong style={{ fontSize: 15 }}>全文一致性校验</Typography.Text>
            {result && errorCount > 0 && (
              <Badge count={errorCount} color="#cf1322" />
            )}
          </div>
          <Space>
            <Tooltip title="重新检查">
              <Button
                type="default"
                size="small"
                icon={<SyncOutlined spin={isChecking} />}
                onClick={onRecheck}
                disabled={isChecking}
              >
                {isChecking ? '检查中...' : '重新检查'}
              </Button>
            </Tooltip>
            <Button
              type="text"
              size="small"
              icon={<CloseOutlined />}
              onClick={onClose}
            />
          </Space>
        </div>

        {/* 上次检查时间 */}
        {lastCheckedAt && !isChecking && (
          <Typography.Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            上次检查：{lastCheckedAt}
          </Typography.Text>
        )}
      </div>

      {/* 内容区域 */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
        {isChecking && (
          <div style={{ textAlign: 'center', padding: '48px 0' }}>
            <Spin size="large" />
            <Typography.Text
              type="secondary"
              style={{ display: 'block', marginTop: 16, fontSize: 13 }}
            >
              AI 正在跨章节交叉检查，请稍候...
            </Typography.Text>
          </div>
        )}

        {!isChecking && !result && (
          <div style={{ textAlign: 'center', padding: '48px 0' }}>
            <ExclamationCircleOutlined
              style={{ fontSize: 40, color: '#d9d9d9', marginBottom: 16 }}
            />
            <Typography.Text type="secondary" style={{ display: 'block' }}>
              点击"重新检查"开始全文一致性校验
            </Typography.Text>
          </div>
        )}

        {!isChecking && result && (
          <>
            {/* 整体评估 */}
            <div
              style={{
                backgroundColor: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: '12px 16px',
                marginBottom: 16,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                {overallCfg?.icon}
                <Typography.Text strong style={{ color: overallCfg?.color }}>
                  {overallCfg?.label}
                </Typography.Text>
              </div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {result.summary}
              </Typography.Text>
              {result.total_chapters_checked > 0 && (
                <Typography.Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                  共检查 {result.total_chapters_checked} 个章节
                </Typography.Text>
              )}

              {/* 统计数据 */}
              {result.issues.length > 0 && (
                <div style={{ display: 'flex', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>
                  {errorCount > 0 && (
                    <span style={{ fontSize: 12 }}>
                      <ExclamationCircleOutlined style={{ color: '#cf1322', marginRight: 4 }} />
                      <span style={{ color: '#cf1322', fontWeight: 500 }}>{errorCount}</span>
                      <span style={{ color: '#6b7280', marginLeft: 2 }}>严重</span>
                    </span>
                  )}
                  {warningCount > 0 && (
                    <span style={{ fontSize: 12 }}>
                      <WarningOutlined style={{ color: '#d46b08', marginRight: 4 }} />
                      <span style={{ color: '#d46b08', fontWeight: 500 }}>{warningCount}</span>
                      <span style={{ color: '#6b7280', marginLeft: 2 }}>警告</span>
                    </span>
                  )}
                  {infoCount > 0 && (
                    <span style={{ fontSize: 12 }}>
                      <InfoCircleOutlined style={{ color: '#0958d9', marginRight: 4 }} />
                      <span style={{ color: '#0958d9', fontWeight: 500 }}>{infoCount}</span>
                      <span style={{ color: '#6b7280', marginLeft: 2 }}>提示</span>
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* error 警告 */}
            {errorCount > 0 && (
              <Alert
                type="error"
                showIcon
                message={`发现 ${errorCount} 个严重矛盾，建议在导出前修正`}
                style={{ marginBottom: 12, fontSize: 13 }}
              />
            )}

            {/* 问题列表 */}
            {result.issues.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px 0' }}>
                <CheckCircleOutlined style={{ fontSize: 36, color: '#52c41a', marginBottom: 12 }} />
                <Typography.Text style={{ display: 'block', color: '#389e0d', fontWeight: 500 }}>
                  未发现明显矛盾，全文一致性良好
                </Typography.Text>
              </div>
            ) : (
              <>
                <Divider style={{ margin: '0 0 12px', fontSize: 12 }} orientation="left" plain>
                  矛盾详情（{result.issues.length} 项）
                </Divider>
                {result.issues.map((issue, i) => (
                  <IssueCard
                    key={i}
                    issue={issue}
                    index={i}
                    onJump={onJumpToChapter}
                  />
                ))}
              </>
            )}
          </>
        )}
      </div>

      {/* 底部摘要条 */}
      {!isChecking && result && (
        <div
          style={{
            padding: '10px 20px',
            borderTop: '1px solid #f0f0f0',
            backgroundColor: '#fafafa',
            flexShrink: 0,
          }}
        >
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {result.issues.length === 0
              ? '✓ 全文一致性检查通过'
              : `共 ${result.issues.length} 个问题：${errorCount} 个严重 · ${warningCount} 个警告 · ${infoCount} 个提示`}
          </Typography.Text>
        </div>
      )}
    </div>
  );
};

export default ConsistencyPanel;
