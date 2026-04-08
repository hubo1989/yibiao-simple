/**
 * 版本历史侧边栏 (Ant Design Drawer + Timeline)
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
} from 'antd';
import {
  HistoryOutlined,
  RobotOutlined,
  EditOutlined,
  AuditOutlined,
  RollbackOutlined,
  CameraOutlined,
} from '@ant-design/icons';
import { versionApi } from '../services/api';
import type { VersionSummary } from '../types/version';

interface VersionHistoryProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  chapterId?: string;
}

type ChangeType = VersionSummary['change_type'];

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
      title: `确认回滚到 V${version.version_number}`,
      content: (
        <div>
          <p>确定要回滚到版本 <strong>V{version.version_number}</strong> 吗？</p>
          <p style={{ marginTop: 8, color: '#888', fontSize: 13 }}>
            回滚前会自动创建当前状态的快照，以便需要时恢复。
          </p>
        </div>
      ),
      okText: '确认回滚',
      okType: 'danger',
      cancelText: '取消',
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
          icon={<RollbackOutlined />}
          loading={rollingBackId === version.id}
          onClick={() => handleRollback(version)}
          style={{ marginLeft: 8, flexShrink: 0 }}
        >
          恢复
        </Button>
      </div>
    ),
  }));

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
        width={400}
        open={isOpen}
        onClose={onClose}
        extra={
          <Button
            size="small"
            icon={<CameraOutlined />}
            onClick={() => setSnapshotModalOpen(true)}
          >
            创建快照
          </Button>
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
