import React, { useState } from 'react';
import { Modal, Checkbox, Tag, Space, Typography, Empty, Spin, Badge } from 'antd';
import { FileImageOutlined } from '@ant-design/icons';
import type { MaterialAsset } from '../../types/material';

const { Text } = Typography;

interface SuggestedMaterial extends MaterialAsset {
  score: number;
}

interface MaterialSuggestPanelProps {
  visible: boolean;
  loading?: boolean;
  suggestions: SuggestedMaterial[];
  onConfirm: (selectedIds: string[]) => void;
  onSkip: () => void;
  onCancel: () => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  business_license: '营业执照',
  legal_person_id: '法人身份证',
  qualification_cert: '资质证书',
  award_cert: '获奖证书',
  iso_cert: 'ISO认证',
  contract_sample: '合同样本',
  project_case: '项目案例',
  team_photo: '团队照片',
  equipment_photo: '设备照片',
  financial_report: '财务报告',
  bank_credit: '银行信用',
  social_security: '社会保障',
  other: '其他',
};

function getScoreColor(score: number): string {
  if (score >= 70) return 'green';
  if (score >= 50) return 'blue';
  return 'default';
}

function getScoreLabel(score: number): string {
  if (score >= 70) return '高匹配';
  if (score >= 50) return '中匹配';
  return '低匹配';
}

const MaterialSuggestPanel: React.FC<MaterialSuggestPanelProps> = ({
  visible,
  loading = false,
  suggestions,
  onConfirm,
  onSkip,
  onCancel,
}) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const handleToggle = (id: string, disabled: boolean) => {
    if (disabled) return;
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleConfirm = () => {
    onConfirm(selectedIds);
    setSelectedIds([]);
  };

  const handleSkip = () => {
    onSkip();
    setSelectedIds([]);
  };

  return (
    <Modal
      title="章节生成前推荐素材"
      open={visible}
      onCancel={onCancel}
      width={560}
      okText="确认并生成"
      cancelText="跳过，直接生成"
      onOk={handleConfirm}
      footer={[
        <button
          key="skip"
          className="ant-btn"
          onClick={handleSkip}
          style={{ marginRight: 8 }}
        >
          跳过，直接生成
        </button>,
        <button
          key="confirm"
          className="ant-btn ant-btn-primary"
          onClick={handleConfirm}
          disabled={selectedIds.length === 0}
        >
          确认选中 {selectedIds.length > 0 ? `(${selectedIds.length})` : ''} 并生成
        </button>,
      ]}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '32px 0' }}>
          <Spin tip="正在检索匹配素材..." />
        </div>
      ) : suggestions.length === 0 ? (
        <Empty description="未找到匹配素材，将直接生成" />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Text type="secondary" style={{ fontSize: 12 }}>
            以下素材与本章节匹配度较高，勾选后 AI 将参考其内容进行生成
          </Text>
          {suggestions.map(item => {
            const isUnavailable = item.is_expired || item.is_disabled;
            const isSelected = selectedIds.includes(item.id);
            return (
              <div
                key={item.id}
                onClick={() => handleToggle(item.id, isUnavailable)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 12px',
                  border: `1px solid ${isSelected ? '#1677ff' : '#f0f0f0'}`,
                  borderRadius: 8,
                  background: isUnavailable ? '#fafafa' : (isSelected ? '#e6f4ff' : '#fff'),
                  cursor: isUnavailable ? 'not-allowed' : 'pointer',
                  opacity: isUnavailable ? 0.5 : 1,
                  transition: 'all 0.15s',
                }}
              >
                <Checkbox
                  checked={isSelected}
                  disabled={isUnavailable}
                  onChange={() => handleToggle(item.id, isUnavailable)}
                />
                <FileImageOutlined style={{ color: '#8c8c8c', fontSize: 16 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Text strong style={{ fontSize: 13 }}>{item.name}</Text>
                    {item.is_disabled && <Tag color="default">已停用</Tag>}
                    {!item.is_disabled && item.is_expired && <Tag color="red">已过期</Tag>}
                  </div>
                  <div style={{ marginTop: 2 }}>
                    {item.category && (
                      <Tag style={{ marginRight: 4 }}>{CATEGORY_LABELS[item.category] || item.category}</Tag>
                    )}
                    <Badge
                      color={getScoreColor(item.score)}
                      text={
                        <Text style={{ fontSize: 11, color: '#8c8c8c' }}>
                          {getScoreLabel(item.score)} ({item.score})
                        </Text>
                      }
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </Space>
      )}
    </Modal>
  );
};

export default MaterialSuggestPanel;
