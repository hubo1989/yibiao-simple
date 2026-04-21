/**
 * 导出文档弹窗 — 选择模板 + 导出格式 + 废标校验 + 一致性校验警告
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Modal, Select, Radio, Button, Space, Typography, Spin, Image, message, Divider, Alert, List } from 'antd';
import { DownloadOutlined, EyeOutlined, PlusOutlined, ThunderboltOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { saveAs } from 'file-saver';
import { documentApi, exportTemplateApi, disqualificationApi, ExportTemplate, DisqualificationItem } from '../services/api';
import type { ConsistencyCheckResult } from '../services/api';
import type { OutlineItem } from '../types';

const { Text } = Typography;

interface ExportDialogProps {
  visible: boolean;
  onClose: () => void;
  projectName: string;
  projectOverview?: string;
  projectId?: string;
  /** 用于构建导出 outline（含最新内容） */
  getExportOutline: () => OutlineItem[];
}

type ExportFormat = 'word' | 'pdf';

const ExportDialog: React.FC<ExportDialogProps> = ({
  visible,
  onClose,
  projectName,
  projectOverview,
  projectId,
  getExportOutline,
}) => {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<ExportTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | undefined>(undefined);
  const [format, setFormat] = useState<ExportFormat>('word');
  const [exporting, setExporting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  // 废标校验状态
  const [validating, setValidating] = useState(false);
  const [riskItems, setRiskItems] = useState<DisqualificationItem[] | null>(null);
  const [showRiskWarning, setShowRiskWarning] = useState(false);

  const loadTemplates = useCallback(async () => {
    setLoadingTemplates(true);
    try {
      const list = await exportTemplateApi.list();
      setTemplates(list);
      // 默认选第一个内置模板
      if (!selectedTemplateId && list.length > 0) {
        const builtin = list.find((t) => t.is_builtin);
        setSelectedTemplateId(builtin?.id ?? list[0].id);
      }
    } catch {
      // 后端未实现时静默降级：列表为空，不阻塞导出
      setTemplates([]);
    } finally {
      setLoadingTemplates(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (visible) {
      void loadTemplates();
      setPreviewUrl(null);
      setRiskItems(null);
      setShowRiskWarning(false);
    }
  }, [visible, loadTemplates]);

  const buildPayload = () => ({
    project_name: projectName || '标书文档',
    project_overview: projectOverview,
    project_id: projectId,
    outline: getExportOutline(),
    ...(selectedTemplateId ? { template_id: selectedTemplateId } : {}),
  });

  const doExport = async () => {
    setExporting(true);
    try {
      if (format === 'word') {
        const response = await documentApi.exportWord(buildPayload());
        saveAs(response.data as Blob, `${projectName || '标书文档'}.docx`);
      } else {
        const response = await documentApi.exportPdf(buildPayload());
        saveAs(response.data as Blob, `${projectName || '标书文档'}.pdf`);
      }
      message.success('导出成功');
      onClose();
    } catch {
      message.error('导出失败，请重试');
    } finally {
      setExporting(false);
    }
  };

  const handleExport = async () => {
    // 如果有 projectId，先做废标校验
    if (projectId) {
      setValidating(true);
      try {
        const result = await disqualificationApi.validateBeforeExport(projectId);
        if (result.has_risk) {
          setRiskItems(result.fatal_unresolved_items);
          setShowRiskWarning(true);
          return; // 先展示警告，由用户决定是否继续
        }
      } catch {
        // 校验失败静默跳过，不阻塞导出
      } finally {
        setValidating(false);
      }
    }
    await doExport();
  };

  const handlePreview = async () => {
    setPreviewing(true);
    setPreviewUrl(null);
    try {
      const response = await exportTemplateApi.preview(buildPayload());
      const blob = response.data as Blob;
      const url = URL.createObjectURL(blob);
      setPreviewUrl(url);
    } catch {
      message.warning('预览接口暂未就绪，请直接导出查看效果');
    } finally {
      setPreviewing(false);
    }
  };

  // 模板 Select 选项
  const templateOptions = templates.map((t) => ({
    value: t.id,
    label: (
      <Space size={4}>
        <span>{t.name}</span>
        {t.is_builtin && (
          <Text type="secondary" style={{ fontSize: 11 }}>
            内置
          </Text>
        )}
      </Space>
    ),
  }));

  const dropdownRender = (menu: React.ReactElement) => (
    <>
      {menu}
      <Divider style={{ margin: '4px 0' }} />
      <Button
        type="link"
        icon={<PlusOutlined />}
        size="small"
        style={{ padding: '4px 12px', width: '100%', textAlign: 'left' }}
        onClick={() => {
          onClose();
          navigate('/templates');
        }}
      >
        新建模板...
      </Button>
    </>
  );

  return (
    <Modal
      title="导出文档"
      open={visible}
      onCancel={onClose}
      width={480}
      centered
      destroyOnClose
      footer={
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Button
            icon={<EyeOutlined />}
            onClick={() => void handlePreview()}
            loading={previewing}
            disabled={exporting}
          >
            预览排版
          </Button>
          <Space>
            <Button onClick={onClose} disabled={exporting}>
              取消
            </Button>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={() => void handleExport()}
              loading={exporting || validating}
            >
              {validating ? '校验中...' : '导出'}
            </Button>
          </Space>
        </Space>
      }
    >
      <Space direction="vertical" size={20} style={{ width: '100%', padding: '8px 0' }}>
        {/* 格式模板 */}
        <div>
          <div style={{ marginBottom: 6 }}>
            <Text strong>格式模板</Text>
          </div>
          {loadingTemplates ? (
            <Spin size="small" />
          ) : (
            <Select
              style={{ width: '100%' }}
              placeholder={templates.length === 0 ? '（默认格式）' : '请选择模板'}
              value={selectedTemplateId}
              onChange={setSelectedTemplateId}
              options={templateOptions}
              dropdownRender={dropdownRender}
              allowClear
              notFoundContent={
                <div style={{ padding: '8px 0', textAlign: 'center' }}>
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    暂无模板，
                    <Button
                      type="link"
                      size="small"
                      style={{ padding: 0 }}
                      onClick={() => { onClose(); navigate('/templates'); }}
                    >
                      去新建
                    </Button>
                  </Text>
                </div>
              }
            />
          )}
        </div>

        {/* 导出格式 */}
        <div>
          <div style={{ marginBottom: 6 }}>
            <Text strong>导出格式</Text>
          </div>
          <Radio.Group value={format} onChange={(e) => setFormat(e.target.value as ExportFormat)}>
            <Radio value="word">Word (.docx)</Radio>
            <Radio value="pdf">PDF</Radio>
          </Radio.Group>
        </div>

        {/* 废标风险警告 */}
        {showRiskWarning && riskItems && riskItems.length > 0 && (
          <div>
            <Alert
              type="error"
              showIcon
              icon={<ThunderboltOutlined />}
              message={`发现 ${riskItems.length} 项废标风险（fatal 级别未通过）`}
              description={
                <div>
                  <div style={{ marginBottom: 6, fontSize: 12, color: '#64748b' }}>
                    以下检查项未通过，继续导出可能导致废标风险：
                  </div>
                  <List
                    size="small"
                    dataSource={riskItems.slice(0, 5)}
                    renderItem={(item) => (
                      <List.Item style={{ padding: '4px 0' }}>
                        <span style={{ fontSize: 12, color: '#ef4444' }}>
                          [{item.item_id}] {item.requirement}
                        </span>
                      </List.Item>
                    )}
                  />
                  {riskItems.length > 5 && (
                    <div style={{ fontSize: 12, color: '#94a3b8' }}>
                      ...还有 {riskItems.length - 5} 项，请在废标检查面板中查看
                    </div>
                  )}
                  <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
                    <Button
                      size="small"
                      danger
                      onClick={() => void doExport()}
                      loading={exporting}
                    >
                      忽略风险，强制导出
                    </Button>
                    <Button size="small" onClick={() => setShowRiskWarning(false)}>
                      取消，返回检查
                    </Button>
                  </div>
                </div>
              }
              style={{ marginTop: 4 }}
            />
          </div>
        )}

        {/* 预览图 */}
        {(previewing || previewUrl) && (
          <div
            style={{
              border: '1px solid #e5e7eb',
              borderRadius: 8,
              overflow: 'hidden',
              textAlign: 'center',
              background: '#f9fafb',
              minHeight: 120,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {previewing ? (
              <Spin tip="生成预览中..." />
            ) : previewUrl ? (
              <Image
                src={previewUrl}
                alt="排版预览"
                style={{ maxWidth: '100%' }}
                preview={false}
              />
            ) : null}
          </div>
        )}
      </Space>
    </Modal>
  );
};

export default ExportDialog;
