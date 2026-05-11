/**
 * 登录页面 — AI Native 暗色主题
 */
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { Alert, Checkbox, Form, Input, message } from 'antd';
import { useAuth } from '../contexts/AuthContext';
import AuthShell from '../components/AuthShell';
import UIButton from '../components/ui/Button';
import type { ApiError } from '../utils/error';

export default function Login(): React.ReactElement {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (values: { username: string; password: string }) => {
    setError('');
    setIsSubmitting(true);
    try {
      await login({
        username: values.username,
        password: values.password,
      });
      message.success('登录成功！');
      navigate('/');
    } catch (err: unknown) {
      const msg = (err as ApiError)?.response?.data?.detail || '登录失败，请检查用户名和密码';
      setError(msg);
      message.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthShell
      eyebrow="AI 标书协作"
      title="AI 驱动的标书协作平台"
      subtitle="从文档解析到内容生成，一站式智能写作工作流。"
      formTitle="登录"
      formDescription="使用你的账户进入工作区"
      footerPrompt="还没有账户？"
      footerActionLabel="创建新账户"
      footerActionTo="/register"
    >
      <Form
        layout="vertical"
        initialValues={{ autoLogin: true }}
        onFinish={handleSubmit}
        requiredMark={false}
        size="large"
      >
        {error ? (
          <Alert
            style={{ marginBottom: 20, borderRadius: 10 }}
            message={error}
            type="error"
            showIcon
          />
        ) : null}

        <Form.Item
          label={<span style={{ color: 'var(--text-secondary)' }}>用户名</span>}
          name="username"
          rules={[{ required: true, message: '请输入用户名' }]}
        >
          <Input prefix={<UserOutlined />} placeholder="请输入用户名" autoComplete="username" />
        </Form.Item>

        <Form.Item
          label={<span style={{ color: 'var(--text-secondary)' }}>密码</span>}
          name="password"
          rules={[{ required: true, message: '请输入密码' }]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" autoComplete="current-password" />
        </Form.Item>

        <div
          style={{
            marginBottom: 24,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <Form.Item name="autoLogin" valuePropName="checked" noStyle>
            <Checkbox style={{ color: 'var(--text-secondary)' }}>记住我</Checkbox>
          </Form.Item>

          <span
            style={{
              color: 'var(--accent-light)',
              cursor: 'pointer',
              fontSize: 13,
            }}
            onClick={() => message.info('忘记密码功能开发中，请联系管理员处理。')}
          >
            忘记密码？
          </span>
        </div>

        <UIButton
          variant="primary"
          size="lg"
          loading={isSubmitting}
          glow
          type="submit"
          style={{ width: '100%' }}
        >
          登 录
        </UIButton>

        <p
          style={{
            marginTop: 20,
            marginBottom: 0,
            color: 'var(--text-muted)',
            fontSize: 13,
            lineHeight: 1.6,
          }}
        >
          如需开通测试或正式账号，请联系系统管理员；若你已有邀请链接，也可直接前往
          <Link to="/register" style={{ marginLeft: 4, color: 'var(--accent-light)' }}>
            注册页
          </Link>
          。
        </p>
      </Form>
    </AuthShell>
  );
}
