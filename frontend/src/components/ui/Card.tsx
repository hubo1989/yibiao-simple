import React, { useState } from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  /** 悬停时显示紫色发光边框 */
  hoverable?: boolean;
  /** AI 生成内容卡片（带紫色流光边框） */
  aiGenerated?: boolean;
  /** AI 正在生成中（呼吸灯） */
  aiStreaming?: boolean;
  /** 点击事件 */
  onClick?: () => void;
  /** 可选的 padding 大小 */
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

const paddingMap = {
  none: '0',
  sm: '16px',
  md: '24px',
  lg: '32px',
};

const baseBorderStyle = (aiGenerated: boolean): React.CSSProperties => ({
  borderColor: aiGenerated ? 'var(--ai-border)' : 'var(--border)',
  boxShadow: 'none',
  transform: 'translateY(0)',
});

const hoverBorderStyle: React.CSSProperties = {
  borderColor: 'rgba(124, 58, 237, 0.25)',
  boxShadow: '0 0 30px rgba(124, 58, 237, 0.15)',
  transform: 'translateY(-2px)',
};

/**
 * AI Native 卡片组件
 * 深色表面 + 可选发光/流光效果
 */
const Card: React.FC<CardProps> = ({
  children,
  className = '',
  style,
  hoverable = false,
  aiGenerated = false,
  aiStreaming = false,
  onClick,
  padding = 'md',
}) => {
  const [hovered, setHovered] = useState(false);

  const classes = [
    'ui-card',
    hoverable && 'hoverable',
    aiGenerated && 'ai-shimmer',
    aiStreaming && 'ai-pulse',
    className,
  ].filter(Boolean).join(' ');

  const hoverStyle = hovered && hoverable ? hoverBorderStyle : baseBorderStyle(aiGenerated);

  return (
    <div
      className={classes}
      onClick={onClick}
      style={{
        background: 'var(--bg-surface)',
        border: `1px solid ${aiGenerated ? 'var(--ai-border)' : 'var(--border)'}`,
        borderRadius: 'var(--radius-lg)',
        padding: paddingMap[padding],
        transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative',
        ...hoverStyle,
        ...style,
      }}
      onMouseEnter={() => hoverable && setHovered(true)}
      onMouseLeave={() => hoverable && setHovered(false)}
    >
      {children}
    </div>
  );
};

export default Card;
