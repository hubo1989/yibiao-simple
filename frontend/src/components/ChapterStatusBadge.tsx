/**
 * 章节状态标签组件
 */
import React from 'react';
import type { ChapterStatus } from '../types/chapter';
import { CHAPTER_STATUS_LABELS, CHAPTER_STATUS_COLORS } from '../types/chapter';

interface ChapterStatusBadgeProps {
  status: ChapterStatus;
  size?: 'sm' | 'md';
}

const ChapterStatusBadge: React.FC<ChapterStatusBadgeProps> = ({ status, size = 'sm' }) => {
  const label = CHAPTER_STATUS_LABELS[status];
  const colorClass = CHAPTER_STATUS_COLORS[status];
  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';

  return (
    <span className={`inline-flex items-center rounded-full font-medium ${colorClass} ${sizeClass}`}>
      {label}
    </span>
  );
};

export default ChapterStatusBadge;
