import React, { useState, useEffect } from 'react';
import { Modal, Steps, Button, Table, Tag, message, Spin, Empty, Checkbox } from 'antd';
import { UploadOutlined, FileTextOutlined, CheckCircleOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import api from '../services/api';

interface Props {
  visible: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface KnowledgeDoc {
  id: string;
  title: string;
  doc_type: string;
  created_at: string;
}

interface MaterialCandidate {
  id: string;
  category: string;
  name: string;
  source_page_from: number | null;
  source_page_to: number | null;
  source_excerpt: string | null;
  preview_path: string | null;
  thumbnail_path: string | null;
  confidence_score: number | null;
  ai_extracted_fields: Record<string, string> | null;
  review_status: string;
}

interface IngestionTask {
  id: string;
  document_id: string;
  status: string;
  total_candidates: number;
  confirmed_count: number;
  rejected_count: number;
  created_at: string;
}

const categoryLabels: Record<string, { label: string; color: string }> = {
  business_license: { label: '营业执照', color: 'blue' },
  legal_person_id: { label: '法人身份', color: 'magenta' },
  qualification_cert: { label: '资质证书', color: 'green' },
  award_cert: { label: '获奖证书', color: 'gold' },
  iso_cert: { label: 'ISO认证', color: 'purple' },
  contract_sample: { label: '合同', color: 'orange' },
  project_case: { label: '项目案例', color: 'cyan' },
  team_photo: { label: '团队照片', color: 'geekblue' },
  equipment_photo: { label: '设备照片', color: 'lime' },
  financial_report: { label: '财务报告', color: 'red' },
  bank_credit: { label: '银行资信', color: 'volcano' },
  social_security: { label: '社保证明', color: 'blue' },
  other: { label: '其他', color: 'default' },
};

const IngestionWizard: React.FC<Props> = ({ visible, onClose, onSuccess }) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [documents, setDocuments] = useState<KnowledgeDoc[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [task, setTask] = useState<IngestionTask | null>(null);
  const [candidates, setCandidates] = useState<MaterialCandidate[]>([]);
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  // 加载知识库文档
  useEffect(() => {
    if (visible && currentStep === 0) {
      loadDocuments();
    }
  }, [visible, currentStep]);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/knowledge/docs', {
        params: { doc_type: 'history_bid' }
      });
      setDocuments(response.data.items || []);
    } catch (error) {
      message.error('加载文档失败');
    } finally {
      setLoading(false);
    }
  };

  // 创建任务并开始解析
  const handleStartIngestion = async () => {
    if (!selectedDocId) {
      message.warning('请选择要解析的文档');
      return;
    }

      setLoading(true);
      setCurrentStep(1); // 进入解析中步骤
      try {
        // 1. 创建任务
        const createResponse = await api.post('/api/ingestion/tasks', {
          document_id: selectedDocId,
        });
        const newTaskId = createResponse.data.id;
        setTaskId(newTaskId);
        setTask(createResponse.data);

        // 2. 执行解析
        message.loading({ content: '正在解析文档...', key: 'parsing' });
        const processResponse = await api.post(`/api/ingestion/tasks/${newTaskId}/process`);
        setCandidates(processResponse.data);
        message.success({ content: '解析完成', key: 'parsing' });

        setCurrentStep(2); // 解析完成，进入审核确认步骤
      } catch (error: unknown) {
        const detail = (error as any)?.response?.data?.detail;
        message.error(detail || '解析失败');
        setCurrentStep(0); // 解析失败，回到选择文档步骤
      } finally {
        setLoading(false);
      }
  };

  // 确认入库
  const handleConfirm = async () => {
    if (selectedCandidateIds.size === 0) {
      message.warning('请至少选择一个候选素材');
      return;
    }

    setLoading(true);
    try {
      const allIds = new Set(candidates.map(c => c.id));
      const confirmIds = Array.from(selectedCandidateIds);
      const rejectIds = Array.from(allIds).filter(id => !selectedCandidateIds.has(id));

      await api.post(`/api/ingestion/tasks/${taskId}/confirm`, {
        confirm_ids: confirmIds,
        reject_ids: rejectIds,
      });

      message.success(`已确认 ${confirmIds.length} 个素材入库`);
      setCurrentStep(3);
      onSuccess();
    } catch (error: unknown) {
      const detail = (error as any)?.response?.data?.detail;
      message.error(detail || '确认失败');
    } finally {
      setLoading(false);
    }
  };

  // 关闭并重置
  const handleClose = () => {
    setCurrentStep(0);
    setSelectedDocId(null);
    setTaskId(null);
    setTask(null);
    setCandidates([]);
    setSelectedCandidateIds(new Set());
    onClose();
  };

  // 候选素材表格列
  const candidateColumns: ColumnsType<MaterialCandidate> = [
    {
      title: '选择',
      key: 'select',
      width: 60,
      render: (_, record) => (
        <Checkbox
          checked={selectedCandidateIds.has(record.id)}
          onChange={(e) => {
            const newSet = new Set(selectedCandidateIds);
            if (e.target.checked) {
              newSet.add(record.id);
            } else {
              newSet.delete(record.id);
            }
            setSelectedCandidateIds(newSet);
          }}
        />
      ),
    },
    {
      title: '类型',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (category: string) => {
        const config = categoryLabels[category] || categoryLabels.other;
        return <Tag color={config.color}>{config.label}</Tag>;
      },
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '页码',
      key: 'pages',
      width: 100,
      render: (_, record) => {
        if (record.source_page_from && record.source_page_to) {
          return record.source_page_from === record.source_page_to
            ? `第${record.source_page_from}页`
            : `第${record.source_page_from}-${record.source_page_to}页`;
        }
        return '-';
      },
    },
    {
      title: '置信度',
      dataIndex: 'confidence_score',
      key: 'confidence',
      width: 100,
      render: (score: number | null) => {
        if (!score) return '-';
        const percent = Math.round(score * 100);
        const color = percent >= 80 ? 'green' : percent >= 60 ? 'orange' : 'red';
        return <Tag color={color}>{percent}%</Tag>;
      },
    },
    {
      title: '提取字段',
      key: 'fields',
      ellipsis: true,
      render: (_, record) => {
        if (!record.ai_extracted_fields) return '-';
        const fields = Object.entries(record.ai_extracted_fields)
          .slice(0, 2)
          .map(([key, value]) => `${key}: ${value}`)
          .join('; ');
        return <span style={{ fontSize: 12, color: '#666' }}>{fields}</span>;
      },
    },
  ];

  const steps = [
    {
      title: '选择文档',
      icon: <FileTextOutlined />,
      content: (
        <div>
          <p style={{ marginBottom: 16, color: '#666' }}>
            从知识库中选择历史标书文档进行解析
          </p>
          <Spin spinning={loading}>
            {documents.length === 0 ? (
              <Empty description="暂无历史标书文档，请先上传" />
            ) : (
              <div style={{ maxHeight: 400, overflow: 'auto' }}>
                {documents.map(doc => (
                  <div
                    key={doc.id}
                    onClick={() => setSelectedDocId(doc.id)}
                    style={{
                      padding: 12,
                      marginBottom: 8,
                      border: `1px solid ${selectedDocId === doc.id ? '#1890ff' : '#d9d9d9'}`,
                      borderRadius: 4,
                      cursor: 'pointer',
                      background: selectedDocId === doc.id ? '#e6f7ff' : '#fff',
                    }}
                  >
                    <div style={{ fontWeight: 500 }}>{doc.title}</div>
                    <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                      上传时间: {new Date(doc.created_at).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Spin>
        </div>
      ),
    },
    {
      title: '解析处理',
      icon: <UploadOutlined />,
      content: (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
          <p style={{ marginTop: 16, color: '#666' }}>正在解析文档，提取可复用素材...</p>
        </div>
      ),
    },
    {
      title: '审核确认',
      icon: <CheckCircleOutlined />,
      content: (
        <div>
          <div style={{ marginBottom: 16 }}>
            <span>共提取 </span>
            <Tag color="blue">{candidates.length}</Tag>
            <span> 个候选素材，已选择 </span>
            <Tag color="green">{selectedCandidateIds.size}</Tag>
            <span> 个</span>
            <Button
              size="small"
              style={{ marginLeft: 12 }}
              onClick={() => setSelectedCandidateIds(new Set(candidates.map(c => c.id)))}
            >
              全选
            </Button>
            <Button
              size="small"
              style={{ marginLeft: 8 }}
              onClick={() => setSelectedCandidateIds(new Set())}
            >
              清空
            </Button>
          </div>
          <Table
            columns={candidateColumns}
            dataSource={candidates}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            scroll={{ x: 800 }}
          />
        </div>
      ),
    },
    {
      title: '完成',
      icon: <CheckCircleOutlined />,
      content: (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <CheckCircleOutlined style={{ fontSize: 64, color: '#52c41a' }} />
          <h3 style={{ marginTop: 16 }}>素材入库成功</h3>
          <p style={{ color: '#666' }}>
            已确认 {selectedCandidateIds.size} 个素材进入素材库，可在素材管理中查看和使用
          </p>
        </div>
      ),
    },
  ];

  return (
    <Modal
      title="从历史标书导入素材"
      open={visible}
      onCancel={handleClose}
      width={900}
      footer={
        currentStep < 3 ? (
          <div style={{ textAlign: 'right' }}>
            {currentStep > 0 && currentStep < 3 && (
              <Button style={{ marginRight: 8 }} onClick={() => setCurrentStep(currentStep - 1)}>
                上一步
              </Button>
            )}
            {currentStep === 0 && (
              <Button type="primary" onClick={handleStartIngestion} loading={loading}>
                开始解析
              </Button>
            )}
            {currentStep === 2 && (
              <Button type="primary" onClick={handleConfirm} loading={loading}>
                确认入库
              </Button>
            )}
            {currentStep === 3 && (
              <Button type="primary" onClick={handleClose}>
                完成
              </Button>
            )}
          </div>
        ) : null
      }
    >
      <Steps current={currentStep} items={steps.map(s => ({ title: s.title, icon: s.icon }))} />
      <div style={{ marginTop: 24, minHeight: 300 }}>{steps[currentStep].content}</div>
    </Modal>
  );
};

export default IngestionWizard;
