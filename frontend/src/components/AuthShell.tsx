/**
 * AuthShell — AI Native 认证页外壳
 * 暗色左右分栏：左侧品牌区 + 右侧表单
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { SparkleIcon } from './ui/AIElements';

interface AuthShellProps {
  eyebrow: string;
  title: string;
  subtitle: string;
  formTitle: string;
  formDescription: string;
  footerPrompt: string;
  footerActionLabel: string;
  footerActionTo: string;
  children: React.ReactNode;
}

const featureItems = [
  { icon: '✦', label: '智能解析' },
  { icon: '✦', label: '自动生成' },
  { icon: '✦', label: '一致性校验' },
];

const AuthShell: React.FC<AuthShellProps> = ({
  eyebrow,
  title,
  subtitle,
  formTitle,
  formDescription,
  footerPrompt,
  footerActionLabel,
  footerActionTo,
  children,
}) => {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        background: 'var(--bg-primary)',
      }}
    >
      {/* ─── 左侧品牌区 ─── */}
      <div
        className="bg-aurora"
        style={{
          flex: '1 1 55%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          padding: '64px clamp(40px, 6vw, 80px)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* 背景装饰 */}
        <div
          style={{
            position: 'absolute',
            top: '20%',
            right: '-5%',
            width: 400,
            height: 400,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(124,58,237,0.15) 0%, transparent 70%)',
            filter: 'blur(60px)',
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: '10%',
            left: '10%',
            width: 300,
            height: 300,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)',
            filter: 'blur(50px)',
            pointerEvents: 'none',
          }}
        />

        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 80 }}>
          <SparkleIcon size={28} color="var(--accent-light)" />
          <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>
            易标AI
          </span>
        </div>

        {/* 标语 */}
        <h1
          style={{
            fontSize: 'clamp(36px, 5vw, 56px)',
            fontWeight: 800,
            lineHeight: 1.1,
            letterSpacing: '-0.03em',
            color: 'var(--text-primary)',
            margin: 0,
            maxWidth: 560,
          }}
        >
          AI 驱动的
          <br />
          <span className="text-gradient">标书协作平台</span>
        </h1>

        <p
          style={{
            fontSize: 18,
            lineHeight: 1.6,
            color: 'var(--text-secondary)',
            maxWidth: 480,
            marginTop: 20,
            marginBottom: 40,
          }}
        >
          {subtitle}
        </p>

        {/* Feature pills */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {featureItems.map((item) => (
            <span
              key={item.label}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 16px',
                borderRadius: '9999px',
                background: 'rgba(124, 58, 237, 0.1)',
                border: '1px solid rgba(124, 58, 237, 0.2)',
                color: 'var(--accent-light)',
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              <span style={{ color: 'var(--accent)' }}>{item.icon}</span>
              {item.label}
            </span>
          ))}
        </div>
      </div>

      {/* ─── 右侧表单区 ─── */}
      <div
        style={{
          flex: '1 1 45%',
          maxWidth: 540,
          minWidth: 380,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          padding: '48px clamp(32px, 5vw, 60px)',
          background: 'var(--bg-surface)',
          borderLeft: '1px solid var(--border)',
        }}
      >
        {/* 表单头部 */}
        <div style={{ marginBottom: 32 }}>
          <h2
            style={{
              fontSize: 28,
              fontWeight: 700,
              color: 'var(--text-primary)',
              margin: 0,
              marginBottom: 8,
            }}
          >
            {formTitle}
          </h2>
          <p
            style={{
              fontSize: 14,
              color: 'var(--text-secondary)',
              margin: 0,
              lineHeight: 1.6,
            }}
          >
            {formDescription}
          </p>
        </div>

        {/* 表单内容 */}
        <div>{children}</div>

        {/* 底部链接 */}
        <div
          style={{
            marginTop: 32,
            paddingTop: 24,
            borderTop: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span style={{ color: 'var(--text-muted)', fontSize: 14 }}>
            {footerPrompt}
          </span>
          <Link
            to={footerActionTo}
            style={{
              color: 'var(--accent-light)',
              fontWeight: 600,
              fontSize: 14,
              textDecoration: 'none',
            }}
          >
            {footerActionLabel}
          </Link>
        </div>
      </div>
    </div>
  );
};

export default AuthShell;
