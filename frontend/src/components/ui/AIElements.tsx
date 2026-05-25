import React from 'react';

/**
 * AI 思考指示器 — 三个脉冲点
 */
export const AIThinkingDots: React.FC<{ label?: string }> = ({ label }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--accent-light)', fontSize: '13px' }}>
    <span className="ai-thinking-dots">
      <span /><span /><span />
    </span>
    {label && <span>{label}</span>}
  </span>
);

/**
 * AI 生成内容标记 — 左侧紫色边框
 */
export const AIGeneratedMark: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="ai-generated" style={{ margin: '8px 0' }}>
    {children}
  </div>
);

/**
 * AI Sparkle 图标
 */
export const SparkleIcon: React.FC<{ size?: number; color?: string }> = ({
  size = 16,
  color = 'var(--accent-light)',
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M12 2L14.09 8.26L20 9.27L15.55 13.97L16.91 20L12 16.9L7.09 20L8.45 13.97L4 9.27L9.91 8.26L12 2Z"
      fill={color}
    />
  </svg>
);

/**
 * 进度环组件
 */
export const ProgressRing: React.FC<{
  percent: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
}> = ({ percent, size = 60, strokeWidth = 5, color }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  const ringColor = color || (percent >= 100 ? 'var(--success)' : percent >= 50 ? 'var(--accent)' : 'var(--accent-blue)');

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        {/* 底圈 */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth={strokeWidth}
        />
        {/* 进度圈 */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={ringColor}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{
            transition: 'stroke-dashoffset 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        />
      </svg>
      <span
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: size > 50 ? '14px' : '11px',
          fontWeight: 600,
          color: 'var(--text-primary)',
        }}
      >
        {Math.round(percent)}%
      </span>
    </div>
  );
};

/**
 * 骨架屏条
 */
export const SkeletonLine: React.FC<{
  width?: string;
  height?: string;
}> = ({ width = '100%', height = '14px' }) => (
  <div className="skeleton" style={{ width, height }} />
);

/**
 * 骨架屏段落
 */
export const SkeletonParagraph: React.FC<{ lines?: number }> = ({ lines = 3 }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
    {Array.from({ length: lines }).map((_, i) => (
      <SkeletonLine
        key={i}
        width={i === lines - 1 ? '60%' : '100%'}
      />
    ))}
  </div>
);
