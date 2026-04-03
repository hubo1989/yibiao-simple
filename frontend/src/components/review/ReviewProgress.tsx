import React from 'react';
import { Typography, Progress, Tag, Spin } from 'antd';
import { CheckCircleOutlined } from '@ant-design/icons';
import { REVIEW_DIMENSION_LABELS } from '../../types/review';
import type { ReviewDimension } from '../../types/review';

interface ReviewProgressProps {
  dimensions: ReviewDimension[];
  progress: Record<string, string>;
  reviewing: boolean;
}

const ReviewProgress: React.FC<ReviewProgressProps> = ({ dimensions, progress, reviewing }) => {
  const getDimensionProgress = (dim: ReviewDimension) => {
    const status = progress[dim];
    if (status === 'completed') return 'done';
    if (status === 'processing') return 'active';
    if (dimensions.includes(dim)) return 'wait';
    return 'default';
  };

  return (
    <div style={{ padding: '20px 0' }}>
      {dimensions.map((dim) => {
        const pState = getDimensionProgress(dim);
        return (
          <div key={dim} style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <Typography.Text strong>{REVIEW_DIMENSION_LABELS[dim]}审查</Typography.Text>
              {pState === 'done' && (
                <Tag icon={<CheckCircleOutlined />} color="success">完成</Tag>
              )}
              {pState === 'active' && (
                <Tag icon={<Spin size="small" />} color="processing">进行中</Tag>
              )}
              {pState === 'wait' && <Tag>等待中</Tag>}
            </div>
            <Progress
              percent={pState === 'done' ? 100 : pState === 'active' ? 50 : 0}
              status={pState === 'done' ? 'success' : pState === 'active' ? 'active' : 'normal'}
            />
          </div>
        );
      })}
      {reviewing && (
        <div style={{ textAlign: 'center', marginTop: 20 }}>
          <Typography.Text type="secondary">正在执行 AI 审查，请稍候...</Typography.Text>
        </div>
      )}
    </div>
  );
};

export default ReviewProgress;
