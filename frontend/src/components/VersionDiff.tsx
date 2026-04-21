/**
 * 版本 Diff 高亮渲染组件
 */
import React from 'react';
import { Card, Tag, Typography, Collapse, Empty, Alert } from 'antd';
import {
  PlusCircleOutlined,
  MinusCircleOutlined,
  EditOutlined,
} from '@ant-design/icons';
import type { VersionDiffResponse, ChapterChange } from '../types/version';

const { Text, Paragraph } = Typography;

interface VersionDiffProps {
  diffData: VersionDiffResponse;
}

/** 简单的行级 diff 渲染：对比 old/new 内容，逐行标注 */
function renderContentDiff(oldContent: string | null, newContent: string | null): React.ReactNode {
  const oldLines = (oldContent || '').split('\n');
  const newLines = (newContent || '').split('\n');

  // 双指针逐行对比
  let i = 0;
  let j = 0;
  const finalLines: { type: 'same' | 'added' | 'removed'; text: string }[] = [];

  while (i < oldLines.length && j < newLines.length) {
    if (oldLines[i] === newLines[j]) {
      finalLines.push({ type: 'same', text: newLines[j] });
      i++;
      j++;
    } else {
      // 尝试看看 old[i] 是否在后面的 new 中出现
      const newIdx = newLines.indexOf(oldLines[i], j);
      const oldIdx = oldLines.indexOf(newLines[j], i);

      if (oldIdx === -1 && newIdx === -1) {
        // 都不匹配，old 行 removed，new 行 added
        finalLines.push({ type: 'removed', text: oldLines[i] });
        finalLines.push({ type: 'added', text: newLines[j] });
        i++;
        j++;
      } else if (newIdx === -1 || (oldIdx !== -1 && oldIdx - i <= newIdx - j)) {
        // old 当前行在 new 后面能找到，先输出 new 中的 added
        finalLines.push({ type: 'added', text: newLines[j] });
        j++;
      } else {
        // new 当前行在 old 后面能找到，先输出 old 中的 removed
        finalLines.push({ type: 'removed', text: oldLines[i] });
        i++;
      }
    }
  }
  while (i < oldLines.length) {
    finalLines.push({ type: 'removed', text: oldLines[i] });
    i++;
  }
  while (j < newLines.length) {
    finalLines.push({ type: 'added', text: newLines[j] });
    j++;
  }

  // 限制渲染行数，过多时折叠
  const MAX_LINES = 60;
  const linesToRender = finalLines.length > MAX_LINES ? finalLines.slice(0, MAX_LINES) : finalLines;
  const truncated = finalLines.length > MAX_LINES;

  return (
    <div style={{ fontFamily: 'monospace', fontSize: 12, lineHeight: '20px', overflowX: 'auto' }}>
      {linesToRender.map((line, idx) => {
        let bg = 'transparent';
        let color = '#333';
        let prefix = ' ';
        let textDecoration = 'none';

        if (line.type === 'added') {
          bg = '#e6ffec';
          color = '#1a7f37';
          prefix = '+';
        } else if (line.type === 'removed') {
          bg = '#ffebe9';
          color = '#cf222e';
          prefix = '-';
          textDecoration = 'line-through';
        }

        return (
          <div
            key={idx}
            style={{
              background: bg,
              color,
              padding: '1px 8px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              textDecoration,
            }}
          >
            <span style={{ opacity: 0.5, marginRight: 8, userSelect: 'none' }}>{prefix}</span>
            {line.text || ' '}
          </div>
        );
      })}
      {truncated && (
        <div style={{ padding: '4px 8px', color: '#888', fontStyle: 'italic' }}>
          ... 还有 {finalLines.length - MAX_LINES} 行未显示
        </div>
      )}
    </div>
  );
}

/** 截取内容摘要 */
function contentPreview(content: string | null, maxLen = 120): string {
  if (!content) return '（无内容）';
  const clean = content.replace(/\n+/g, ' ').trim();
  return clean.length > maxLen ? clean.slice(0, maxLen) + '...' : clean;
}

const ChangeCard: React.FC<{ change: ChapterChange }> = ({ change }) => {
  const { type } = change;

  const styleMap: Record<string, { borderColor: string; bg: string; tagColor: string; label: string; icon: React.ReactNode }> = {
    added: {
      borderColor: '#b7eb8f',
      bg: '#f6ffed',
      tagColor: 'success',
      label: '新增',
      icon: <PlusCircleOutlined />,
    },
    deleted: {
      borderColor: '#ffa39e',
      bg: '#fff2f0',
      tagColor: 'error',
      label: '删除',
      icon: <MinusCircleOutlined />,
    },
    modified: {
      borderColor: '#ffe58f',
      bg: '#fffbe6',
      tagColor: 'warning',
      label: '修改',
      icon: <EditOutlined />,
    },
  };

  const style = styleMap[type] || styleMap.modified;

  const title = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <Tag color={style.tagColor} icon={style.icon}>{style.label}</Tag>
      <Text strong style={{ fontSize: 13 }}>
        {change.chapter_number ? `${change.chapter_number} ` : ''}
        {change.title || '未命名章节'}
      </Text>
    </div>
  );

  return (
    <Card
      size="small"
      style={{
        marginBottom: 8,
        borderLeft: `3px solid ${style.borderColor}`,
        background: style.bg,
      }}
    >
      {title}

      {/* 标题变更 */}
      {type === 'modified' && change.title_changed && change.old_title && (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          <Text type="secondary">标题变更: </Text>
          <Text delete style={{ color: '#cf222e' }}>{change.old_title}</Text>
          <Text style={{ margin: '0 4px' }}>→</Text>
          <Text style={{ color: '#1a7f37' }}>{change.new_title}</Text>
        </div>
      )}

      {/* 内容变更 */}
      {type === 'modified' && change.content_changed && (
        <Collapse
          size="small"
          style={{ marginTop: 8, background: 'transparent' }}
          items={[
            {
              key: '1',
              label: <Text type="secondary" style={{ fontSize: 12 }}>查看内容变更</Text>,
              children: renderContentDiff(change.old_content, change.new_content),
            },
          ]}
        />
      )}

      {/* added/deleted 的摘要 */}
      {type === 'added' && change.new_content && (
        <Paragraph
          type="secondary"
          style={{ marginTop: 6, marginBottom: 0, fontSize: 12 }}
          ellipsis={{ rows: 2 }}
        >
          {contentPreview(change.new_content)}
        </Paragraph>
      )}
      {type === 'deleted' && change.old_content && (
        <Paragraph
          type="secondary"
          style={{ marginTop: 6, marginBottom: 0, fontSize: 12, textDecoration: 'line-through' }}
          ellipsis={{ rows: 2 }}
        >
          {contentPreview(change.old_content)}
        </Paragraph>
      )}
    </Card>
  );
};

const VersionDiff: React.FC<VersionDiffProps> = ({ diffData }) => {
  const { v1, v2, diff } = diffData;

  if (diff.total_changes === 0) {
    return <Empty description="两个版本之间没有差异" style={{ marginTop: 24 }} />;
  }

  return (
    <div>
      {/* 统计摘要 */}
      <Alert
        type="info"
        showIcon={false}
        style={{ marginBottom: 12 }}
        message={
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <Text strong style={{ fontSize: 13 }}>
              V{v1.version_number} → V{v2.version_number} 变更:
            </Text>
            {diff.added > 0 && <Tag color="success">新增 {diff.added} 章节</Tag>}
            {diff.deleted > 0 && <Tag color="error">删除 {diff.deleted} 章节</Tag>}
            {diff.modified > 0 && <Tag color="warning">修改 {diff.modified} 章节</Tag>}
            <Text type="secondary" style={{ fontSize: 12 }}>
              共 {diff.total_changes} 处变更
            </Text>
          </div>
        }
      />

      {/* 变更列表 */}
      {diff.changes.map((change, idx) => (
        <ChangeCard key={`${change.chapter_id}-${idx}`} change={change} />
      ))}
    </div>
  );
};

export default VersionDiff;
