import React from 'react';
import { Typography, Tag, Button, Tooltip, Collapse, List } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import {
  COVERAGE_STATUS_LABELS,
  COVERAGE_STATUS_COLORS,
  SEVERITY_LABELS,
  SEVERITY_COLORS,
} from '../../types/review';
import type {
  ResponsivenessItem,
  ComplianceItem,
  ConsistencyItem,
} from '../../types/review';

interface ReviewIssueItemProps {
  dimension: string;
  item: ResponsivenessItem | ComplianceItem | ConsistencyItem;
  onCopy?: (text: string) => void;
}

const ReviewIssueItem: React.FC<ReviewIssueItemProps> = ({ dimension, item, onCopy }) => {
  if (dimension === 'responsiveness') {
    const r = item as ResponsivenessItem;
    return (
      <List.Item style={{ padding: '16px 0' }}>
        <div style={{ width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Tag color={COVERAGE_STATUS_COLORS[r.coverage_status]}>
              {COVERAGE_STATUS_LABELS[r.coverage_status]}
            </Tag>
            <Typography.Text strong>{r.rating_item}</Typography.Text>
            <Tag>
              置信度: {r.confidence === 'high' ? '高' : r.confidence === 'medium' ? '中' : '低'}
            </Tag>
          </div>
          {r.evidence && (
            <Typography.Paragraph type="secondary" style={{ fontSize: 13, marginBottom: 4 }}>
              证据：{r.evidence}
            </Typography.Paragraph>
          )}
          {r.issues.length > 0 && (
            <div style={{ marginBottom: 4 }}>
              {r.issues.map((issue, i) => (
                <div key={i} style={{ color: '#cf1322', fontSize: 13 }}>
                  问题{i + 1}：{issue}
                </div>
              ))}
            </div>
          )}
          {r.suggestions.length > 0 && (
            <div style={{ marginBottom: 4 }}>
              {r.suggestions.map((s, i) => (
                <div key={i} style={{ color: '#0958d9', fontSize: 13 }}>
                  建议{i + 1}：{s}
                </div>
              ))}
            </div>
          )}
          {r.rewrite_suggestions.length > 0 && (
            <div style={{ marginTop: 4 }}>
              {r.rewrite_suggestions.map((rw, i) => (
                <div key={i} style={{
                  background: '#f6ffed', border: '1px solid #b7eb8f',
                  borderRadius: 6, padding: '6px 10px', fontSize: 13,
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                  <span>{rw}</span>
                  {onCopy && (
                    <Tooltip title="复制">
                      <Button
                        type="text"
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={() => onCopy(rw)}
                      />
                    </Tooltip>
                  )}
                </div>
              ))}
            </div>
          )}
          {r.chapter_targets.length > 0 && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              位置：{r.chapter_targets.join('、')}
            </Typography.Text>
          )}
          {r.source_refs.length > 0 && (
            <Collapse
              ghost
              size="small"
              items={[{
                key: 'detail',
                label: '引用来源',
                children: r.source_refs.map((ref, i) => (
                  <div key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                    <Typography.Text type="secondary">{ref.location}</Typography.Text>
                    <Typography.Paragraph style={{ fontSize: 13, margin: '2px 0' }} ellipsis={{ rows: 2 }}>
                      "{ref.quote}"
                    </Typography.Paragraph>
                    <Typography.Text type="secondary">{ref.relation}</Typography.Text>
                  </div>
                )),
              }]}
            />
          )}
        </div>
      </List.Item>
    );
  }

  if (dimension === 'compliance') {
    const c = item as ComplianceItem;
    return (
      <List.Item style={{ padding: '16px 0' }}>
        <div style={{ width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Tag color={c.check_result === 'pass' ? 'green' : c.check_result === 'fail' ? 'red' : 'orange'}>
              {c.check_result === 'pass' ? '通过' : c.check_result === 'fail' ? '不通过' : '警告'}
            </Tag>
            <Tag color={SEVERITY_COLORS[c.severity]}>{SEVERITY_LABELS[c.severity]}</Tag>
            <Typography.Text strong>{c.compliance_category}</Typography.Text>
          </div>
          {c.clause_text && (
            <Typography.Paragraph type="secondary" style={{ fontSize: 13 }}>
              招标条款：{c.clause_text}
            </Typography.Paragraph>
          )}
          <Typography.Paragraph style={{ fontSize: 13, marginBottom: 4 }}>{c.detail}</Typography.Paragraph>
          {c.suggestion && (
            <Typography.Text style={{ color: '#0958d9', fontSize: 13 }}>
              建议：{c.suggestion}
            </Typography.Text>
          )}
        </div>
      </List.Item>
    );
  }

  if (dimension === 'consistency') {
    const c = item as ConsistencyItem;
    return (
      <List.Item style={{ padding: '16px 0' }}>
        <div style={{ width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Tag color={SEVERITY_COLORS[c.severity]}>{SEVERITY_LABELS[c.severity]}</Tag>
            <Typography.Text strong>{c.description}</Typography.Text>
          </div>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            <Typography.Text type="secondary">章节A：</Typography>{c.chapter_a}
            <Typography.Paragraph style={{ fontSize: 13, margin: '2px 0' }}>{c.detail_a}</Typography.Paragraph>
          </div>
          <div style={{ fontSize: 13, marginBottom: 4 }}>
            <Typography.Text type="secondary">章节B：</Typography>{c.chapter_b}
            <Typography.Paragraph style={{ fontSize: 13, margin: '2px 0' }}>{c.detail_b}</Typography.Paragraph>
          </div>
          {c.suggestion && (
            <Typography.Text style={{ color: '#0958d9', fontSize: 13 }}>
              建议：{c.suggestion}
            </Typography.Text>
          )}
        </div>
      </List.Item>
    );
  }

  return null;
};

export default ReviewIssueItem;
