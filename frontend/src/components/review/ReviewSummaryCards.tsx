import React from 'react';
import { Card, Statistic, Tag } from 'antd';
import { CloseCircleOutlined, WarningOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { RISK_LEVEL_LABELS } from '../../types/review';
import type { ReviewSummary } from '../../types/review';

interface ReviewSummaryCardsProps {
  summary: ReviewSummary;
}

const ReviewSummaryCards: React.FC<ReviewSummaryCardsProps> = ({ summary }) => (
  <>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
      <Card bordered>
        <Statistic
          title="综合得分"
          value={summary.overall_score}
          suffix={`/ ${summary.score_max}`}
          valueStyle={{
            color: summary.overall_score >= 80 ? '#3f8600' : summary.overall_score >= 60 ? '#cf1322' : undefined,
          }}
        />
      </Card>
      <Card bordered>
        <Statistic
          title="覆盖率"
          value={Math.round(summary.coverage_rate * 100)}
          suffix="%"
          valueStyle={{
            color: summary.coverage_rate >= 0.8 ? '#3f8600' : '#cf1322',
          }}
        />
      </Card>
      <Card bordered>
        <Statistic title="问题总数" value={summary.total_issues} />
      </Card>
      <Card bordered>
        <Statistic
          title="风险等级"
          value={RISK_LEVEL_LABELS[summary.risk_level]}
          valueStyle={{
            color: summary.risk_level === 'low' ? '#3f8600' : summary.risk_level === 'medium' ? '#fa8c16' : '#cf1322',
          }}
        />
      </Card>
    </div>

    {summary.issue_distribution && (
      <div style={{ marginBottom: 24, display: 'flex', gap: 16 }}>
        <Tag color="red" style={{ fontSize: 13, padding: '4px 12px' }}>
          <CloseCircleOutlined /> 严重：{summary.issue_distribution.critical}
        </Tag>
        <Tag color="orange" style={{ fontSize: 13, padding: '4px 12px' }}>
          <WarningOutlined /> 警告：{summary.issue_distribution.warning}
        </Tag>
        <Tag color="blue" style={{ fontSize: 13, padding: '4px 12px' }}>
          <InfoCircleOutlined /> 提示：{summary.issue_distribution.info}
        </Tag>
      </div>
    )}
  </>
);

export default ReviewSummaryCards;
