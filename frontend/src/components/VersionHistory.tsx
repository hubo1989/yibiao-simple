/**
 * 版本历史侧边栏 (Ant Design Drawer + Timeline)
 * 支持：版本列表、对比模式、diff 高亮、回滚确认
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Drawer,
  Timeline,
  Button,
  Modal,
  Input,
  Empty,
  Spin,
  Tag,
  message,
  Space,
  Typography,
  Select,
  Divider,
} from 'antd';
import {
  HistoryOutlined,
  RobotOutlined,
  EditOutlined,
  AuditOutlined,
  RollbackOutlined,
  CameraOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { versionApi } from '../services/api';
import type { VersionSummary, VersionDiffResponse } from '../types/version';
import VersionDiff from './VersionDiff';

interface VersionHistoryProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  chapterId?: string;
}

const CHANGE_TYPE_LABELS: Record<string, string> = {
  content_update: '内容更新',
  status_change: '状态变更',
  manual_edit: '手动编辑',
  rollback: '版本回滚',
  ai_generate: 'AI 生成',
};

const CHANGE_TYPE_COLORS: Record<string, string> = {
  content_update: 'blue',
  status_change: 'gold',
  manual_edit: 'purple',
  rollback: 'orange',
  ai_generate: 'green',
};

const CHANGE_TYPE_ICONS: Record<string, React.ReactNode> = {
  ai_generate: <RobotOutlined />,
  manual_edit: <EditOutlined />,
  proofread: <AuditOutlined />,
  rollback: <RollbackOutlined />,
  content_update: <EditOutlined />,
  status_change: <AuditOutlined />,
};

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
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

  // 创建快照
  const [snapshotModalOpen, setSnapshotModalOpen] = useState(false);
  const [snapshotSummary, setSnapshotSummary] = useState('');
  const [creatingSnapshot, setCreatingSnapshot] = useState(false);

  // 回滚
  const [rollingBackId, setRollingBackId] = useState<string | null>(null);

  // 对比模式
  const [compareMode, setCompareMode] = useState(false);
  const [compareV1, setCompareV1] = useState<string | undefined>(undefined);
  const [compareV2, setCompareV2] = useState<string | undefined>(undefined);
  const [diffData, setDiffData] = useState<VersionDiffResponse | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  const loadVersions = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await versionApi.list(projectId, {
        chapter_id: chapterId,
        limit: 50,
      });
      setVersions(result.items);
      setTotal(result.total);
    } catch {
      setError('加载版本历史失败');
    } finally {
      setLoading(false);
    }
  }, [projectId, chapterId]);

  useEffect(() => {
    if (isOpen) {
      loadVersions();
    }
  }, [isOpen, loadVersions]);

  // 退出对比模式时清空状态
  useEffect(() => {
    if (!compareMode) {
      setCompareV1(undefined);
      setCompareV2(undefined);
      setDiffData(null);
    }
  }, [compareMode]);

  const handleCreateSnapshot = async () => {
    setCreatingSnapshot(true);
    try {
      await versionApi.createSnapshot(projectId, snapshotSummary || undefined);
      message.success('快照创建成功');
      setSnapshotModalOpen(false);
      setSnapshotSummary('');
      await loadVersions();
    } catch {
      message.error('创建快照失败');
    } finally {
      setCreatingSnapshot(false);
    }
  };

  const handleRollback = (version: VersionSummary) => {
    Modal.confirm({
      title: '确认回滚',
      content: (
        <div>
          <p>确认回滚到 <strong>V{version.version_number}</strong> 吗？</p>
          <p style={{ color: '#888', fontSize: 12, marginTop: 8 }}>
            回滚前会自动创建当前状态的快照，以便需要时恢复。
          </p>
        </div>
      ),
      okText: '确认回滚',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        setRollingBackId(version.id);
        try {
          await versionApi.rollback(projectId, version.id, true);
          message.success('回滚成功，页面即将刷新');
          setTimeout(() => window.location.reload(), 800);
        } catch {
          message.error('回滚失败');
        } finally {
          setRollingBackId(null);
        }
      },
    });
  };

  const handleCompare = async () => {
    if (!compareV1 || !compareV2) {
      message.warning('请选择两个版本进行对比');
      return;
    }
    if (compareV1 === compareV2) {
      message.warning('请选择不同的版本');
      return;
    }
    setDiffLoading(true);
    setDiffData(null);
    try {
      const result = await versionApi.diff(projectId, compareV1, compareV2);
      setDiffData(result);
    } catch {
      message.error('获取版本差异失败');
    } finally {
      setDiffLoading(false);
    }
  };

  // 版本选项列表
  const versionOptions = versions.map((v) => ({
    value: v.id,
    label: `V${v.version_number} - ${CHANGE_TYPE_LABELS[v.change_type] || v.change_type} (${formatDate(v.created_at)})`,
  }));

  const timelineItems = versions.map((version) => ({
    key: version.id,
    dot: (
      <span style={{ fontSize: 14, color: CHANGE_TYPE_COLORS[version.change_type] || '#666' }}>
        {CHANGE_TYPE_ICONS[version.change_type] || <HistoryOutlined />}
      </span>
    ),
    children: (
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Space size={6} wrap>
            <Typography.Text strong>V{version.version_number}</Typography.Text>
            <Tag color={CHANGE_TYPE_COLORS[version.change_type] || 'default'}>
              {CHANGE_TYPE_LABELS[version.change_type] || version.change_type}
            </Tag>
          </Space>
          <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
            {formatDate(version.created_at)}
          </div>
          {version.change_summary && (
            <div style={{ fontSize: 13, color: '#555', marginTop: 4, wordBreak: 'break-all' }}>
              {version.change_summary}
            </div>
          )}
        </div>
        <Button
          size="small"
          type="text"
          danger
          icon={<RollbackOutlined />}
          loading={rollingBackId === version.id}
          onClick={() => handleRollback(version)}
          style={{ marginLeft: 8, flexShrink: 0 }}
        >
          回滚
        </Button>
      </div>
    ),
  }));

  // 对比模式 UI
  const renderComparePanel = () => (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          旧版本（左）
        </Typography.Text>
        <Select
          style={{ width: '100%' }}
          placeholder="选择旧版本"
          value={compareV1}
          onChange={setCompareV1}
          options={versionOptions}
          showSearch
          optionFilterProp="label"
        />
      </div>
      <div style={{ marginBottom: 12 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          新版本（右）
        </Typography.Text>
        <Select
          style={{ width: '100%' }}
          placeholder="选择新版本"
          value={compareV2}
          onChange={setCompareV2}
          options={versionOptions}
          showSearch
          optionFilterProp="label"
        />
      </div>
      <Button
        type="primary"
        block
        onClick={handleCompare}
        loading={diffLoading}
        disabled={!compareV1 || !compareV2}
        icon={<SwapOutlined />}
      >
        对比版本
      </Button>

      <Divider style={{ margin: '16px 0' }} />

      {diffLoading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
          <Spin tip="正在计算差异..." />
        </div>
      )}

      {diffData && !diffLoading && <VersionDiff diffData={diffData} />}

      {!diffData && !diffLoading && (
        <Empty description="选择两个版本后点击对比" style={{ marginTop: 24 }} />
      )}
    </div>
  );

  return (
    <>
      <Drawer
        title={
          <Space>
            <HistoryOutlined />
            <span>版本历史</span>
            {total > 0 && (
              <Tag style={{ marginLeft: 4 }}>{total}</Tag>
            )}
          </Space>
        }
        placement="right"
        width={compareMode ? 520 : 400}
        open={isOpen}
        onClose={onClose}
        extra={
          <Space>
            <Button
              size="small"
              type={compareMode ? 'primary' : 'default'}
              icon={<SwapOutlined />}
              onClick={() => setCompareMode(!compareMode)}
            >
              {compareMode ? '退出对比' : '版本对比'}
            </Button>
            <Button
              size="small"
              icon={<CameraOutlined />}
              onClick={() => setSnapshotModalOpen(true)}
            >
              创建快照
            </Button>
          </Space>
        }
      >
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <Spin />
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', color: 'red', padding: 40 }}>{error}</div>
        ) : versions.length === 0 ? (
          <Empty description="暂无版本历史" style={{ marginTop: 40 }} />
        ) : compareMode ? (
          renderComparePanel()
        ) : (
          <>
            <Timeline items={timelineItems} style={{ marginTop: 8 }} />
            {total > versions.length && (
              <div style={{ textAlign: 'center', color: '#888', fontSize: 12, padding: '8px 0' }}>
                显示 {versions.length} / {total} 条记录
              </div>
            )}
          </>
        )}
      </Drawer>

      <Modal
        title="创建快照"
        open={snapshotModalOpen}
        onCancel={() => {
          setSnapshotModalOpen(false);
          setSnapshotSummary('');
        }}
        onOk={handleCreateSnapshot}
        okText="创建"
        confirmLoading={creatingSnapshot}
      >
        <div style={{ marginBottom: 8, color: '#555' }}>可选填写本次快照的摘要说明：</div>
        <Input.TextArea
          rows={3}
          placeholder="如：正式提交前备份"
          value={snapshotSummary}
          onChange={(e) => setSnapshotSummary(e.target.value)}
        />
      </Modal>
    </>
  );
};

export default VersionHistory;
