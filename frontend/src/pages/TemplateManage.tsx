/**
 * 导出模板管理页面  /templates
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Button,
  Card,
  Col,
  Form,
  Modal,
  Popconfirm,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
  message,
  Input,
  Select,
} from 'antd';
import {
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { exportTemplateApi, projectApi, ExportTemplate } from '../services/api';
import type { ProjectSummary } from '../types/project';
import { useLayoutHeader } from '../layouts/layoutHeader';
import TemplateEditForm, {
  templateToFormValues,
  formValuesToPayload,
} from '../components/TemplateEditForm';

const { Title, Text, Paragraph } = Typography;

// ── 小工具：格式配置摘要 ─────────────────────────────────────────
function configSummary(cfg: any): string {
  if (!cfg) return '默认格式';
  const parts: string[] = [];
  if (cfg.font_family) parts.push(`字体：${cfg.font_family}`);
  if (cfg.font_size) parts.push(`字号：${cfg.font_size}pt`);
  if (cfg.line_spacing) parts.push(`行距：${cfg.line_spacing}倍`);
  if (cfg.margin?.left) parts.push(`左边距：${cfg.margin.left}cm`);
  return parts.join('  ·  ') || '默认格式';
}

// ── 模板卡片 ──────────────────────────────────────────────────────
interface TemplateCardProps {
  template: ExportTemplate;
  onEdit: (t: ExportTemplate) => void;
  onCopy: (t: ExportTemplate) => void;
  onDelete: (t: ExportTemplate) => void;
}

const TemplateCard: React.FC<TemplateCardProps> = ({ template, onEdit, onCopy, onDelete }) => (
  <Card
    size="small"
    style={{ height: '100%' }}
    title={
      <Space>
        <Text strong>{template.name}</Text>
        {template.is_builtin && <Tag color="blue">内置</Tag>}
      </Space>
    }
    extra={
      <Space>
        {!template.is_builtin && (
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => onEdit(template)}
          >
            编辑
          </Button>
        )}
        <Button
          type="text"
          size="small"
          icon={<CopyOutlined />}
          onClick={() => onCopy(template)}
        >
          复制
        </Button>
        {!template.is_builtin && (
          <Popconfirm
            title="确认删除此模板？"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => onDelete(template)}
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        )}
      </Space>
    }
  >
    {template.description && (
      <Paragraph type="secondary" ellipsis={{ rows: 1 }} style={{ margin: '0 0 6px' }}>
        {template.description}
      </Paragraph>
    )}
    <Text type="secondary" style={{ fontSize: 12 }}>
      {configSummary(template.format_config)}
    </Text>
  </Card>
);

// ── 主页面 ────────────────────────────────────────────────────────
const TemplateManage: React.FC = () => {
  const { setLayoutHeader } = useLayoutHeader();
  const [templates, setTemplates] = useState<ExportTemplate[]>([]);
  const [loading, setLoading] = useState(false);

  // 编辑 / 新建 modal
  const [editVisible, setEditVisible] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ExportTemplate | null>(null);
  const [editForm] = Form.useForm();
  const [editSubmitting, setEditSubmitting] = useState(false);

  // AI 提取 modal
  const [extractVisible, setExtractVisible] = useState(false);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [extractProjectId, setExtractProjectId] = useState<string | undefined>();
  const [extractText, setExtractText] = useState('');
  const [extracting, setExtracting] = useState(false);

  useEffect(() => {
    setLayoutHeader({
      content: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0' }}>
          <Title level={5} style={{ margin: 0 }}>
            导出模板管理
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            管理 Word/PDF 排版格式模板
          </Text>
        </div>
      ),
    });
    return () => setLayoutHeader(null);
  }, [setLayoutHeader]);

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const list = await exportTemplateApi.list();
      setTemplates(list);
    } catch {
      message.error('加载模板失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTemplates();
  }, [loadTemplates]);

  // ── 打开新建/编辑弹窗 ──────────────────────────────────────────
  const openCreate = () => {
    setEditingTemplate(null);
    editForm.resetFields();
    editForm.setFieldsValue({
      name: '',
      description: '',
      font_family: '仿宋',
      font_size: 12,
      line_spacing: 1.5,
      margin_top: 2.54,
      margin_bottom: 2.54,
      margin_left: 3.17,
      margin_right: 3.17,
      header_text: '',
      footer_text: '',
      show_cover: false,
      show_toc: true,
    });
    setEditVisible(true);
  };

  const openEdit = (t: ExportTemplate) => {
    setEditingTemplate(t);
    editForm.setFieldsValue(templateToFormValues(t));
    setEditVisible(true);
  };

  const openCopy = (t: ExportTemplate) => {
    setEditingTemplate(null);
    const values = templateToFormValues(t);
    editForm.setFieldsValue({ ...values, name: `${values.name}（副本）` });
    setEditVisible(true);
  };

  const handleEditSave = async () => {
    let values: any;
    try {
      values = await editForm.validateFields();
    } catch {
      return;
    }
    setEditSubmitting(true);
    try {
      const payload = formValuesToPayload(values);
      if (editingTemplate) {
        await exportTemplateApi.update(editingTemplate.id, payload);
        message.success('保存成功');
      } else {
        await exportTemplateApi.create(payload);
        message.success('创建成功');
      }
      setEditVisible(false);
      void loadTemplates();
    } catch {
      message.error('保存失败');
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleDelete = async (t: ExportTemplate) => {
    try {
      await exportTemplateApi.delete(t.id);
      message.success('已删除');
      void loadTemplates();
    } catch {
      message.error('删除失败');
    }
  };

  // ── AI 提取 ────────────────────────────────────────────────────
  const openExtract = async () => {
    setExtractVisible(true);
    setExtractProjectId(undefined);
    setExtractText('');
    try {
      const list = await projectApi.list();
      setProjects(list);
    } catch {
      setProjects([]);
    }
  };

  const handleExtract = async () => {
    if (!extractProjectId && !extractText.trim()) {
      message.warning('请选择项目或输入文本');
      return;
    }
    setExtracting(true);
    try {
      const result = await exportTemplateApi.extractFromDocument({
        project_id: extractProjectId || '',
        file_content: extractText || undefined,
      });
      const cfg = result?.format_config || {};
      setExtractVisible(false);
      // 打开新建弹窗并预填提取结果
      setEditingTemplate(null);
      editForm.setFieldsValue({
        name: result?.name || '从文件提取的模板',
        description: result?.description || '',
        font_family: cfg.font_family ?? '仿宋',
        font_size: cfg.font_size ?? 12,
        line_spacing: cfg.line_spacing ?? 1.5,
        margin_top: cfg.margin?.top ?? 2.54,
        margin_bottom: cfg.margin?.bottom ?? 2.54,
        margin_left: cfg.margin?.left ?? 3.17,
        margin_right: cfg.margin?.right ?? 3.17,
        header_text: cfg.header?.text ?? '',
        footer_text: cfg.footer?.text ?? '',
        show_cover: cfg.cover?.enabled ?? false,
        show_toc: cfg.toc?.enabled ?? true,
      });
      setEditVisible(true);
      message.success('AI 提取完成，请确认并保存');
    } catch {
      message.error('提取失败，请重试');
    } finally {
      setExtracting(false);
    }
  };

  // 分组
  const builtinTemplates = templates.filter((t) => t.is_builtin);
  const userTemplates = templates.filter((t) => !t.is_builtin);

  return (
    <div style={{ padding: '24px', maxWidth: 1100, margin: '0 auto' }}>
      {/* 页面标题栏 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 24,
        }}
      >
        <div>
          <Title level={4} style={{ margin: 0 }}>
            导出模板管理
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            管理 Word / PDF 排版格式，可用于导出时选择
          </Text>
        </div>
        <Space>
          <Button icon={<RobotOutlined />} onClick={() => void openExtract()}>
            从招标文件提取
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建模板
          </Button>
        </Space>
      </div>

      <Spin spinning={loading}>
        {/* 内置模板 */}
        <div style={{ marginBottom: 32 }}>
          <Title level={5} style={{ marginBottom: 12 }}>
            内置模板
          </Title>
          {builtinTemplates.length === 0 ? (
            <Text type="secondary">暂无内置模板</Text>
          ) : (
            <Row gutter={[16, 16]}>
              {builtinTemplates.map((t) => (
                <Col key={t.id} xs={24} sm={12} lg={8}>
                  <TemplateCard
                    template={t}
                    onEdit={openEdit}
                    onCopy={openCopy}
                    onDelete={handleDelete}
                  />
                </Col>
              ))}
            </Row>
          )}
        </div>

        {/* 用户自定义模板 */}
        <div>
          <Title level={5} style={{ marginBottom: 12 }}>
            自定义模板
          </Title>
          {userTemplates.length === 0 ? (
            <Text type="secondary">
              暂无自定义模板，点击"新建模板"创建，或"从招标文件提取"自动生成
            </Text>
          ) : (
            <Row gutter={[16, 16]}>
              {userTemplates.map((t) => (
                <Col key={t.id} xs={24} sm={12} lg={8}>
                  <TemplateCard
                    template={t}
                    onEdit={openEdit}
                    onCopy={openCopy}
                    onDelete={handleDelete}
                  />
                </Col>
              ))}
            </Row>
          )}
        </div>
      </Spin>

      {/* 新建/编辑 Modal */}
      <Modal
        title={editingTemplate ? '编辑模板' : '新建模板'}
        open={editVisible}
        onCancel={() => setEditVisible(false)}
        onOk={() => void handleEditSave()}
        okText="保存"
        cancelText="取消"
        confirmLoading={editSubmitting}
        width={600}
        destroyOnClose
      >
        <TemplateEditForm
          form={editForm}
          readOnly={editingTemplate?.is_builtin ?? false}
        />
      </Modal>

      {/* AI 提取 Modal */}
      <Modal
        title="从招标文件提取格式"
        open={extractVisible}
        onCancel={() => setExtractVisible(false)}
        onOk={() => void handleExtract()}
        okText="提取"
        cancelText="取消"
        confirmLoading={extracting}
        width={520}
        destroyOnClose
      >
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <div>
            <Text strong>选择项目（可选）</Text>
            <Select
              style={{ width: '100%', marginTop: 6 }}
              placeholder="选择已上传招标文件的项目"
              allowClear
              value={extractProjectId}
              onChange={setExtractProjectId}
              options={projects.map((p) => ({ label: p.name, value: p.id }))}
            />
          </div>
          <div>
            <Text strong>或直接粘贴文本（可选）</Text>
            <Input.TextArea
              rows={5}
              placeholder="将招标文件中的格式要求粘贴到这里，AI 将自动提取排版配置"
              value={extractText}
              onChange={(e) => setExtractText(e.target.value)}
              style={{ marginTop: 6 }}
            />
          </div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            AI 将自动分析文件格式要求，提取字体、行距、页边距等配置，生成模板初稿供您确认。
          </Text>
        </Space>
      </Modal>
    </div>
  );
};

export default TemplateManage;
