import React from 'react';
import { Card, Tabs, Select, List, Empty } from 'antd';
import { REVIEW_DIMENSION_LABELS } from '../../types/review';
import type { ReviewDimension, ResponsivenessItem, ComplianceItem, ConsistencyItem } from '../../types/review';
import ReviewIssueItem from './ReviewIssueItem';

interface IssueEntry {
  dimension: string;
  item: ResponsivenessItem | ComplianceItem | ConsistencyItem;
  key: string;
}

interface ReviewIssueListProps {
  dimensions: ReviewDimension[];
  allIssues: IssueEntry[];
  dimensionTab: string;
  onDimensionTabChange: (key: string) => void;
  severityFilter: string;
  onSeverityFilterChange: (value: string) => void;
  onCopy?: (text: string) => void;
}

const ReviewIssueList: React.FC<ReviewIssueListProps> = ({
  dimensions,
  allIssues,
  dimensionTab,
  onDimensionTabChange,
  severityFilter,
  onSeverityFilterChange,
  onCopy,
}) => {
  const filteredIssues = allIssues.filter((entry) => {
    if (dimensionTab !== 'all' && entry.dimension !== dimensionTab) return false;
    if (severityFilter !== 'all') {
      const sev = entry.item.severity || entry.item.coverage_status;
      const sevMap: Record<string, string> = {
        covered: 'info',
        partial: 'warning',
        missing: 'critical',
        risk: 'critical',
      };
      if (sevMap[sev] !== severityFilter) return false;
    }
    return true;
  });

  return (
    <Card bordered>
      <Tabs
        activeKey={dimensionTab}
        onChange={onDimensionTabChange}
        items={[
          { key: 'all', label: `全部 (${allIssues.length})` },
          ...dimensions.map((d) => ({
            key: d,
            label: `${REVIEW_DIMENSION_LABELS[d]} (${
              allIssues.filter((e) => e.dimension === d).length
            })`,
          })),
        ]}
        tabBarExtraContent={
          <Select
            value={severityFilter}
            onChange={onSeverityFilterChange}
            style={{ width: 120 }}
            options={[
              { value: 'all', label: '全部级别' },
              { value: 'critical', label: '严重' },
              { value: 'warning', label: '警告' },
              { value: 'info', label: '提示' },
            ]}
          />
        }
      />
      {filteredIssues.length === 0 ? (
        <Empty description="没有匹配的审查结果" style={{ padding: '40px 0' }} />
      ) : (
        <List
          dataSource={filteredIssues}
          rowKey="key"
          renderItem={(entry) => (
            <ReviewIssueItem
              dimension={entry.dimension}
              item={entry.item}
              onCopy={onCopy}
            />
          )}
        />
      )}
    </Card>
  );
};

export default ReviewIssueList;
