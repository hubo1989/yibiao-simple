import React from 'react';
import { Link } from 'react-router-dom';
import { CheckCircleFilled, RocketOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { Typography } from 'antd';

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
  {
    icon: <RocketOutlined style={{ color: '#1677ff', fontSize: 20 }} />,
    title: '更快进入项目现场',
    description: '从招标文件解析到目录生成与正文协作，流程被压缩到一个工作台中。',
  },
  {
    icon: <SafetyCertificateOutlined style={{ color: '#13c2c2', fontSize: 20 }} />,
    title: '更稳的企业级协作',
    description: '版本、权限与日志放在同一套系统里，减少线下补救和信息漂移。',
  },
  {
    icon: <CheckCircleFilled style={{ color: '#52c41a', fontSize: 20 }} />,
    title: '更清晰的交付节奏',
    description: '把分析、编目、审核和回溯分层展示，团队更容易把握当前状态。',
  },
];

const panelStyle: React.CSSProperties = {
  background: 'rgba(255, 255, 255, 0.84)',
  backdropFilter: 'blur(18px)',
  border: '1px solid rgba(15, 23, 42, 0.08)',
  borderRadius: 28,
  boxShadow: '0 24px 80px rgba(15, 23, 42, 0.10)',
};

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
        padding: '32px 24px',
        background:
          'radial-gradient(circle at top left, rgba(22,119,255,0.14), transparent 26%), radial-gradient(circle at bottom right, rgba(19,194,194,0.16), transparent 28%), linear-gradient(135deg, #f5f7fb 0%, #eef3f8 100%)',
      }}
    >
      <div
        style={{
          maxWidth: 1240,
          margin: '0 auto',
          minHeight: 'calc(100vh - 64px)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 24,
          alignItems: 'stretch',
        }}
      >
        <section
          style={{
            ...panelStyle,
            flex: '1 1 560px',
            padding: '40px clamp(24px, 4vw, 48px)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            background:
              'linear-gradient(160deg, rgba(255,255,255,0.96) 0%, rgba(245,249,255,0.88) 54%, rgba(236,247,255,0.92) 100%)',
          }}
        >
          <div>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 14px',
                borderRadius: 999,
                background: 'rgba(22, 119, 255, 0.08)',
                color: '#0958d9',
                fontSize: 13,
                fontWeight: 600,
                letterSpacing: 0.2,
              }}
            >
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #1677ff 0%, #13c2c2 100%)',
                  boxShadow: '0 0 0 6px rgba(22, 119, 255, 0.10)',
                }}
              />
              {eyebrow}
            </div>

            <Typography.Title
              level={1}
              style={{
                marginTop: 28,
                marginBottom: 12,
                fontSize: 'clamp(34px, 5vw, 56px)',
                lineHeight: 1.05,
                letterSpacing: '-0.04em',
                color: '#0f172a',
              }}
            >
              {title}
            </Typography.Title>

            <Typography.Paragraph
              style={{
                maxWidth: 560,
                marginBottom: 0,
                fontSize: 18,
                lineHeight: 1.75,
                color: 'rgba(15, 23, 42, 0.70)',
              }}
            >
              {subtitle}
            </Typography.Paragraph>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 16,
              marginTop: 32,
            }}
          >
            {featureItems.map((item) => (
              <div
                key={item.title}
                style={{
                  padding: 20,
                  borderRadius: 22,
                  border: '1px solid rgba(15, 23, 42, 0.08)',
                  background: 'rgba(255,255,255,0.72)',
                }}
              >
                <div style={{ marginBottom: 14 }}>{item.icon}</div>
                <Typography.Title level={5} style={{ marginBottom: 8, color: '#0f172a' }}>
                  {item.title}
                </Typography.Title>
                <Typography.Paragraph style={{ marginBottom: 0, color: 'rgba(15, 23, 42, 0.62)' }}>
                  {item.description}
                </Typography.Paragraph>
              </div>
            ))}
          </div>
        </section>

        <section
          style={{
            ...panelStyle,
            flex: '1 1 420px',
            maxWidth: 520,
            minWidth: 320,
            padding: '36px clamp(22px, 4vw, 40px)',
            marginLeft: 'auto',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
          }}
        >
          <div style={{ marginBottom: 24 }}>
            <Typography.Text
              style={{
                display: 'block',
                marginBottom: 8,
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
                color: '#1677ff',
              }}
            >
              拉卡拉标书智能体
            </Typography.Text>
            <Typography.Title level={2} style={{ marginBottom: 8, color: '#0f172a' }}>
              {formTitle}
            </Typography.Title>
            <Typography.Paragraph style={{ marginBottom: 0, color: 'rgba(15, 23, 42, 0.62)' }}>
              {formDescription}
            </Typography.Paragraph>
          </div>

          <div>{children}</div>

          <div
            style={{
              marginTop: 24,
              paddingTop: 20,
              borderTop: '1px solid rgba(15, 23, 42, 0.08)',
              display: 'flex',
              justifyContent: 'space-between',
              gap: 12,
              alignItems: 'center',
              flexWrap: 'wrap',
            }}
          >
            <Typography.Text style={{ color: 'rgba(15, 23, 42, 0.62)' }}>
              {footerPrompt}
            </Typography.Text>
            <Link to={footerActionTo} style={{ color: '#1677ff', fontWeight: 600 }}>
              {footerActionLabel}
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
};

export default AuthShell;
