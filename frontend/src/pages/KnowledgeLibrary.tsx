/**
 * 标书知识库 - 章节模板管理页面
 */
import React, { useState, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Button,
  Space,
  Input,
  Select,
  Tag,
  Typography,
  Modal,
  Form,
  message,
  Spin,
  Empty,
  Tooltip,
  Card,
  Row,
  Col,
  Divider,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  CopyOutlined,
  BookOutlined,
  ProjectOutlined,
  TagOutlined,
} from '@ant-design/icons';
import { chapterTemplateApi, ChapterTemplate } from '../services/api';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const CATEGORIES = [
  '技术方案',
  '项目经验',
  '团队配置',
  '质量保障',
  '安全方案',
  '服务方案',
  '投标报价',
  '其他',
];

const CATEGORY_COLORS: Record<string, string> = {
  技术方案: 'blue',
  项目经验: 'green',
  团队配置: 'purple',
  质量保障: 'orange',
  安全方案: 'red',
  服务方案: 'cyan',
  投标报价: 'gold',
  其他: 'default',
};

const KnowledgeLibrary: React.FC = () => {
  const [templates, setTemplates] = useState<ChapterTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [category, setCategory] = useState<string | undefined>();

  // 新建/编辑弹窗
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ChapterTemplate | null>(null);
  const [editForm] = Form.useForm();
  const [editLoading, setEditLoading] = useState(false);

  // 预览弹窗
  const [previewTemplate, setPreviewTemplate] = useState<ChapterTemplate | null>(null);
  const [previewVisible, setPreviewVisible] = useState(false);

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const data = await chapterTemplateApi.list({
        category: category || undefined,
        keyword: keyword || undefined,
      });
      setTemplates(data);
    } catch (error: unknown) {
      const detail = (error as any)?.message;
      message.error(detail || '加载章节模板失败');
    } finally {
      setLoading(false);
    }
  }, [category, keyword]);

  useEffect(() => {
    void loadTemplates();
  }, [loadTemplates]);

  const handleSearch = () => {
    void loadTemplates();
  };

  const handleOpenCreate = () => {
    setEditingTemplate(null);
    editForm.resetFields();
    setEditModalVisible(true);
  };

  const handleOpenEdit = (tpl: ChapterTemplate) => {
    setEditingTemplate(tpl);
    editForm.setFieldsValue({
      name: tpl.name,
      description: tpl.description || '',
      category: tpl.category || undefined,
      tags: tpl.tags || [],
      content: tpl.content,
    });
    setEditModalVisible(true);
  };

  const handleSaveTemplate = async () => {
    try {
      const values = await editForm.validateFields();
      setEditLoading(true);

      if (editingTemplate) {
        await chapterTemplateApi.update(editingTemplate.id, values);
        message.success('模板已更新');
      } else {
        await chapterTemplateApi.create(values);
        message.success('模板已创建');
      }

      setEditModalVisible(false);
      editForm.resetFields();
      setEditingTemplate(null);
      await loadTemplates();
    } catch (error: unknown) {
      if ((error as any)?.errorFields) return; // form validation
      const detail = (error as any)?.message;
      message.error(detail || '保存模板失败');
    } finally {
      setEditLoading(false);
    }
  };

  const handleDelete = async (tpl: ChapterTemplate) => {
    try {
      await chapterTemplateApi.delete(tpl.id);
      message.success('模板已删除');
      await loadTemplates();
    } catch (error: unknown) {
      const detail = (error as any)?.message;
      message.error(detail || '删除模板失败');
    }
  };

  const handleCopy = async (tpl: ChapterTemplate) => {
    try {
      await navigator.clipboard.writeText(tpl.content);
      message.success('内容已复制到剪贴板');
    } catch {
      message.error('复制失败，请手动复制');
    }
  };

  const handlePreview = (tpl: ChapterTemplate) => {
    setPreviewTemplate(tpl);
    setPreviewVisible(true);
  };

  return (
    <div style={{ padding: '24px', maxWidth: 1200, margin: '0 auto' }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: 24 }}>
        <Space align="center">
          <BookOutlined style={{ fontSize: 24, color: '#1677ff' }} />
          <Title level={4} style={{ margin: 0 }}>
            标书知识库
          </Title>
        </Space>
        <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
          保存并复用中标章节模板，提升标书撰写效率
        </Text>
      </div>

      {/* 搜索栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Space wrap size={[12, 8]} style={{ width: '100%' }}>
          <Input
            placeholder="搜索模板名称或描述"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 280 }}
            allowClear
          />
          <Select
            placeholder="按分类筛选"
            value={category}
            onChange={(val) => setCategory(val)}
            allowClear
            style={{ width: 160 }}
          >
            {CATEGORIES.map((c) => (
              <Option key={c} value={c}>
                {c}
              </Option>
            ))}
          </Select>
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>
          <div style={{ flex: 1 }} />
          <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenCreate}>
            新建模板
          </Button>
        </Space>
      </Card>

      {/* 模板列表 */}
      <Spin spinning={loading}>
        {templates.length === 0 && !loading ? (
          <Card>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span>
                  {keyword || category ? '未找到匹配的模板' : '暂无章节模板'}
                  {!keyword && !category && (
                    <span>，点击「新建模板」开始创建</span>
                  )}
                </span>
              }
            >
              {!keyword && !category && (
                <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenCreate}>
                  新建模板
                </Button>
              )}
            </Empty>
          </Card>
        ) : (
          <Row gutter={[16, 16]}>
            {templates.map((tpl) => (
              <Col key={tpl.id} xs={24} sm={24} md={12} lg={8}>
                <Card
                  hoverable
                  style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
                  styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column' } }}
                  actions={[
                    <Tooltip title="预览内容" key="preview">
                      <Button
                        type="text"
                        icon={<EyeOutlined />}
                        onClick={() => handlePreview(tpl)}
                      >
                        预览
                      </Button>
                    </Tooltip>,
                    <Tooltip title="编辑" key="edit">
                      <Button
                        type="text"
                        icon={<EditOutlined />}
                        onClick={() => handleOpenEdit(tpl)}
                      >
                        编辑
                      </Button>
                    </Tooltip>,
                    <Tooltip title="复制内容" key="copy">
                      <Button
                        type="text"
                        icon={<CopyOutlined />}
                        onClick={() => void handleCopy(tpl)}
                      >
                        复制
                      </Button>
                    </Tooltip>,
                    <Popconfirm
                      key="delete"
                      title="确定删除该模板？"
                      description="删除后不可恢复"
                      onConfirm={() => void handleDelete(tpl)}
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true }}
                    >
                      <Tooltip title="删除">
                        <Button type="text" danger icon={<DeleteOutlined />}>
                          删除
                        </Button>
                      </Tooltip>
                    </Popconfirm>,
                  ]}
                >
                  <div style={{ flex: 1 }}>
                    {/* 标题行 */}
                    <div
                      style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 8, gap: 8 }}
                    >
                      <Text strong style={{ fontSize: 15, flex: 1 }}>
                        {tpl.name}
                      </Text>
                    </div>

                    {/* 分类标签 */}
                    <Space wrap size={[4, 4]} style={{ marginBottom: 8 }}>
                      {tpl.category && (
                        <Tag color={CATEGORY_COLORS[tpl.category] || 'default'}>
                          {tpl.category}
                        </Tag>
                      )}
                      {tpl.tags.slice(0, 3).map((tag) => (
                        <Tag key={tag} icon={<TagOutlined />} color="processing">
                          {tag}
                        </Tag>
                      ))}
                      {tpl.tags.length > 3 && (
                        <Tag color="default">+{tpl.tags.length - 3}</Tag>
                      )}
                    </Space>

                    {/* 描述 */}
                    {tpl.description && (
                      <Text
                        type="secondary"
                        style={{ display: 'block', fontSize: 13, marginBottom: 8 }}
                        ellipsis={{ tooltip: tpl.description }}
                      >
                        {tpl.description}
                      </Text>
                    )}

                    {/* 来源项目 */}
                    {tpl.source_project_name && (
                      <div style={{ marginBottom: 8 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          <ProjectOutlined style={{ marginRight: 4 }} />
                          来源：{tpl.source_project_name}
                        </Text>
                      </div>
                    )}

                    <Divider style={{ margin: '8px 0' }} />

                    {/* 统计信息 */}
                    <Space split={<Divider type="vertical" />}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        已使用 {tpl.usage_count} 次
                      </Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {new Date(tpl.created_at).toLocaleDateString()}
                      </Text>
                    </Space>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Spin>

      {/* 新建/编辑弹窗 */}
      <Modal
        title={editingTemplate ? '编辑模板' : '新建章节模板'}
        open={editModalVisible}
        onOk={() => void handleSaveTemplate()}
        onCancel={() => {
          setEditModalVisible(false);
          setEditingTemplate(null);
          editForm.resetFields();
        }}
        okText={editingTemplate ? '保存' : '创建'}
        cancelText="取消"
        confirmLoading={editLoading}
        width={720}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item
            name="name"
            label="模板名称"
            rules={[{ required: true, message: '请输入模板名称' }]}
          >
            <Input placeholder="如：安全方案-中标版" maxLength={200} showCount />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="category" label="分类">
                <Select placeholder="选择分类" allowClear>
                  {CATEGORIES.map((c) => (
                    <Option key={c} value={c}>
                      {c}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="tags" label="标签">
                <Select
                  mode="tags"
                  placeholder="输入标签后按 Enter"
                  style={{ width: '100%' }}
                  tokenSeparators={[',']}
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="description" label="描述">
            <Input placeholder="简要描述此模板的用途和特点" maxLength={300} />
          </Form.Item>

          <Form.Item
            name="content"
            label="章节内容（Markdown）"
            rules={[{ required: true, message: '请输入章节内容' }]}
          >
            <TextArea
              placeholder="输入章节内容，支持 Markdown 格式"
              rows={12}
              style={{ fontFamily: 'monospace', fontSize: 13 }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 内容预览弹窗 */}
      <Modal
        title={
          <Space>
            <EyeOutlined />
            <span>{previewTemplate?.name}</span>
            {previewTemplate?.category && (
              <Tag color={CATEGORY_COLORS[previewTemplate.category] || 'default'}>
                {previewTemplate.category}
              </Tag>
            )}
          </Space>
        }
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={[
          <Button
            key="copy"
            icon={<CopyOutlined />}
            onClick={() => {
              if (previewTemplate) void handleCopy(previewTemplate);
            }}
          >
            复制内容
          </Button>,
          <Button key="close" onClick={() => setPreviewVisible(false)}>
            关闭
          </Button>,
        ]}
        width={800}
      >
        {previewTemplate && (
          <div>
            {previewTemplate.source_project_name && (
              <div style={{ marginBottom: 12 }}>
                <Text type="secondary" style={{ fontSize: 13 }}>
                  <ProjectOutlined style={{ marginRight: 6 }} />
                  来源项目：{previewTemplate.source_project_name}
                </Text>
              </div>
            )}
            {previewTemplate.tags.length > 0 && (
              <Space wrap style={{ marginBottom: 12 }}>
                {previewTemplate.tags.map((tag) => (
                  <Tag key={tag} icon={<TagOutlined />} color="processing">
                    {tag}
                  </Tag>
                ))}
              </Space>
            )}
            <Divider style={{ margin: '12px 0' }} />
            <div
              className="markdown-body"
              style={{ maxHeight: '60vh', overflowY: 'auto', fontSize: 14 }}
            >
              <ReactMarkdown>{previewTemplate.content}</ReactMarkdown>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default KnowledgeLibrary;
