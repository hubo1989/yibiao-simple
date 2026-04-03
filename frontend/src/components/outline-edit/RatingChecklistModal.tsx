import React from 'react';
import { Modal, Button, Typography, Tag, Alert, Spin } from 'antd';
import type { RatingChecklistResponse } from '../../types/bid';

interface RatingChecklistModalProps {
  visible: boolean;
  isLoading: boolean;
  data: RatingChecklistResponse | null;
  onRefresh: () => void;
  onClose: () => void;
}

const RatingChecklistModal: React.FC<RatingChecklistModalProps> = ({
  visible,
  isLoading,
  data,
  onRefresh,
  onClose,
}) => (
  <Modal
    title="评分响应清单"
    open={visible}
    width={920}
    onCancel={onClose}
    footer={[
      <Button key="refresh" onClick={onRefresh} loading={isLoading}>
        重新生成
      </Button>,
      <Button key="close" type="primary" onClick={onClose}>
        关闭
      </Button>,
    ]}
  >
    {isLoading ? (
      <div style={{ padding: '48px 0', textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    ) : data?.items?.length ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxHeight: '70vh', overflowY: 'auto', paddingRight: 4 }}>
        <Alert
          type="info"
          showIcon
          message={`共生成 ${data.items.length} 条评分项响应建议，可用于核对目录覆盖范围与后续正文写作重点。`}
        />

        {data.items.map((item, index) => (
          <div
            key={`${item.rating_item}-${index}`}
            style={{
              border: '1px solid #e5e7eb',
              borderRadius: 16,
              padding: 16,
              background: '#fff',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 12, alignItems: 'flex-start' }}>
              <div>
                <Typography.Text strong style={{ fontSize: 15 }}>
                  {index + 1}. {item.rating_item}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                  建议优先映射到目录主职责明确、能直接承接评分要点的章节中。
                </Typography.Text>
              </div>
              <Tag color="blue">{item.score || '未标注分值'}</Tag>
            </div>

            {item.response_targets?.length ? (
              <div style={{ marginBottom: 12 }}>
                <Typography.Text strong>响应目标</Typography.Text>
                <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {item.response_targets.map((target) => (
                    <Tag key={target} color="geekblue">{target}</Tag>
                  ))}
                </div>
              </div>
            ) : null}

            {item.evidence_suggestions?.length ? (
              <div style={{ marginBottom: 12 }}>
                <Typography.Text strong>建议佐证</Typography.Text>
                <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                  {item.evidence_suggestions.map((evidence, evidenceIndex) => (
                    <Typography.Text key={`${evidence}-${evidenceIndex}`} type="secondary">
                      &bull; {evidence}
                    </Typography.Text>
                  ))}
                </div>
              </div>
            ) : null}

            {item.writing_focus ? (
              <div style={{ marginBottom: item.risk_points?.length ? 12 : 0 }}>
                <Typography.Text strong>写作重点</Typography.Text>
                <Typography.Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
                  {item.writing_focus}
                </Typography.Paragraph>
              </div>
            ) : null}

            {item.risk_points?.length ? (
              <div>
                <Typography.Text strong style={{ color: '#cf1322' }}>失分风险</Typography.Text>
                <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                  {item.risk_points.map((risk, riskIndex) => (
                    <Typography.Text key={`${risk}-${riskIndex}`} style={{ color: '#cf1322' }}>
                      &bull; {risk}
                    </Typography.Text>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    ) : (
      <Alert
        type="warning"
        showIcon
        message="暂未生成评分响应清单"
        description="请确认项目已经完成标书解析，并且技术评分要求已成功保存。"
      />
    )}
  </Modal>
);

export default RatingChecklistModal;
