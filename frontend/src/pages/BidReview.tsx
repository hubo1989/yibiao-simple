import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ProCard } from '@ant-design/pro-components';
import { Typography, Button, message, Tag, Descriptions, Spin } from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { projectApi } from '../services/api';
import type { Project } from '../types/project';
import { PROJECT_STATUS_LABELS } from '../types/project';
import ReactMarkdown from 'react-markdown';
import ContentPageHeader from '../components/ContentPageHeader';

const { Title, Text } = Typography;

const BidReview: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const fetchProject = async () => {
      try {
        if (projectId) {
          const data = await projectApi.get(projectId);
          setProject(data);
        }
      } catch (error) {
        message.error('获取项目失败');
      } finally {
        setLoading(false);
      }
    };
    fetchProject();
  }, [projectId]);

  const handleReview = async (isApproved: boolean) => {
    if (!projectId) return;
    try {
      setSubmitting(true);
      // Assuming projectApi has an endpoint for updating status, OR update using a patch
      // If none exist, we just simulate success.
      await projectApi.update(projectId, { 
        status: isApproved ? 'completed' : 'draft',
      });
      message.success(`已${isApproved ? '通过' : '驳回'}该标书`);
      navigate('/projects');
    } catch (error) {
      message.error('提交审核意见失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center bg-gray-50 px-6">
        <ProCard style={{ textAlign: 'center', padding: '50px 0', width: '100%', maxWidth: 640 }}>
          <Text type="danger">找不到该标书项目</Text>
        </ProCard>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'in_progress': return 'processing';
      case 'reviewing': return 'warning';
      case 'completed': return 'success';
      default: return 'default';
    }
  };

  return (
    <div className="min-h-full bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <ContentPageHeader
          onBack={() => navigate('/projects')}
          eyebrow={project.name}
          title="标书审核"
          description="返回按钮固定在内容区左侧，审核操作收敛到同一层页面工具栏里。"
          actions={
            <>
              <Tag key="status" color={getStatusColor(project.status)}>
                {PROJECT_STATUS_LABELS[project.status] || project.status}
              </Tag>
              <Button danger icon={<CloseOutlined />} onClick={() => handleReview(false)} loading={submitting}>
                驳回
              </Button>
              <Button type="primary" icon={<CheckOutlined />} onClick={() => handleReview(true)} loading={submitting}>
                审核通过
              </Button>
            </>
          }
        />

        <div className="space-y-6">
        <ProCard title="标书基础信息" bordered>
          <Descriptions column={{ xs: 1, sm: 2, md: 3 }}>
            <Descriptions.Item label="项目名称">{project.name}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{new Date(project.created_at).toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="最近更新">{new Date(project.updated_at).toLocaleString()}</Descriptions.Item>
            <Descriptions.Item label="项目描述" span={3}>{project.description || '无'}</Descriptions.Item>
          </Descriptions>
        </ProCard>

        <ProCard title="项目概述与要求" bordered>
          {project.project_overview ? (
            <div style={{ marginBottom: 24 }}>
              <Title level={5}>项目概述</Title>
              <div className="markdown-body" style={{ background: '#fafafa', padding: 16, borderRadius: 8 }}>
                <ReactMarkdown>{project.project_overview}</ReactMarkdown>
              </div>
            </div>
          ) : null}
          {project.tech_requirements ? (
            <div>
              <Title level={5}>评分要求</Title>
              <div className="markdown-body" style={{ background: '#fafafa', padding: 16, borderRadius: 8 }}>
                <ReactMarkdown>{project.tech_requirements}</ReactMarkdown>
              </div>
            </div>
          ) : null}
        </ProCard>
        </div>
      </div>
    </div>
  );
};

export default BidReview;
