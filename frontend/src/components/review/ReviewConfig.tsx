import React from 'react';
import { Typography, Checkbox, Switch } from 'antd';
import type { ReviewDimension } from '../../types/review';

interface ReviewConfigProps {
  dimensions: ReviewDimension[];
  onDimensionsChange: (values: ReviewDimension[]) => void;
  useKnowledge: boolean;
  onKnowledgeChange: (checked: boolean) => void;
}

const ReviewConfig: React.FC<ReviewConfigProps> = ({
  dimensions,
  onDimensionsChange,
  useKnowledge,
  onKnowledgeChange,
}) => (
  <div style={{ maxWidth: 600 }}>
    <div style={{ marginBottom: 24 }}>
      <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>审查维度</Typography.Text>
      <Checkbox.Group
        value={dimensions}
        onChange={(vals) => onDimensionsChange(vals as ReviewDimension[])}
        options={[
          { label: '响应性审查', value: 'responsiveness' },
          { label: '合规性审查', value: 'compliance' },
          { label: '一致性审查', value: 'consistency' },
        ]}
      />
    </div>
    <div style={{ marginBottom: 24 }}>
      <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>知识库辅助</Typography.Text>
      <Switch
        checked={useKnowledge}
        onChange={onKnowledgeChange}
        checkedChildren="已开启"
        unCheckedChildren="已关闭"
      />
      <div>
        <Typography.Text type="secondary" style={{ fontSize: 13 }}>
          开启后将使用项目关联的知识库作为审查参考
        </Typography.Text>
      </div>
    </div>
  </div>
);

export default ReviewConfig;
