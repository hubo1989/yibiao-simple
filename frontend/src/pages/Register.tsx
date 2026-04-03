/**
 * 注册页面
 */
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LockOutlined, MailOutlined, UserOutlined } from '@ant-design/icons';
import { Alert, Button, Form, Input, Typography } from 'antd';
import { useAuth } from '../contexts/AuthContext';
import type { RegisterRequest } from '../types/auth';
import AuthShell from '../components/AuthShell';
import type { ApiError } from '../utils/error';

export default function Register(): React.ReactElement {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [error, setError] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (values: RegisterRequest & { confirmPassword: string }) => {
    setError('');
    setIsLoading(true);

    try {
      await register({
        username: values.username,
        email: values.email,
        password: values.password,
      });
      navigate('/');
    } catch (err: unknown) {
      const detail = (err as ApiError)?.response?.data;
      let message: string;
      if (Array.isArray(detail)) {
        // Pydantic 验证错误数组
        message = detail.map((e: { msg: string }) => e.msg).join('；');
      } else if (typeof detail === 'string') {
        message = detail;
      } else {
        message = '注册失败，请稍后重试';
      }
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell
      eyebrow="团队接入"
      title="把新成员接进来，也保持统一的权限与交付节奏。"
      subtitle="注册入口现在与登录页统一为同一套企业工作区风格，避免用户在认证链路里出现体验断层。"
      formTitle="创建账户"
      formDescription="填写基础信息后即可进入拉卡拉标书智能体工作区。密码强度与确认逻辑会在提交前校验。"
      footerPrompt="已经有账户？"
      footerActionLabel="返回登录"
      footerActionTo="/login"
    >
      <Form layout="vertical" onFinish={handleSubmit} requiredMark={false} size="large">
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
          rules={[
            { required: true, message: '请输入用户名' },
            { min: 2, message: '用户名至少需要 2 个字符' },
          ]}
        >
          <Input prefix={<UserOutlined />} placeholder="请输入用户名" autoComplete="username" />
        </Form.Item>

        <Form.Item
          label="邮箱地址"
          name="email"
          rules={[
            { required: true, message: '请输入邮箱地址' },
            { type: 'email', message: '请输入有效的邮箱地址' },
          ]}
        >
          <Input prefix={<MailOutlined />} placeholder="请输入邮箱地址" autoComplete="email" />
        </Form.Item>

        <Form.Item
          label="密码"
          name="password"
          rules={[
            { required: true, message: '请输入密码' },
            { min: 8, message: '密码至少需要 8 个字符' },
          ]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="请输入密码（至少 8 个字符）" autoComplete="new-password" />
        </Form.Item>

        <Form.Item
          label="确认密码"
          name="confirmPassword"
          dependencies={['password']}
          rules={[
            { required: true, message: '请再次输入密码' },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue('password') === value) {
                  return Promise.resolve();
                }
                return Promise.reject(new Error('两次输入的密码不一致'));
              },
            }),
          ]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="请再次输入密码" autoComplete="new-password" />
        </Form.Item>

        <Button type="primary" htmlType="submit" block loading={isLoading} style={{ height: 48, borderRadius: 14 }}>
          注册并进入工作区
        </Button>

        <Typography.Paragraph style={{ marginTop: 16, marginBottom: 0, color: 'rgba(15, 23, 42, 0.58)' }}>
          完成注册即表示你同意团队的使用规范；如果这是受邀协作项目，也可以直接返回
          <Link to="/login" style={{ marginLeft: 4 }}>
            登录页
          </Link>
          使用已有账号进入。
        </Typography.Paragraph>
      </Form>
    </AuthShell>
  );
}
