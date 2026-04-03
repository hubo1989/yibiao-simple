import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageContainer, ProTable, ActionType, ProColumns } from '@ant-design/pro-components';
import { Button, Tag, Typography, message, Modal, Form, Input } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { projectApi } from '../services/api';
import type { ProjectSummary } from '../types/project';
import { PROJECT_STATUS_LABELS, ProjectStatus } from '../types/project';
import { getErrorMessage } from '../utils/error';

const ProjectManager: React.FC = () => {
  const navigate = useNavigate();
  const actionRef = useRef<ActionType>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm] = Form.useForm();
  const [creating, setCreating] = useState(false);

  const getStatusColor = (status: ProjectStatus) => {
    switch (status) {
      case 'draft': return 'default';
      case 'in_progress': return 'processing';
      case 'reviewing': return 'warning';
      case 'completed': return 'success';
      default: return 'default';
    }
  };

  const handleCreateProject = async (values: { name: string; description?: string }) => {
    try {
      setCreating(true);
      const newProject = await projectApi.create({
        name: values.name,
        description: values.description
      });
      message.success('创建项目成功');
      setShowCreateModal(false);
      createForm.resetFields();
      navigate(`/project/${newProject.id}`);
    } catch (err: unknown) {
      console.error('创建项目失败:', err);
      message.error(getErrorMessage(err, '创建项目失败'));
    } finally {
      setCreating(false);
    }
  };

  const columns: ProColumns<ProjectSummary>[] = [
    {
      title: '项目 ID',
      dataIndex: 'id',
      ellipsis: true,
      width: 120,
      search: false,
      render: (dom) => <Typography.Text copyable ellipsis>{dom}</Typography.Text>
    },
    {
      title: '项目名称',
      dataIndex: 'name',
      copyable: true,
      width: 200,
      render: (dom, entity) => (
        <Button type="link" onClick={() => navigate(`/project/${entity.id}`)} style={{ fontWeight: 500, padding: 0 }}>
          {dom}
        </Button>
      )
    },
    {
      title: '项目状态',
      dataIndex: 'status',
      valueType: 'select',
      valueEnum: {
        all: { text: '全部', status: 'Default' },
        draft: { text: '草稿', status: 'Default' },
        in_progress: { text: '进行中', status: 'Processing' },
        reviewing: { text: '审核中', status: 'Warning' },
        completed: { text: '已完成', status: 'Success' },
      },
      render: (_, entity) => (
        <Tag color={getStatusColor(entity.status)}>
          {PROJECT_STATUS_LABELS[entity.status]}
        </Tag>
      )
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      valueType: 'dateRange',
      hideInTable: true,
      search: {
        transform: (value) => {
          return {
            start_time: value[0],
            end_time: value[1],
          };
        },
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      valueType: 'dateTime',
      search: false,
      sorter: true,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      valueType: 'dateTime',
      search: false,
      sorter: true,
    },
    {
      title: '操作',
      valueType: 'option',
      width: 150,
      render: (text, record, _, action) => [
        <Button key="view" type="link" onClick={() => navigate(`/project/${record.id}`)} style={{ padding: 0 }}>
          进入工作区
        </Button>,
        <Button key="review" type="link" onClick={() => navigate(`/project/${record.id}/review`)} style={{ padding: 0 }}>
          审核
        </Button>,
        <Button key="settings" type="link" onClick={() => navigate(`/project/${record.id}/settings`)} style={{ padding: 0 }}>
          设置
        </Button>,
      ],
    },
  ];

  return (
    <PageContainer
      header={{
        title: '标书项目管理',
        ghost: true,
      }}
    >
      <ProTable<ProjectSummary>
        columns={columns}
        actionRef={actionRef}
        cardBordered
        request={async (params, sort, filter) => {
          try {
            const queryParams: Record<string, any> = {
              sort_by: sort && Object.keys(sort)[0] ? Object.keys(sort)[0] : 'updated_at',
              sort_order: sort && Object.values(sort)[0] === 'ascend' ? 'asc' : 'desc',
            };
            
            const response = await projectApi.list(queryParams);
            let data = response;
            
            // Client side filtering for simplicity
            if (params.name) {
              data = data.filter((item: ProjectSummary) => item.name.includes(params.name as string));
            }
            if (params.status && params.status !== 'all') {
              data = data.filter((item: ProjectSummary) => item.status === params.status);
            }
            if (params.start_time) {
              data = data.filter((item: ProjectSummary) => new Date(item.created_at) >= new Date(params.start_time as string));
            }
            if (params.end_time) {
              data = data.filter((item: ProjectSummary) => new Date(item.created_at) <= new Date(params.end_time as string));
            }

            return {
              data: data,
              success: true,
              total: data.length,
            };
          } catch (error) {
            console.error('获取项目列表失败:', error);
            return { data: [], success: false, total: 0 };
          }
        }}
        rowKey="id"
        search={{
          labelWidth: 'auto',
        }}
        pagination={{
          pageSize: 10,
          showSizeChanger: true,
        }}
        dateFormatter="string"
        toolBarRender={() => [
          <Button key="create" type="primary" onClick={() => setShowCreateModal(true)} icon={<PlusOutlined />}>
            新建项目
          </Button>,
        ]}
      />

      <Modal
        title="新建项目"
        open={showCreateModal}
        onCancel={() => setShowCreateModal(false)}
        onOk={() => createForm.submit()}
        confirmLoading={creating}
        okText={creating ? '创建中...' : '创建'}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreateProject}
        >
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input placeholder="请输入项目名称" />
          </Form.Item>
          <Form.Item name="description" label="项目描述">
            <Input.TextArea rows={3} placeholder="请输入项目描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
};

export default ProjectManager;
