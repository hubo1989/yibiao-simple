import React from 'react';
import { Modal, Space, Alert, Button, Typography, Tag, Card, Spin } from 'antd';
import type { ChapterReverseEnhanceResponse, ChapterEnhancementAction } from '../../types/bid';

interface ReverseEnhanceModalProps {
  visible: boolean;
  target: { chapterNumber: string; title: string } | null;
  isLoading: boolean;
  result: ChapterReverseEnhanceResponse | null;
  onCopy: () => void;
  onClose: () => void;
}

const priorityLabel = (priority: string) => {
  if (priority === 'high') return '高优先级';
  if (priority === 'medium') return '中优先级';
  return '低优先级';
};

const priorityColor = (priority: string) => {
  if (priority === 'high') return 'error';
  if (priority === 'medium') return 'processing';
  return 'default';
};

const ReverseEnhanceModal: React.FC<ReverseEnhanceModalProps> = ({
  visible,
  target,
  isLoading,
  result,
  onCopy,
  onClose,
}) => (
  <Modal
    title={target ? `反向补强：${target.chapterNumber} ${target.title}` : '反向补强'}
    open={visible}
    width={820}
    onCancel={onClose}
    footer={[
      result ? (
        <Button key="copy" onClick={onCopy}>
          复制建议
        </Button>
      ) : null,
      <Button key="close" type="primary" onClick={onClose}>
        关闭
      </Button>,
    ]}
  >
    {isLoading ? (
      <div style={{ padding: '48px 0', textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    ) : result ? (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Alert type="info" showIcon message={result.coverage_assessment} description={result.summary} />

        <div>
          <Typography.Text strong>已覆盖评分点</Typography.Text>
          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {result.matched_points.length ? (
              result.matched_points.map((point) => (
                <Tag key={point} color="success">{point}</Tag>
              ))
            ) : (
              <Typography.Text type="secondary">暂无明确已覆盖评分点</Typography.Text>
            )}
          </div>
        </div>

        <div>
          <Typography.Text strong>待补强评分点</Typography.Text>
          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {result.missing_points.length ? (
              result.missing_points.map((point) => (
                <Tag key={point} color="error">{point}</Tag>
              ))
            ) : (
              <Typography.Text type="secondary">当前没有识别到明显缺失项</Typography.Text>
            )}
          </div>
        </div>

        <div style={{ display: 'grid', gap: 12 }}>
          <Typography.Text strong>补强动作</Typography.Text>
          {result.enhancement_actions.length ? (
            result.enhancement_actions.map((action: ChapterEnhancementAction, index: number) => (
              <Card key={`${action.problem}-${index}`} size="small">
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                  <Typography.Text strong>{index + 1}. {action.problem}</Typography.Text>
                  <Tag color={priorityColor(action.priority)}>{priorityLabel(action.priority)}</Tag>
                </div>
                <Typography.Paragraph style={{ marginTop: 8, marginBottom: action.evidence_needed ? 8 : 0 }}>
                  {action.action}
                </Typography.Paragraph>
                {action.evidence_needed ? (
                  <Typography.Text type="secondary">建议补充材料：{action.evidence_needed}</Typography.Text>
                ) : null}
              </Card>
            ))
          ) : (
            <Typography.Text type="secondary">暂无可执行补强动作</Typography.Text>
          )}
        </div>
      </Space>
    ) : (
      <Alert
        type="warning"
        showIcon
        message="暂未获得补强结果"
        description="请确认章节内容已生成且项目评分要求已保存，然后重试。"
      />
    )}
  </Modal>
);

export default ReverseEnhanceModal;
