/**
 * 废标检查面板
 * 显示从招标文件提取的否决性条款，支持逐项标记检查状态。
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Button,
  Tag,
  Tooltip,
  Input,
  Spin,
  message,
  Empty,
  Badge,
  Alert,
  Popconfirm,
} from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  MinusCircleOutlined,
  QuestionCircleOutlined,
  ThunderboltOutlined,
  SafetyOutlined,
  ReloadOutlined,
  FileSearchOutlined,
} from '@ant-design/icons';
import {
  disqualificationApi,
  DisqualificationItem,
  DisqualificationSummary,
} from '../services/api';

interface DisqualificationPanelProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
}

const CHECK_TYPE_LABEL: Record<string, string> = {
  certificate: '资质证书',
  document: '文件材料',
  format: '格式装订',
  deadline: '时限要求',
  other: '其他',
};

const CHECK_TYPE_COLOR: Record<string, string> = {
  certificate: 'blue',
  document: 'purple',
  format: 'cyan',
  deadline: 'orange',
  other: 'default',
};

// 按 category 分组
function groupByCategory(items: DisqualificationItem[]): Record<string, DisqualificationItem[]> {
  return items.reduce<Record<string, DisqualificationItem[]>>((acc, item) => {
    const key = item.category || '其他';
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});
}

const StatusIcon: React.FC<{ status: string; size?: number }> = ({ status, size = 18 }) => {
  const style = { fontSize: size };
  switch (status) {
    case 'passed':
      return <CheckCircleOutlined style={{ ...style, color: '#22c55e' }} />;
    case 'failed':
      return <CloseCircleOutlined style={{ ...style, color: '#ef4444' }} />;
    case 'not_applicable':
      return <MinusCircleOutlined style={{ ...style, color: '#94a3b8' }} />;
    default:
      return <QuestionCircleOutlined style={{ ...style, color: '#cbd5e1' }} />;
  }
};

const DisqualificationPanel: React.FC<DisqualificationPanelProps> = ({
  projectId,
  isOpen,
  onClose,
}) => {
  const [items, setItems] = useState<DisqualificationItem[]>([]);
  const [summary, setSummary] = useState<DisqualificationSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [editingNote, setEditingNote] = useState<string | null>(null);
  const [noteValues, setNoteValues] = useState<Record<string, string>>({});
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const fetchItems = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [data, sum] = await Promise.all([
        disqualificationApi.list(projectId),
        disqualificationApi.summary(projectId),
      ]);
      setItems(data);
      setSummary(sum);
    } catch (err: any) {
      // 如果是 404（无数据）就静默忽略
      if (!err?.message?.includes('404')) {
        message.error(err?.message || '加载失败');
      }
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (isOpen && projectId) {
      void fetchItems();
    }
  }, [isOpen, projectId, fetchItems]);

  const handleExtract = async () => {
    setExtracting(true);
    try {
      const data = await disqualificationApi.extract(projectId);
      setItems(data);
      // 刷新摘要
      const sum = await disqualificationApi.summary(projectId);
      setSummary(sum);
      message.success(`成功提取 ${data.length} 项废标检查条款`);
    } catch (err: any) {
      message.error(err?.message || '提取失败，请检查是否已上传招标文件');
    } finally {
      setExtracting(false);
    }
  };

  const handleUpdateStatus = async (item: DisqualificationItem, newStatus: string) => {
    setUpdatingId(item.id);
    try {
      const note = noteValues[item.id] ?? item.note ?? '';
      const updated = await disqualificationApi.updateItem(projectId, item.id, {
        status: newStatus,
        note: note || undefined,
      });
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
      // 刷新摘要
      const sum = await disqualificationApi.summary(projectId);
      setSummary(sum);
    } catch (err: any) {
      message.error(err?.message || '更新失败');
    } finally {
      setUpdatingId(null);
    }
  };

  const handleSaveNote = async (item: DisqualificationItem) => {
    const note = noteValues[item.id] ?? '';
    setUpdatingId(item.id);
    try {
      const updated = await disqualificationApi.updateItem(projectId, item.id, {
        status: item.status,
        note: note || undefined,
      });
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
      setEditingNote(null);
      message.success('备注已保存');
    } catch (err: any) {
      message.error(err?.message || '保存失败');
    } finally {
      setUpdatingId(null);
    }
  };

  if (!isOpen) return null;

  const grouped = groupByCategory(items);

  const hasFatalRisk = (summary?.fatal_unresolved ?? 0) > 0;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        width: 520,
        height: '100vh',
        background: '#fff',
        boxShadow: '-4px 0 24px rgba(15,23,42,0.1)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 1000,
      }}
    >
      {/* 顶栏 */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SafetyOutlined style={{ fontSize: 20, color: '#3b82f6' }} />
          <span style={{ fontWeight: 600, fontSize: 16, color: '#0f172a' }}>废标项检查</span>
          {hasFatalRisk && (
            <Badge
              count={summary?.fatal_unresolved}
              style={{ backgroundColor: '#ef4444' }}
            />
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Tooltip title="重新提取（会覆盖现有检查项）">
            <Popconfirm
              title="重新提取将清空现有检查记录，确认？"
              onConfirm={() => void handleExtract()}
              okText="确认"
              cancelText="取消"
              disabled={extracting}
            >
              <Button
                size="small"
                icon={<ReloadOutlined />}
                loading={extracting}
                disabled={items.length === 0}
              >
                重新提取
              </Button>
            </Popconfirm>
          </Tooltip>
          <Button size="small" onClick={onClose}>
            关闭
          </Button>
        </div>
      </div>

      {/* 摘要栏 */}
      {summary && summary.total > 0 && (
        <div
          style={{
            padding: '12px 20px',
            background: hasFatalRisk ? '#fff7ed' : '#f0fdf4',
            borderBottom: '1px solid #e5e7eb',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <span style={{ fontSize: 13, color: '#64748b' }}>
            共 <b>{summary.total}</b> 项
          </span>
          <span style={{ fontSize: 13, color: '#22c55e' }}>
            ✅ 通过 <b>{summary.passed}</b>
          </span>
          <span style={{ fontSize: 13, color: '#ef4444' }}>
            ❌ 未通过 <b>{summary.failed}</b>
          </span>
          <span style={{ fontSize: 13, color: '#94a3b8' }}>
            ⊘ 不适用 <b>{summary.not_applicable}</b>
          </span>
          <span style={{ fontSize: 13, color: '#94a3b8' }}>
            ? 未检 <b>{summary.unchecked}</b>
          </span>
          {hasFatalRisk && (
            <Tag color="red" icon={<ThunderboltOutlined />} style={{ marginLeft: 'auto' }}>
              {summary.fatal_unresolved} 项废标风险
            </Tag>
          )}
        </div>
      )}

      {/* 内容区 */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin />
          </div>
        ) : items.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Empty
              image={<FileSearchOutlined style={{ fontSize: 48, color: '#cbd5e1' }} />}
              imageStyle={{ height: 56 }}
              description={
                <div>
                  <div style={{ color: '#64748b', marginBottom: 8 }}>尚未提取废标检查项</div>
                  <div style={{ color: '#94a3b8', fontSize: 12 }}>
                    请先上传招标文件，然后点击下方按钮提取否决性条款
                  </div>
                </div>
              }
            >
              <Button
                type="primary"
                icon={<FileSearchOutlined />}
                loading={extracting}
                onClick={() => void handleExtract()}
              >
                提取检查项
              </Button>
            </Empty>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {Object.entries(grouped).map(([category, catItems]) => (
              <div key={category}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: '#475569',
                    marginBottom: 10,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <span
                    style={{
                      display: 'inline-block',
                      width: 3,
                      height: 14,
                      borderRadius: 2,
                      background: '#3b82f6',
                    }}
                  />
                  {category}
                  <span style={{ color: '#94a3b8', fontWeight: 400 }}>（{catItems.length} 项）</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {catItems.map((item) => {
                    const isFatalFailed =
                      item.severity === 'fatal' &&
                      (item.status === 'failed' || item.status === 'unchecked');
                    return (
                      <div
                        key={item.id}
                        style={{
                          border: `1px solid ${isFatalFailed ? '#fca5a5' : '#e5e7eb'}`,
                          borderRadius: 10,
                          padding: '12px 14px',
                          background: isFatalFailed ? '#fff5f5' : '#fafafa',
                          transition: 'border-color 0.2s',
                        }}
                      >
                        {/* 头部：item_id + 标签 + 状态图标 */}
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 8,
                            marginBottom: 6,
                          }}
                        >
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 600,
                              color: '#94a3b8',
                              minWidth: 44,
                              marginTop: 2,
                            }}
                          >
                            {item.item_id}
                          </span>
                          <div style={{ flex: 1, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                            <Tag
                              color={item.severity === 'fatal' ? 'red' : 'orange'}
                              style={{ fontSize: 11, lineHeight: '18px', padding: '0 6px' }}
                            >
                              {item.severity === 'fatal' ? '⚡ 直接废标' : '⚠ 潜在风险'}
                            </Tag>
                            <Tag
                              color={CHECK_TYPE_COLOR[item.check_type] ?? 'default'}
                              style={{ fontSize: 11, lineHeight: '18px', padding: '0 6px' }}
                            >
                              {CHECK_TYPE_LABEL[item.check_type] ?? item.check_type}
                            </Tag>
                          </div>
                          <Spin
                            size="small"
                            spinning={updatingId === item.id}
                            style={{ marginTop: 2 }}
                          >
                            <StatusIcon status={item.status} />
                          </Spin>
                        </div>

                        {/* 要求描述 */}
                        <div
                          style={{
                            fontSize: 13,
                            color: '#1e293b',
                            lineHeight: 1.6,
                            marginBottom: 6,
                          }}
                        >
                          {item.requirement}
                        </div>

                        {/* 来源文本 */}
                        {item.source_text && (
                          <div
                            style={{
                              fontSize: 11,
                              color: '#94a3b8',
                              borderLeft: '2px solid #e5e7eb',
                              paddingLeft: 8,
                              marginBottom: 8,
                              lineHeight: 1.5,
                            }}
                          >
                            {item.source_text}
                          </div>
                        )}

                        {/* 操作按钮 */}
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            flexWrap: 'wrap',
                          }}
                        >
                          <Button
                            size="small"
                            type={item.status === 'passed' ? 'primary' : 'default'}
                            icon={<CheckCircleOutlined />}
                            onClick={() => void handleUpdateStatus(item, 'passed')}
                            disabled={updatingId === item.id}
                            style={
                              item.status === 'passed'
                                ? { background: '#22c55e', borderColor: '#22c55e', color: '#fff' }
                                : {}
                            }
                          >
                            通过
                          </Button>
                          <Button
                            size="small"
                            type={item.status === 'failed' ? 'primary' : 'default'}
                            icon={<CloseCircleOutlined />}
                            onClick={() => void handleUpdateStatus(item, 'failed')}
                            disabled={updatingId === item.id}
                            danger={item.status === 'failed'}
                          >
                            未通过
                          </Button>
                          <Button
                            size="small"
                            type={item.status === 'not_applicable' ? 'primary' : 'default'}
                            icon={<MinusCircleOutlined />}
                            onClick={() => void handleUpdateStatus(item, 'not_applicable')}
                            disabled={updatingId === item.id}
                            style={
                              item.status === 'not_applicable'
                                ? { background: '#94a3b8', borderColor: '#94a3b8', color: '#fff' }
                                : {}
                            }
                          >
                            不适用
                          </Button>
                          <Button
                            size="small"
                            type="link"
                            onClick={() => {
                              if (editingNote === item.id) {
                                setEditingNote(null);
                              } else {
                                setNoteValues((prev) => ({
                                  ...prev,
                                  [item.id]: item.note ?? '',
                                }));
                                setEditingNote(item.id);
                              }
                            }}
                          >
                            {editingNote === item.id ? '收起备注' : item.note ? '编辑备注' : '添加备注'}
                          </Button>
                        </div>

                        {/* 备注编辑 */}
                        {editingNote === item.id && (
                          <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
                            <Input.TextArea
                              autoSize={{ minRows: 1, maxRows: 3 }}
                              placeholder="添加备注（可选）"
                              value={noteValues[item.id] ?? ''}
                              onChange={(e) =>
                                setNoteValues((prev) => ({ ...prev, [item.id]: e.target.value }))
                              }
                              style={{ fontSize: 12 }}
                            />
                            <Button
                              size="small"
                              type="primary"
                              loading={updatingId === item.id}
                              onClick={() => void handleSaveNote(item)}
                            >
                              保存
                            </Button>
                          </div>
                        )}

                        {/* 显示已有备注 */}
                        {item.note && editingNote !== item.id && (
                          <div
                            style={{
                              marginTop: 6,
                              fontSize: 12,
                              color: '#64748b',
                              background: '#f1f5f9',
                              borderRadius: 6,
                              padding: '4px 8px',
                            }}
                          >
                            📝 {item.note}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}

            {/* 底部风险评估 */}
            {summary && (
              <Alert
                type={hasFatalRisk ? 'error' : summary.unchecked > 0 ? 'warning' : 'success'}
                message={
                  hasFatalRisk
                    ? `⚡ 存在 ${summary.fatal_unresolved} 项直接废标风险，请在导出前确认`
                    : summary.unchecked > 0
                    ? `还有 ${summary.unchecked} 项未完成检查，建议全部核实后再导出`
                    : '✅ 所有检查项已完成，未发现废标风险'
                }
                showIcon={false}
                style={{ marginTop: 8 }}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DisqualificationPanel;
