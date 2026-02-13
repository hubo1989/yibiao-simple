/**
 * 章节锁定状态指示器组件
 */
import React from 'react';
import { LockClosedIcon, LockOpenIcon } from '@heroicons/react/24/outline';

interface ChapterLockIndicatorProps {
  isLocked: boolean;
  lockExpired: boolean;
  lockedByUsername: string | null;
  currentUserId?: string;
  lockedByUserId?: string | null;
}

const ChapterLockIndicator: React.FC<ChapterLockIndicatorProps> = ({
  isLocked,
  lockExpired,
  lockedByUsername,
  currentUserId,
  lockedByUserId,
}) => {
  // 锁已过期或未锁定
  if (!isLocked || lockExpired) {
    return (
      <span className="inline-flex items-center text-gray-400 text-xs">
        <LockOpenIcon className="w-3 h-3 mr-1" />
        可编辑
      </span>
    );
  }

  // 当前用户自己锁定
  const isSelfLocked = currentUserId && lockedByUserId === currentUserId;
  if (isSelfLocked) {
    return (
      <span className="inline-flex items-center text-blue-600 text-xs bg-blue-50 px-2 py-0.5 rounded">
        <LockClosedIcon className="w-3 h-3 mr-1" />
        我正在编辑
      </span>
    );
  }

  // 被其他人锁定
  return (
    <span className="inline-flex items-center text-orange-600 text-xs bg-orange-50 px-2 py-0.5 rounded" title={`被 ${lockedByUsername || '未知用户'} 锁定`}>
      <LockClosedIcon className="w-3 h-3 mr-1" />
      {lockedByUsername || '未知用户'} 编辑中
    </span>
  );
};

export default ChapterLockIndicator;
