/**
 * 导出模板编辑表单
 * 可作为 Modal 内容使用，也可独立嵌入页面。
 */
import React from 'react';
import {
  Form,
  Input,
  InputNumber,
  Collapse,
  Space,
  Switch,
  Select,
  Typography,
} from 'antd';
import type { ExportTemplate } from '../services/api';

const { Text } = Typography;

export interface TemplateFormValues {
  name: string;
  description?: string;
  font_family?: string;
  font_size?: number;
  line_spacing?: number;
  margin_top?: number;
  margin_bottom?: number;
  margin_left?: number;
  margin_right?: number;
  header_text?: string;
  footer_text?: string;
  show_cover?: boolean;
  show_toc?: boolean;
}

/** 将 ExportTemplate 的 format_config 铺平为表单值 */
export function templateToFormValues(template: ExportTemplate): TemplateFormValues {
  const cfg = template.format_config || {};
  return {
    name: template.name,
    description: template.description ?? '',
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
  };
}

/** 将表单值转换为 API payload */
export function formValuesToPayload(values: TemplateFormValues) {
  return {
    name: values.name,
    description: values.description ?? '',
    format_config: {
      font_family: values.font_family,
      font_size: values.font_size,
      line_spacing: values.line_spacing,
      margin: {
        top: values.margin_top,
        bottom: values.margin_bottom,
        left: values.margin_left,
        right: values.margin_right,
      },
      header: { text: values.header_text ?? '' },
      footer: { text: values.footer_text ?? '' },
      cover: { enabled: values.show_cover ?? false },
      toc: { enabled: values.show_toc ?? true },
    },
  };
}

const fontOptions = [
  { label: '仿宋', value: '仿宋' },
  { label: '宋体', value: '宋体' },
  { label: '黑体', value: '黑体' },
  { label: '楷体', value: '楷体' },
  { label: 'Times New Roman', value: 'Times New Roman' },
  { label: 'Arial', value: 'Arial' },
];

interface TemplateEditFormProps {
  form: ReturnType<typeof Form.useForm>[0];
  readOnly?: boolean;
}

const TemplateEditForm: React.FC<TemplateEditFormProps> = ({ form, readOnly = false }) => {
  const collapseItems = [
    {
      key: 'basic',
      label: '基本信息',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={0}>
          <Form.Item
            label="模板名称"
            name="name"
            rules={[{ required: true, message: '请输入模板名称' }]}
          >
            <Input placeholder="如：GB/T 9704 标准" disabled={readOnly} />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={2} placeholder="可选描述" disabled={readOnly} />
          </Form.Item>
        </Space>
      ),
    },
    {
      key: 'font',
      label: '字体设置',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={0}>
          <Form.Item label="正文字体" name="font_family">
            <Select options={fontOptions} disabled={readOnly} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item label="正文字号（pt）" name="font_size">
            <InputNumber min={8} max={36} disabled={readOnly} />
          </Form.Item>
          <Form.Item label="行间距（倍）" name="line_spacing">
            <InputNumber min={1} max={3} step={0.25} disabled={readOnly} />
          </Form.Item>
        </Space>
      ),
    },
    {
      key: 'margin',
      label: '页边距（cm）',
      children: (
        <Space wrap size={16}>
          <Form.Item label="上边距" name="margin_top">
            <InputNumber min={0} max={10} step={0.1} disabled={readOnly} />
          </Form.Item>
          <Form.Item label="下边距" name="margin_bottom">
            <InputNumber min={0} max={10} step={0.1} disabled={readOnly} />
          </Form.Item>
          <Form.Item label="左边距" name="margin_left">
            <InputNumber min={0} max={10} step={0.1} disabled={readOnly} />
          </Form.Item>
          <Form.Item label="右边距" name="margin_right">
            <InputNumber min={0} max={10} step={0.1} disabled={readOnly} />
          </Form.Item>
        </Space>
      ),
    },
    {
      key: 'header_footer',
      label: '页眉页脚',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={0}>
          <Form.Item label="页眉文字" name="header_text">
            <Input placeholder="留空则不显示页眉" disabled={readOnly} />
          </Form.Item>
          <Form.Item label="页脚文字" name="footer_text">
            <Input placeholder="支持 {page}（页码）变量" disabled={readOnly} />
          </Form.Item>
        </Space>
      ),
    },
    {
      key: 'structure',
      label: '封面与目录',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size={0}>
          <Form.Item label="生成封面" name="show_cover" valuePropName="checked">
            <Switch disabled={readOnly} />
          </Form.Item>
          <Form.Item label="生成目录" name="show_toc" valuePropName="checked">
            <Switch disabled={readOnly} />
          </Form.Item>
        </Space>
      ),
    },
  ];

  return (
    <Form form={form} layout="vertical" size="middle">
      <Collapse
        defaultActiveKey={['basic', 'font']}
        items={collapseItems}
        bordered={false}
        style={{ background: 'transparent' }}
      />
      {readOnly && (
        <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
          内置模板只读，请复制后修改。
        </Text>
      )}
    </Form>
  );
};

export default TemplateEditForm;
