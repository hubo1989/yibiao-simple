import React from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'ai';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: React.ReactNode;
  glow?: boolean;
}

const variantStyles: Record<Variant, string> = {
  primary: `
    background: linear-gradient(135deg, #7c3aed 0%, #6366f1 100%);
    color: #fff;
    border: none;
    box-shadow: 0 4px 14px rgba(124, 58, 237, 0.35);
  `,
  secondary: `
    background: var(--bg-surface);
    color: var(--text-primary);
    border: 1px solid var(--border);
  `,
  ghost: `
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid transparent;
  `,
  danger: `
    background: var(--error-bg);
    color: var(--error);
    border: 1px solid rgba(239, 68, 68, 0.3);
  `,
  ai: `
    background: var(--ai-bg);
    color: var(--accent-light);
    border: 1px solid var(--ai-border);
  `,
};

const sizeMap: Record<Size, { height: string; padding: string; fontSize: string }> = {
  sm: { height: '32px', padding: '0 12px', fontSize: '13px' },
  md: { height: '40px', padding: '0 20px', fontSize: '14px' },
  lg: { height: '48px', padding: '0 28px', fontSize: '15px' },
};

/**
 * AI Native 按钮组件
 * 支持 primary/secondary/ghost/danger/ai 变体
 */
const Button: React.FC<ButtonProps> = ({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  glow = false,
  children,
  disabled,
  style,
  className = '',
  ...rest
}) => {
  const sizeStyle = sizeMap[size];

  return (
    <button
      disabled={disabled || loading}
      className={`ui-button ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        borderRadius: 'var(--radius-md)',
        fontFamily: 'var(--font-sans)',
        fontWeight: 500,
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        transition: 'all 150ms cubic-bezier(0.16, 1, 0.3, 1)',
        height: sizeStyle.height,
        padding: sizeStyle.padding,
        fontSize: sizeStyle.fontSize,
        boxShadow: glow ? '0 0 30px rgba(124, 58, 237, 0.3)' : undefined,
        ...parseStyleString(variantStyles[variant]),
        ...style,
      }}
      onMouseEnter={(e) => {
        if (disabled || loading) return;
        const el = e.currentTarget;
        el.style.transform = 'translateY(-1px)';
        if (variant === 'primary') {
          el.style.filter = 'brightness(1.1)';
          el.style.boxShadow = '0 6px 20px rgba(124, 58, 237, 0.5)';
        } else if (variant === 'secondary') {
          el.style.borderColor = 'var(--accent)';
          el.style.color = 'var(--accent-light)';
        } else if (variant === 'ghost') {
          el.style.background = 'var(--bg-hover)';
          el.style.color = 'var(--text-primary)';
        } else if (variant === 'ai') {
          el.style.boxShadow = '0 0 20px rgba(124, 58, 237, 0.3)';
        }
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget;
        el.style.transform = '';
        el.style.filter = '';
        const v = variantStyles[variant];
        Object.assign(el.style, parseStyleString(v));
        if (glow) {
          el.style.boxShadow = '0 0 30px rgba(124, 58, 237, 0.3)';
        }
      }}
      {...rest}
    >
      {loading ? (
        <span className="ai-thinking-dots">
          <span /><span /><span />
        </span>
      ) : icon ? (
        <span style={{ display: 'flex', alignItems: 'center' }}>{icon}</span>
      ) : null}
      {children}
    </button>
  );
};

/**
 * 将 CSS style string 解析为 React CSSProperties 对象
 */
function parseStyleString(str: string): React.CSSProperties {
  const result: Record<string, string> = {};
  str.split(';').forEach((pair) => {
    const [key, ...valParts] = pair.split(':');
    if (key && valParts.length) {
      const prop = key.trim().replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      result[prop] = valParts.join(':').trim();
    }
  });
  return result as React.CSSProperties;
}

export default Button;
