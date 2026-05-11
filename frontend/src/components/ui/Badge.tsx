import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  /** 颜色变体 */
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'ai';
  /** 带脉冲圆点 */
  dot?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const variantMap = {
  default: {
    bg: 'var(--bg-elevated)',
    color: 'var(--text-secondary)',
    dot: 'var(--text-muted)',
  },
  success: {
    bg: 'var(--success-bg)',
    color: 'var(--success)',
    dot: 'var(--success)',
  },
  warning: {
    bg: 'var(--warning-bg)',
    color: 'var(--warning)',
    dot: 'var(--warning)',
  },
  error: {
    bg: 'var(--error-bg)',
    color: 'var(--error)',
    dot: 'var(--error)',
  },
  info: {
    bg: 'var(--info-bg)',
    color: 'var(--info)',
    dot: 'var(--info)',
  },
  ai: {
    bg: 'var(--ai-bg)',
    color: 'var(--accent-light)',
    dot: 'var(--accent)',
  },
};

/**
 * 状态徽章组件
 */
const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  dot = false,
  className = '',
  style,
}) => {
  const v = variantMap[variant];

  return (
    <span
      className={`ui-badge ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 12px',
        borderRadius: '9999px',
        fontSize: '12px',
        fontWeight: 500,
        background: v.bg,
        color: v.color,
        lineHeight: 1,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {dot && (
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: v.dot,
            flexShrink: 0,
          }}
        />
      )}
      {children}
    </span>
  );
};

export default Badge;
