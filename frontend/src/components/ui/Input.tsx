import React, { useState } from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** 前缀图标 */
  prefixIcon?: React.ReactNode;
  /** 后缀图标 */
  suffixIcon?: React.ReactNode;
  /** 尺寸 */
  inputSize?: 'sm' | 'md' | 'lg';
  /** 全宽 */
  fullWidth?: boolean;
}

const sizeMap = {
  sm: { height: '36px', fontSize: '13px', padding: '0 12px' },
  md: { height: '44px', fontSize: '14px', padding: '0 16px' },
  lg: { height: '52px', fontSize: '15px', padding: '0 20px' },
};

const baseInputStyle: React.CSSProperties = {
  borderColor: 'var(--border)',
  boxShadow: 'none',
};

const focusedInputStyle: React.CSSProperties = {
  borderColor: 'var(--accent)',
  boxShadow: '0 0 0 3px rgba(124, 58, 237, 0.15)',
};

/**
 * AI Native 输入框组件
 * 暗色背景 + 紫色焦点边框
 */
const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ prefixIcon, suffixIcon, inputSize = 'md', fullWidth = true, style, className = '', onFocus, onBlur, ...rest }, ref) => {
    const [focused, setFocused] = useState(false);
    const sz = sizeMap[inputSize];

    const focusStyle = focused ? focusedInputStyle : baseInputStyle;

    return (
      <div
        className={`ui-input-wrapper ${className}`}
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          width: fullWidth ? '100%' : 'auto',
        }}
      >
        {prefixIcon && (
          <span
            style={{
              position: 'absolute',
              left: '14px',
              display: 'flex',
              alignItems: 'center',
              color: 'var(--text-muted)',
              pointerEvents: 'none',
              zIndex: 1,
            }}
          >
            {prefixIcon}
          </span>
        )}
        <input
          ref={ref}
          style={{
            width: '100%',
            height: sz.height,
            fontSize: sz.fontSize,
            padding: sz.padding,
            paddingLeft: prefixIcon ? '42px' : undefined,
            paddingRight: suffixIcon ? '42px' : undefined,
            background: 'var(--bg-input)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-sans)',
            outline: 'none',
            transition: 'border-color 150ms ease, box-shadow 150ms ease',
            ...focusStyle,
            ...style,
          }}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
          {...rest}
        />
        {suffixIcon && (
          <span
            style={{
              position: 'absolute',
              right: '14px',
              display: 'flex',
              alignItems: 'center',
              color: 'var(--text-muted)',
              cursor: 'pointer',
            }}
          >
            {suffixIcon}
          </span>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
export default Input;
