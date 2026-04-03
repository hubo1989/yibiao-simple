/**
 * 登录页面
 */
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { Alert, Button, Checkbox, Form, Input, Typography, message } from 'antd';
import { useAuth } from '../contexts/AuthContext';
import AuthShell from '../components/AuthShell';
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
      eyebrow="投标协作中台"
      title="让标书编写从堆任务，变成可追踪的生产流程。"
      subtitle="拉卡拉标书智能体将文档解析、目录编制、正文协作与审核回溯聚合在同一个企业级工作区里，减少重复沟通与版本失控。"
      formTitle="登录工作区"
      formDescription="使用你的正式账户进入系统。当前页面不再展示误导性的演示账号占位信息。"
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
            style={{ marginBottom: 20, borderRadius: 14 }}
            message={error}
            type="error"
            showIcon
          />
        ) : null}

        <Form.Item
          label="用户名"
          name="username"
          rules={[{ required: true, message: '请输入用户名' }]}
        >
          <Input prefix={<UserOutlined />} placeholder="请输入用户名" autoComplete="username" />
        </Form.Item>

        <Form.Item
          label="密码"
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
            <Checkbox>自动登录</Checkbox>
          </Form.Item>

          <Button
            type="link"
            style={{ paddingInline: 0 }}
            onClick={() => message.info('忘记密码功能开发中，请联系管理员处理。')}
          >
            忘记密码？
          </Button>
        </div>

        <Button type="primary" htmlType="submit" block loading={isSubmitting} style={{ height: 48, borderRadius: 14 }}>
          登录
        </Button>

        <Typography.Paragraph style={{ marginTop: 16, marginBottom: 0, color: 'rgba(15, 23, 42, 0.58)' }}>
          如需开通测试或正式账号，请联系系统管理员；若你已有邀请链接，也可直接前往
          <Link to="/register" style={{ marginLeft: 4 }}>
            注册页
          </Link>
          。
        </Typography.Paragraph>
      </Form>
    </AuthShell>
  );
}
