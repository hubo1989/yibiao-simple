import React from 'react';
import { Drawer, List, Empty, Button, Tag } from 'antd';
import { REVIEW_TASK_STATUS_LABELS } from '../../types/review';
import type { ReviewHistoryItem } from '../../types/review';

interface ReviewHistoryDrawerProps {
  open: boolean;
  onClose: () => void;
  items: ReviewHistoryItem[];
  onSelectItem: (taskId: string) => void;
}

const ReviewHistoryDrawer: React.FC<ReviewHistoryDrawerProps> = ({
  open,
  onClose,
  items,
  onSelectItem,
}) => (
  <Drawer title="审查历史" open={open} onClose={onClose} width={480}>
    {items.length === 0 ? (
      <Empty description="暂无审查历史" />
    ) : (
      <List
        dataSource={items}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Button
                type="link"
                size="small"
                onClick={() => onSelectItem(item.task_id)}
              >
                查看结果
              </Button>,
            ]}
          >
            <List.Item.Meta
              avatar={
                <Tag color={
                  item.status === 'completed' ? 'green' :
                  item.status === 'failed' ? 'red' : 'default'
                }>
                  {REVIEW_TASK_STATUS_LABELS[item.status]}
                </Tag>
              }
              title={
                item.summary
                  ? `得分 ${item.summary.overall_score} / 覆盖率 ${Math.round(item.summary.coverage_rate * 100)}%`
                  : '无结果'
              }
              description={`${item.model_name || '默认模型'} · ${new Date(item.created_at).toLocaleString()}`}
            />
          </List.Item>
        )}
      />
    )}
  </Drawer>
);

export default ReviewHistoryDrawer;
