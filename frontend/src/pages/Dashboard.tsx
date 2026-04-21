/**
 * 进度看板 — 全局项目进度视图
 */
import React, { useEffect, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Statistic,
  Progress,
  Tag,
  Space,
  Segmented,
  Empty,
  Spin,
  Typography,
} from 'antd';
import {
  ProjectOutlined,
  SyncOutlined,
  AuditOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { dashboardApi } from '../services/api';
import type { DashboardResponse, DashboardProjectItem } from '../services/api';
import type { ProjectStatus } from '../types/project';

const { Text } = Typography;

const STATUS_TAG_CONFIG: Record<string, { color: string; label: string }> = {
  draft: { color: 'default', label: '草稿' },
  in_progress: { color: 'processing', label: '进行中' },
  reviewing: { color: 'warning', label: '审核中' },
  completed: { color: 'success', label: '已完成' },
};

const FILTER_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: '进行中', value: 'in_progress' },
  { label: '审核中', value: 'reviewing' },
  { label: '已完成', value: 'completed' },
];

function formatTime(isoStr: string): string {
  const d = new Date(isoStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return '刚刚';
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} 小时前`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay} 天前`;
  return d.toLocaleDateString('zh-CN');
}

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await dashboardApi.overview();
      setData(res);
    } catch {
      // error handled by api layer
    } finally {
      setLoading(false);
    }
  };

  const filteredProjects: DashboardProjectItem[] =
    data?.projects.filter((p) => filter === 'all' || p.status === filter) ?? [];

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (!data) {
    return <Empty description="加载失败，请刷新重试" />;
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      {/* 顶部指标卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card bordered={false} size="small">
            <Statistic
              title="总项目数"
              value={data.total_projects}
              prefix={<ProjectOutlined style={{ color: '#1677ff' }} />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card bordered={false} size="small">
            <Statistic
              title="进行中"
              value={data.by_status.in_progress}
              prefix={<SyncOutlined style={{ color: '#1677ff' }} />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card bordered={false} size="small">
            <Statistic
              title="审核中"
              value={data.by_status.reviewing}
              prefix={<AuditOutlined style={{ color: '#fa8c16' }} />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card bordered={false} size="small">
            <Statistic
              title="已完成"
              value={data.by_status.completed}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 筛选栏 */}
      <div style={{ marginBottom: 16 }}>
        <Segmented
          options={FILTER_OPTIONS}
          value={filter}
          onChange={(val) => setFilter(val as string)}
        />
      </div>

      {/* 项目进度列表 */}
      {filteredProjects.length === 0 ? (
        <Empty description="暂无项目" />
      ) : (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {filteredProjects.map((proj) => {
            const cfg = STATUS_TAG_CONFIG[proj.status] || STATUS_TAG_CONFIG.draft;
            const stats = proj.chapter_stats;
            return (
              <Card
                key={proj.id}
                size="small"
                hoverable
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/project/${proj.id}`)}
              >
                <Row align="middle" gutter={[16, 8]}>
                  {/* 项目名 + 状态 */}
                  <Col xs={24} sm={8}>
                    <Space>
                      <Text strong style={{ fontSize: 15 }}>{proj.name}</Text>
                      <Tag color={cfg.color}>{cfg.label}</Tag>
                    </Space>
                  </Col>

                  {/* 进度条 */}
                  <Col xs={24} sm={6}>
                    <Progress
                      percent={proj.completion_percentage}
                      size="small"
                      strokeColor="#52c41a"
                      format={(pct) => `${pct}%`}
                    />
                  </Col>

                  {/* 章节状态分布 */}
                  <Col xs={24} sm={7}>
                    <Space size={4} wrap>
                      {stats.pending > 0 && <Tag>待生成 {stats.pending}</Tag>}
                      {stats.generated > 0 && <Tag color="blue">已生成 {stats.generated}</Tag>}
                      {stats.reviewing > 0 && <Tag color="orange">审核中 {stats.reviewing}</Tag>}
                      {stats.finalized > 0 && <Tag color="green">已定稿 {stats.finalized}</Tag>}
                      {stats.total === 0 && <Text type="secondary">暂无章节</Text>}
                    </Space>
                  </Col>

                  {/* 最近更新 */}
                  <Col xs={24} sm={3} style={{ textAlign: 'right' }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {formatTime(proj.updated_at)}
                    </Text>
                  </Col>
                </Row>
              </Card>
            );
          })}
        </Space>
      )}
    </div>
  );
};

export default Dashboard;
