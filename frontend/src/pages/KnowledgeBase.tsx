import React, { useState, useRef, useEffect } from 'react';
import { ProTable, ActionType, ProColumns } from '@ant-design/pro-components';
import { Button, Tag, Space, Modal, Form, Input, Select, Upload, message, Typography, Popconfirm } from 'antd';
import { PlusOutlined, UploadOutlined, CloudUploadOutlined } from '@ant-design/icons';
import api from '../services/api';
import type { KnowledgeDoc } from '../types/knowledge';
import { useLayoutHeader } from '../layouts/layoutHeader';

const POLL_INTERVAL = 5000; // 5秒轮询

const KnowledgeBase: React.FC = () => {
  const { setLayoutHeader } = useLayoutHeader();
  const actionRef = useRef<ActionType>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [hasProcessing, setHasProcessing] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 当存在 indexing/pending 状态时自动轮询刷新
  useEffect(() => {
    if (hasProcessing) {
      pollingRef.current = setInterval(() => {
        actionRef.current?.reload();
      }, POLL_INTERVAL);
    } else if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [hasProcessing]);

  useEffect(() => {
    setLayoutHeader({
      content: (
        <div className="flex min-w-0 items-center gap-4 py-2">
          <h1 className="shrink-0 text-[18px] font-semibold tracking-tight text-slate-900">知识库管理</h1>
          <span className="h-5 w-px shrink-0 bg-slate-200" />
          <span className="truncate text-sm text-slate-500">
            管理历史标书、企业资料和案例片段，智能推荐相关内容
          </span>
        </div>
      ),
    });

    return () => {
      setLayoutHeader(null);
    };
  }, [setLayoutHeader]);
  
  const [createForm] = Form.useForm();
  const [uploadForm] = Form.useForm();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'indexing': return 'processing';
      case 'pending': return 'warning';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'completed': return '已完成';
      case 'indexing': return '索引中';
      case 'pending': return '待索引';
      case 'failed': return '失败';
      default: return status;
    }
  };

  const handleReindex = async (id: string) => {
    try {
      message.loading('正在重新索引...');
      await api.post(`/api/knowledge/${id}/reindex`);
      message.success('已发送重新索引请求');
      actionRef.current?.reload();
    } catch (error: any) {
      console.error('重新索引失败:', error);
      message.error(error.response?.data?.detail || '重新索引失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/knowledge/${id}`);
      message.success('删除成功');
      actionRef.current?.reload();
    } catch (error: any) {
      console.error('删除失败:', error);
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const handleCreateSubmit = async (values: any) => {
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('title', values.title);
      formData.append('content', values.content);
      formData.append('doc_type', values.doc_type);
      formData.append('scope', values.scope);
      if (values.tags) formData.append('tags', values.tags);
      if (values.category) formData.append('category', values.category);

      await api.post('/api/knowledge/create', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      message.success('创建成功，正在生成索引');
      setShowCreateModal(false);
      createForm.resetFields();
      actionRef.current?.reload();
    } catch (error: any) {
      console.error('创建失败:', error);
      message.error(error.response?.data?.detail || '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUploadSubmit = async (values: any) => {
    if (!uploadFile) {
      message.warning('请选择要上传的文件');
      return;
    }

    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('title', values.title);
      formData.append('doc_type', values.doc_type);
      formData.append('scope', values.scope);
      if (values.tags) formData.append('tags', values.tags);
      if (values.category) formData.append('category', values.category);

      await api.post('/api/knowledge/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      message.success('上传成功，正在后台生成索引');
      setShowUploadModal(false);
      setUploadFile(null);
      uploadForm.resetFields();
      actionRef.current?.reload();
    } catch (error: any) {
      console.error('上传失败:', error);
      message.error(error.response?.data?.detail || '上传失败');
    } finally {
      setSubmitting(false);
    }
  };

  const columns: ProColumns<KnowledgeDoc>[] = [
    {
      title: '标题',
      dataIndex: 'title',
      width: '25%',
      render: (dom, entity) => (
        <div>
          <Typography.Text strong>{dom}</Typography.Text>
          {entity.tags && entity.tags.length > 0 && (
            <div style={{ marginTop: 4 }}>
              {entity.tags.map(tag => <Tag key={tag} color="blue">{tag}</Tag>)}
            </div>
          )}
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'doc_type',
      valueType: 'select',
      valueEnum: {
        all: { text: '全部类型', status: 'Default' },
        history_bid: { text: '历史标书', status: 'Success' },
        company_info: { text: '企业资料', status: 'Processing' },
        case_fragment: { text: '案例片段', status: 'Warning' },
        other: { text: '其他', status: 'Default' },
      },
      render: (_, entity) => {
        const labels: Record<string, string> = {
          history_bid: '历史标书',
          company_info: '企业资料',
          case_fragment: '案例片段',
          other: '其他'
        };
        return <Tag color="purple">{labels[entity.doc_type] || entity.doc_type}</Tag>;
      }
    },
    {
      title: '范围',
      dataIndex: 'scope',
      valueType: 'select',
      valueEnum: {
        all: { text: '全部范围', status: 'Default' },
        global: { text: '全局', status: 'Success' },
        enterprise: { text: '企业', status: 'Processing' },
        user: { text: '个人', status: 'Default' },
      },
      render: (_, entity) => {
        const labels: Record<string, string> = {
          global: '全局',
          enterprise: '企业',
          user: '个人'
        };
        return <Tag>{labels[entity.scope] || entity.scope}</Tag>;
      }
    },
    {
      title: '索引状态',
      dataIndex: 'pageindex_status',
      search: false,
      render: (_, entity) => (
        <Tag color={getStatusColor(entity.pageindex_status)}>
          {getStatusLabel(entity.pageindex_status)}
        </Tag>
      ),
    },
    {
      title: '使用次数',
      dataIndex: 'usage_count',
      search: false,
      align: 'center',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      valueType: 'date',
      search: false,
    },
    {
      title: '操作',
      valueType: 'option',
      width: 180,
      render: (text, record, _, action) => [
        <Typography.Link
          key="reindex"
          onClick={() => handleReindex(record.id)}
          disabled={record.pageindex_status === 'indexing'}
        >
          重新索引
        </Typography.Link>,
        <Popconfirm
          key="delete"
          title="确定要删除这个知识库文档吗？"
          onConfirm={() => handleDelete(record.id)}
          okText="确定"
          cancelText="取消"
        >
          <Typography.Link type="danger">删除</Typography.Link>
        </Popconfirm>,
      ],
    },
  ];

  return (
    <div className="min-h-full bg-gray-50">
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <ProTable<KnowledgeDoc>
        columns={columns}
        actionRef={actionRef}
        cardBordered
        request={async (params) => {
          const queryParams = new URLSearchParams();
          if (params.doc_type && params.doc_type !== 'all') queryParams.append('doc_type', params.doc_type);
          if (params.scope && params.scope !== 'all') queryParams.append('scope', params.scope);
          
          try {
            const response = await api.get(`/api/knowledge?${queryParams.toString()}`);
            let data = response.data;
            // 客户端实现简单的标题搜索
            if (params.title) {
              data = data.filter((item: KnowledgeDoc) => item.title.includes(params.title));
            }
            // 检测是否有正在处理的文档，驱动轮询
            const processing = data.some((item: KnowledgeDoc) =>
              item.pageindex_status === 'indexing' || item.pageindex_status === 'pending'
            );
            setHasProcessing(processing);
            return {
              data: data,
              success: true,
              total: data.length,
            };
          } catch (error) {
            console.error('获取列表失败:', error);
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
          <Button key="create" type="primary" onClick={() => setShowUploadModal(true)} icon={<CloudUploadOutlined />}>
            上传文件
          </Button>,
          <Button key="manual" onClick={() => setShowCreateModal(true)} icon={<PlusOutlined />}>
            手动创建
          </Button>,
        ]}
      />

      <Modal
        title="手动创建知识库内容"
        open={showCreateModal}
        onCancel={() => setShowCreateModal(false)}
        onOk={() => createForm.submit()}
        confirmLoading={submitting}
        width={700}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreateSubmit}
          initialValues={{ doc_type: 'other', scope: 'user' }}
        >
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="请输入标题" />
          </Form.Item>
          <Form.Item name="content" label="内容" rules={[{ required: true, message: '请输入内容' }]}>
            <Input.TextArea rows={8} placeholder="支持 Markdown 格式" />
          </Form.Item>
          <Space size="large" style={{ display: 'flex', width: '100%' }}>
            <Form.Item name="doc_type" label="文档类型" style={{ flex: 1, minWidth: 200 }}>
              <Select>
                <Select.Option value="history_bid">历史标书</Select.Option>
                <Select.Option value="company_info">企业资料</Select.Option>
                <Select.Option value="case_fragment">案例片段</Select.Option>
                <Select.Option value="other">其他</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="scope" label="范围" style={{ flex: 1, minWidth: 200 }}>
              <Select>
                <Select.Option value="user">个人</Select.Option>
                <Select.Option value="enterprise">企业</Select.Option>
                <Select.Option value="global">全局</Select.Option>
              </Select>
            </Form.Item>
          </Space>
          <Space size="large" style={{ display: 'flex', width: '100%' }}>
            <Form.Item name="tags" label="标签" help="多个标签请用逗号分隔" style={{ flex: 1, minWidth: 200 }}>
              <Input placeholder="例如：智慧城市,招投标" />
            </Form.Item>
            <Form.Item name="category" label="分类" style={{ flex: 1, minWidth: 200 }}>
              <Input placeholder="请输入分类" />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      <Modal
        title="上传知识库文件"
        open={showUploadModal}
        onCancel={() => { setShowUploadModal(false); setUploadFile(null); }}
        onOk={() => uploadForm.submit()}
        confirmLoading={submitting}
        okButtonProps={{ disabled: !uploadFile }}
      >
        <Form
          form={uploadForm}
          layout="vertical"
          onFinish={handleUploadSubmit}
          initialValues={{ doc_type: 'other', scope: 'user' }}
        >
          <Form.Item label="文件" required>
            <Upload
              beforeUpload={(file) => {
                setUploadFile(file);
                if (!uploadForm.getFieldValue('title')) {
                  uploadForm.setFieldsValue({ title: file.name.replace(/\.[^/.]+$/, '') });
                }
                return false; // Prevent auto upload
              }}
              onRemove={() => setUploadFile(null)}
              fileList={uploadFile ? [uploadFile as any] : []}
              maxCount={1}
              accept=".pdf,.doc,.docx"
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="请输入标题" />
          </Form.Item>
          <Form.Item name="doc_type" label="文档类型">
            <Select>
              <Select.Option value="history_bid">历史标书</Select.Option>
              <Select.Option value="company_info">企业资料</Select.Option>
              <Select.Option value="case_fragment">案例片段</Select.Option>
              <Select.Option value="other">其他</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="scope" label="范围">
            <Select>
              <Select.Option value="user">个人</Select.Option>
              <Select.Option value="enterprise">企业</Select.Option>
              <Select.Option value="global">全局</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="tags" label="标签" help="多个标签请用逗号分隔">
            <Input placeholder="例如：智慧城市,招投标" />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Input placeholder="请输入分类" />
          </Form.Item>
        </Form>
      </Modal>

      </main>
    </div>
  );
};

export default KnowledgeBase;
