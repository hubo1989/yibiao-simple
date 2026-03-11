import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageContainer, ProCard } from '@ant-design/pro-components';
import {
  Avatar,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Progress,
  Row,
  Space,
  Statistic,
  Tag,
  Typography,
} from 'antd';
import {
  ArrowRightOutlined,
  AuditOutlined,
  BookOutlined,
  CheckCircleOutlined,
  FileAddOutlined,
  FolderOpenOutlined,
  PlusOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { projectApi } from '../services/api';
import type { ProjectCreate, ProjectProgress, ProjectSummary } from '../types/project';
import { PROJECT_STATUS_LABELS, ProjectStatus } from '../types/project';

interface ProjectWithProgress extends ProjectSummary {
  progress?: ProjectProgress;
}

const ProjectList: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [projects, setProjects] = useState<ProjectWithProgress[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState<ProjectCreate>({ name: '', description: '' });
  const [creating, setCreating] = useState(false);

  const loadProjects = useCallback(async () => {
    try {
      setLoading(true);
      const projectList = await projectApi.list({ sort_by: 'updated_at', sort_order: 'desc' });
      const projectsWithProgress = await Promise.all(
        projectList.map(async (project) => {
          try {
            const progress = await projectApi.getProgress(project.id);
            return { ...project, progress };
          } catch {
            return { ...project, progress: undefined };
          }
        })
      );
      setProjects(projectsWithProgress);
    } catch (err) {
      console.error('加载项目失败:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreateProject = async () => {
    if (!createForm.name.trim()) return;
    try {
      setCreating(true);
      const newProject = await projectApi.create(createForm);
      navigate(`/project/${newProject.id}`);
    } catch (err) {
      console.error('创建项目失败:', err);
    } finally {
      setCreating(false);
    }
  };

  const projectStats = useMemo(() => {
    const total = projects.length;
    const active = projects.filter((project) => project.status === 'in_progress').length;
    const reviewing = projects.filter((project) => project.status === 'reviewing').length;
    const completed = projects.filter((project) => project.status === 'completed').length;
    const averageProgress =
      total === 0
        ? 0
        : Math.round(
            projects.reduce((sum, project) => sum + (project.progress?.completion_percentage || 0), 0) / total
          );

    return { total, active, reviewing, completed, averageProgress };
  }, [projects]);

  const recentProjects = useMemo(() => projects.slice(0, 6), [projects]);
  const recentUpdates = useMemo(() => projects.slice(0, 5), [projects]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
    });
  };

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusColor = (status: ProjectStatus) => {
    const colors: Record<ProjectStatus, string> = {
      draft: 'default',
      in_progress: 'processing',
      reviewing: 'warning',
      completed: 'success',
    };
    return colors[status] || 'default';
  };

  return (
    <PageContainer header={{ title: '' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card
          style={{
            borderRadius: 24,
            overflow: 'hidden',
            background:
              'linear-gradient(135deg, rgba(22,119,255,0.12) 0%, rgba(255,255,255,0.98) 42%, rgba(19,194,194,0.10) 100%)',
            border: '1px solid rgba(22, 119, 255, 0.10)',
          }}
          bodyStyle={{ padding: 28 }}
        >
          <Row gutter={[24, 24]} align="middle" justify="space-between">
            <Col xs={24} xl={16}>
              <Space size="large" align="start">
                <Avatar size={68} style={{ background: 'linear-gradient(135deg, #1677ff 0%, #13c2c2 100%)' }}>
                  {(user?.username || 'U').slice(0, 1).toUpperCase()}
                </Avatar>
                <div>
                  <Typography.Text style={{ color: '#1677ff', fontWeight: 700 }}>
                    项目工作台
                  </Typography.Text>
                  <Typography.Title level={3} style={{ marginTop: 8, marginBottom: 8 }}>
                    {user?.username || '团队成员'}，先处理最近要交付的项目。
                  </Typography.Title>
                  <Typography.Paragraph style={{ marginBottom: 0, maxWidth: 720, color: 'rgba(15, 23, 42, 0.62)' }}>
                    当前界面不再混入硬编码的待办或公告，而是直接基于真实项目状态、进度和最近更新时间组织信息。
                  </Typography.Paragraph>
                </div>
              </Space>
            </Col>
            <Col xs={24} xl={8}>
              <Space wrap style={{ justifyContent: 'flex-end', width: '100%' }}>
                <Button icon={<FolderOpenOutlined />} onClick={() => navigate('/projects')}>
                  查看全部项目
                </Button>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowCreateModal(true)}>
                  新建项目
                </Button>
              </Space>
              <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'right', marginTop: 12 }}>
                {new Date().toLocaleDateString('zh-CN', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  weekday: 'long',
                })}
              </Typography.Text>
            </Col>
          </Row>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} md={12} xl={6}>
            <Card bordered={false} style={{ borderRadius: 20 }}>
              <Statistic title="项目总数" value={projectStats.total} prefix={<FolderOpenOutlined />} />
            </Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card bordered={false} style={{ borderRadius: 20 }}>
              <Statistic title="进行中" value={projectStats.active} prefix={<SyncOutlined />} valueStyle={{ color: '#1677ff' }} />
            </Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card bordered={false} style={{ borderRadius: 20 }}>
              <Statistic title="待审核" value={projectStats.reviewing} prefix={<AuditOutlined />} valueStyle={{ color: '#d48806' }} />
            </Card>
          </Col>
          <Col xs={24} md={12} xl={6}>
            <Card bordered={false} style={{ borderRadius: 20 }}>
              <Statistic title="平均完成度" value={projectStats.averageProgress} suffix="%" prefix={<CheckCircleOutlined />} valueStyle={{ color: '#389e0d' }} />
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={16}>
            <ProCard
              title="最近项目"
              loading={loading}
              extra={
                <Button type="link" icon={<ArrowRightOutlined />} onClick={() => navigate('/projects')}>
                  打开项目管理
                </Button>
              }
            >
              {recentProjects.length === 0 ? (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="当前还没有项目，先创建一个项目开始"
                >
                  <Button type="primary" icon={<FileAddOutlined />} onClick={() => setShowCreateModal(true)}>
                    创建首个项目
                  </Button>
                </Empty>
              ) : (
                <Row gutter={[16, 16]}>
                  {recentProjects.map((project) => (
                    <Col xs={24} md={12} key={project.id}>
                      <Card
                        hoverable
                        size="small"
                        style={{ borderRadius: 18 }}
                        bodyStyle={{ padding: 18 }}
                        onClick={() => navigate(`/project/${project.id}`)}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                          <div style={{ minWidth: 0 }}>
                            <Typography.Title level={5} style={{ marginBottom: 8 }}>
                              {project.name}
                            </Typography.Title>
                            <Typography.Paragraph
                              ellipsis={{ rows: 2 }}
                              style={{ marginBottom: 12, color: 'rgba(15, 23, 42, 0.62)' }}
                            >
                              {project.description || '暂无项目描述'}
                            </Typography.Paragraph>
                          </div>
                          <Tag color={getStatusColor(project.status)}>{PROJECT_STATUS_LABELS[project.status]}</Tag>
                        </div>

                        {project.progress?.total_chapters ? (
                          <div style={{ marginBottom: 12 }}>
                            <Progress percent={project.progress.completion_percentage} size="small" status="active" />
                          </div>
                        ) : null}

                        <Space split={<span style={{ color: '#d9d9d9' }}>|</span>} size={0} wrap>
                          <Typography.Text type="secondary">更新于 {formatDateTime(project.updated_at)}</Typography.Text>
                          <Typography.Text type="secondary">创建于 {formatDate(project.created_at)}</Typography.Text>
                        </Space>
                      </Card>
                    </Col>
                  ))}
                </Row>
              )}
            </ProCard>
          </Col>

          <Col xs={24} xl={8}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <ProCard title="快捷操作">
                <Row gutter={[12, 12]}>
                  <Col span={12}>
                    <Button block style={{ height: 88 }} onClick={() => setShowCreateModal(true)}>
                      <Space direction="vertical" size={6}>
                        <FileAddOutlined style={{ fontSize: 22, color: '#1677ff' }} />
                        <span>新建项目</span>
                      </Space>
                    </Button>
                  </Col>
                  <Col span={12}>
                    <Button block style={{ height: 88 }} onClick={() => navigate('/projects')}>
                      <Space direction="vertical" size={6}>
                        <FolderOpenOutlined style={{ fontSize: 22, color: '#722ed1' }} />
                        <span>项目管理</span>
                      </Space>
                    </Button>
                  </Col>
                  <Col span={12}>
                    <Button block style={{ height: 88 }} onClick={() => navigate('/knowledge')}>
                      <Space direction="vertical" size={6}>
                        <BookOutlined style={{ fontSize: 22, color: '#13c2c2' }} />
                        <span>知识库</span>
                      </Space>
                    </Button>
                  </Col>
                  <Col span={12}>
                    <Button block style={{ height: 88 }} onClick={() => navigate('/projects')}>
                      <Space direction="vertical" size={6}>
                        <AuditOutlined style={{ fontSize: 22, color: '#d48806' }} />
                        <span>进入审核</span>
                      </Space>
                    </Button>
                  </Col>
                </Row>
              </ProCard>

              <ProCard title="最近更新" loading={loading}>
                {recentUpdates.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无项目更新记录" />
                ) : (
                  <List
                    dataSource={recentUpdates}
                    renderItem={(project) => (
                      <List.Item
                        style={{ paddingInline: 0, cursor: 'pointer' }}
                        onClick={() => navigate(`/project/${project.id}`)}
                      >
                        <List.Item.Meta
                          title={
                            <Space size={8} wrap>
                              <Typography.Text strong>{project.name}</Typography.Text>
                              <Tag color={getStatusColor(project.status)}>{PROJECT_STATUS_LABELS[project.status]}</Tag>
                            </Space>
                          }
                          description={
                            <Typography.Text type="secondary">
                              {project.description || '暂无项目描述'} · {formatDateTime(project.updated_at)}
                            </Typography.Text>
                          }
                        />
                      </List.Item>
                    )}
                  />
                )}
              </ProCard>
            </Space>
          </Col>
        </Row>
      </Space>

      <Modal
        title="新建项目"
        open={showCreateModal}
        onCancel={() => setShowCreateModal(false)}
        onOk={handleCreateProject}
        confirmLoading={creating}
        okText={creating ? '创建中...' : '创建'}
      >
        <Form layout="vertical">
          <Form.Item label="项目名称" required>
            <Input value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })} placeholder="请输入项目名称" />
          </Form.Item>
          <Form.Item label="项目描述">
            <Input.TextArea value={createForm.description} onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })} rows={3} placeholder="请输入项目描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
};

export default ProjectList;
