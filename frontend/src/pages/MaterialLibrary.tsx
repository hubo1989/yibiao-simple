import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Card, Empty, Form, Image, Input, Modal, Popconfirm, Select, Space, Tag, Upload, message } from 'antd';
import { InboxOutlined, PlusOutlined, ImportOutlined, EditOutlined, DeleteOutlined, SearchOutlined, ReloadOutlined, StopOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { materialApi } from '../services/api';
import type { MaterialAsset, MaterialCategory } from '../types/material';
import { useLayoutHeader } from '../layouts/layoutHeader';
import IngestionWizard from '../components/IngestionWizard';
import { getFileUrl, getErrorMessage, ApiError } from '../utils/error';

// 计算距今天数（正数=未来，负数=已过期）
function daysUntil(dateStr: string | null | undefined): number | null {
  if (!dateStr) return null;
  const diff = new Date(dateStr).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function ExpiryTag({ item }: { item: MaterialAsset }) {
  if (item.is_disabled) {
    return <Tag color="default">已停用</Tag>;
  }
  // 动态计算是否过期（不依赖后端 is_expired 字段）
  const days = daysUntil(item.valid_until);
  if (days !== null && days < 0) {
    return <Tag color="error">已过期</Tag>;
  }
  if (days !== null && days <= 30) {
    return <Tag color="warning">即将过期 {days} 天</Tag>;
  }
  if (item.valid_until) {
    return <Tag color="success">有效</Tag>;
  }
  return null;
}

const categoryOptions: { label: string; value: MaterialCategory }[] = [
  { label: '营业执照', value: 'business_license' },
  { label: '法人证件', value: 'legal_person_id' },
  { label: '资质证书', value: 'qualification_cert' },
  { label: '奖项证书', value: 'award_cert' },
  { label: 'ISO 证书', value: 'iso_cert' },
  { label: '合同样本', value: 'contract_sample' },
  { label: '项目案例', value: 'project_case' },
  { label: '其他', value: 'other' },
];

const MaterialLibrary: React.FC = () => {
  const { setLayoutHeader } = useLayoutHeader();
  const [items, setItems] = useState<MaterialAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [showIngestion, setShowIngestion] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [keyword, setKeyword] = useState('');
  const [category, setCategory] = useState<string | undefined>();
  const [form] = Form.useForm();
  const [showEdit, setShowEdit] = useState(false);
  const [editingItem, setEditingItem] = useState<MaterialAsset | null>(null);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editForm] = Form.useForm();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [previewPdf, setPreviewPdf] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await materialApi.list({
        category,
        keyword: keyword || undefined,
      });
      setItems(data);
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '加载素材失败'));
    } finally {
      setLoading(false);
    }
  }, [category, keyword]);

  useEffect(() => {
    setLayoutHeader({
      content: (
        <div className="flex min-w-0 items-center gap-4 py-2">
          <h1 className="shrink-0 text-[18px] font-semibold tracking-tight text-slate-900">素材库管理</h1>
          <span className="h-5 w-px shrink-0 bg-slate-200" />
          <span className="truncate text-sm text-slate-500">管理营业执照、资质证书、项目案例等投标附件素材</span>
        </div>
      ),
    });
    return () => setLayoutHeader(null);
  }, [setLayoutHeader]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredItems = useMemo(() => items, [items]);

  const handleUpload = async (values: { name: string; category: MaterialCategory; description?: string; tags?: string }) => {
    if (uploadSubmitting) return;
    if (!file) {
      message.warning('请选择要上传的素材文件');
      return;
    }
    setUploadSubmitting(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', values.name);
    formData.append('category', values.category);
    formData.append('scope', 'user');
    if (values.description) formData.append('description', values.description);
    if (values.tags) formData.append('tags', values.tags);

    try {
      await materialApi.upload(formData);
      message.success('素材上传成功');
      setShowUpload(false);
      setFile(null);
      form.resetFields();
      await loadData();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '素材上传失败'));
    } finally {
      setUploadSubmitting(false);
    }
  };

  const handleEdit = async (values: { name: string; category: MaterialCategory; description?: string; tags?: string; review_status?: string }) => {
    if (!editingItem) return;
    setEditSubmitting(true);
    try {
      const payload: Record<string, any> = { ...values };
      if (typeof payload.tags === 'string') {
        payload.tags = payload.tags.split(/[,，]/).map((t: string) => t.trim()).filter(Boolean);
      }
      await materialApi.update(editingItem.id, payload);
      message.success('更新成功');
      setShowEdit(false);
      setEditingItem(null);
      editForm.resetFields();
      await loadData();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '更新失败'));
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await materialApi.delete(id);
      message.success('删除成功');
      await loadData();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '删除失败'));
    } finally {
      setDeletingId(null);
    }
  };

  const handleToggleDisable = async (item: MaterialAsset) => {
    setTogglingId(item.id);
    try {
      if (item.is_disabled) {
        await materialApi.enable(item.id);
        message.success('已启用');
      } else {
        await materialApi.disable(item.id);
        message.success('已停用');
      }
      await loadData();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '操作失败'));
    } finally {
      setTogglingId(null);
    }
  };

  return (
    <div style={{ maxWidth: 1240, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card>
          <Space wrap style={{ width: '100%', justifyContent: 'space-between' }}>
            <Space wrap>
              <Input.Search
                allowClear
                placeholder="搜索素材名称或说明"
                style={{ width: 280 }}
                onSearch={(value) => setKeyword(value)}
              />
              <Select
                allowClear
                placeholder="按分类筛选"
                style={{ width: 220 }}
                options={categoryOptions}
                value={category}
                onChange={(value) => setCategory(value)}
              />
            </Space>
            <Space>
              <Button icon={<ImportOutlined />} onClick={() => setShowIngestion(true)}>
                从历史标书导入
              </Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowUpload(true)}>
                上传素材
              </Button>
            </Space>
          </Space>
        </Card>

        {filteredItems.length ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
            {filteredItems.map((item) => (
              <Card
                key={item.id}
                loading={loading}
                actions={[
                  <Button
                    key="edit"
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => {
                      editForm.setFieldsValue({
                        name: item.name,
                        category: item.category,
                        description: item.description || '',
                        tags: (item.tags || []).join(', '),
                        review_status: item.review_status,
                      });
                      setEditingItem(item);
                      setShowEdit(true);
                    }}
                  >
                    编辑
                  </Button>,
                  <Button
                    key="toggle-disable"
                    type="text"
                    size="small"
                    icon={item.is_disabled ? <CheckCircleOutlined /> : <StopOutlined />}
                    loading={togglingId === item.id}
                    onClick={() => handleToggleDisable(item)}
                  >
                    {item.is_disabled ? '启用' : '停用'}
                  </Button>,
                  <Popconfirm
                    key="delete"
                    title="确定删除该素材吗？"
                    description="删除后无法恢复"
                    onConfirm={() => handleDelete(item.id)}
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      loading={deletingId === item.id}
                    >
                      删除
                    </Button>
                  </Popconfirm>,
                ]}
                cover={
                  item.thumbnail_path || item.preview_path ? (
                    item.file_type === 'pdf' ? (
                      <div
                        style={{ height: 180, overflow: 'hidden', background: '#f8fafc', cursor: 'pointer', position: 'relative' }}
                        onClick={() => setPreviewPdf(getFileUrl(item.file_path))}
                      >
                        <img
                          src={getFileUrl(item.thumbnail_path || item.preview_path || '')}
                          alt={item.name}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.3)', opacity: 0, transition: 'opacity 0.2s' }}
                          onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
                          onMouseLeave={(e) => (e.currentTarget.style.opacity = '0')}
                        >
                          <span style={{ color: '#fff', fontSize: 14, fontWeight: 500 }}>点击预览 PDF</span>
                        </div>
                      </div>
                    ) : (
                      <Image
                        src={getFileUrl(item.thumbnail_path || item.preview_path || '')}
                        alt={item.name}
                        style={{ height: 180, objectFit: 'cover' }}
                        preview={{
                          src: item.preview_path
                            ? getFileUrl(item.preview_path)
                            : undefined,
                        }}
                      />
                    )
                  ) : undefined
                }
              >
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag color="blue">{categoryOptions.find(o => o.value === item.category)?.label || item.category}</Tag>
                    <ExpiryTag item={item} />
                    {item.review_status !== 'confirmed' ? <Tag color="gold">待确认</Tag> : null}
                  </Space>
                  <div style={{ fontWeight: 600 }}>{item.name}</div>
                  <div style={{ color: '#64748b', minHeight: 44 }}>{item.description || '暂无说明'}</div>
                  <Space wrap>
                    {item.tags?.map((tag) => (
                      <Tag key={tag}>{tag}</Tag>
                    ))}
                  </Space>
                </Space>
              </Card>
            ))}
          </div>
        ) : (
          <Card loading={loading}>
            <Empty description="还没有素材，先上传一些营业执照、证书或案例吧" />
          </Card>
        )}
      </Space>

      <Modal
        title="上传素材"
        open={showUpload}
        onCancel={() => setShowUpload(false)}
        onOk={() => form.submit()}
        okText="上传"
        confirmLoading={uploadSubmitting}
      >
        <Form form={form} layout="vertical" onFinish={handleUpload}>
          <Form.Item name="name" label="素材名称" rules={[{ required: true, message: '请输入素材名称' }]}>
            <Input placeholder="如：营业执照副本" />
          </Form.Item>
          <Form.Item name="category" label="素材分类" initialValue="other" rules={[{ required: true, message: '请选择分类' }]}>
            <Select options={categoryOptions} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} placeholder="可补充主体名称、证照编号、用途说明" />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Input placeholder="多个标签请用英文逗号分隔" />
          </Form.Item>
          <Form.Item label="素材文件" required>
            <Upload.Dragger
              accept=".png,.jpg,.jpeg,.pdf"
              beforeUpload={(uploadFile) => {
                setFile(uploadFile);
                return false;
              }}
              maxCount={1}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽上传 PNG / JPG / PDF</p>
            </Upload.Dragger>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="编辑素材"
        open={showEdit}
        onCancel={() => {
          setShowEdit(false);
          setEditingItem(null);
          editForm.resetFields();
        }}
        onOk={() => editForm.submit()}
        okText="保存"
        confirmLoading={editSubmitting}
      >
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>
          <Form.Item name="name" label="素材名称" rules={[{ required: true, message: '请输入素材名称' }]}>
            <Input placeholder="如：营业执照副本" />
          </Form.Item>
          <Form.Item name="category" label="素材分类" rules={[{ required: true, message: '请选择分类' }]}>
            <Select options={categoryOptions} />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input.TextArea rows={3} placeholder="可补充主体名称、证照编号、用途说明" />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Input placeholder="多个标签请用英文逗号分隔" />
          </Form.Item>
          <Form.Item name="review_status" label="确认状态">
            <Select
              options={[
                { label: '待确认', value: 'pending' },
                { label: '已确认', value: 'confirmed' },
                { label: '已拒绝', value: 'rejected' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="PDF 预览"
        open={!!previewPdf}
        onCancel={() => setPreviewPdf(null)}
        footer={null}
        width="80vw"
        style={{ top: 20 }}
        destroyOnClose
      >
        <iframe
          src={previewPdf || ''}
          style={{ width: '100%', height: '75vh', border: 'none' }}
          title="PDF 预览"
        />
      </Modal>

      {/* 从历史标书导入 */}
      <IngestionWizard
        visible={showIngestion}
        onClose={() => setShowIngestion(false)}
        onSuccess={() => {
          loadData();
          setShowIngestion(false);
        }}
      />
    </div>
  );
};

export default MaterialLibrary;
