/**
 * 主应用组件
 */
import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const ProjectList = lazy(() => import('./pages/ProjectList'));
const ProjectWorkspace = lazy(() => import('./pages/ProjectWorkspace'));
const ProjectSettings = lazy(() => import('./pages/ProjectSettings'));
const BidReview = lazy(() => import('./pages/BidReview'));
const Admin = lazy(() => import('./pages/Admin'));
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase'));
const MaterialLibrary = lazy(() => import('./pages/MaterialLibrary'));
const ProjectManager = lazy(() => import('./pages/ProjectManager'));
const RequestLogs = lazy(() => import('./pages/RequestLogs'));
const AppShell = lazy(() => import('./layouts/AppShell'));
const TemplateManage = lazy(() => import('./pages/TemplateManage'));
const KnowledgeLibrary = lazy(() => import('./pages/KnowledgeLibrary'));

/* AI Native 全屏加载 */
const routeFallback = (
  <div
    style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#0f0d15',
      gap: 16,
    }}
  >
    <div className="ai-thinking-dots" style={{ transform: 'scale(2)' }}>
      <span /><span /><span />
    </div>
    <span style={{ color: '#8b85a0', fontSize: 14 }}>正在加载...</span>
  </div>
);

/* Ant Design 暗色主题配置 */
const antdDarkTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#7c3aed',
    colorBgContainer: '#1a1825',
    colorBgElevated: '#231f35',
    colorBorder: '#2a2640',
    colorText: '#f1f0f5',
    colorTextSecondary: '#8b85a0',
    borderRadius: 12,
    fontFamily: 'Inter, -apple-system, PingFang SC, Noto Sans SC, sans-serif',
  },
};

function App() {
  return (
    <ConfigProvider theme={antdDarkTheme}>
      <AuthProvider>
        <BrowserRouter>
          <Suspense fallback={routeFallback}>
            <Routes>
              {/* 公开路由 */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />

              {/* 受保护的路由 — 使用新 AppShell */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <AppShell />
                  </ProtectedRoute>
                }
              >
                <Route index element={<ProjectList />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="project/:projectId" element={<ProjectWorkspace />} />
                <Route path="project/:projectId/settings" element={<ProjectSettings />} />
                <Route path="project/:projectId/review" element={<BidReview />} />
                
                {/* 管理员专用路由 */}
                <Route
                  path="admin"
                  element={
                    <ProtectedRoute allowedRoles={['admin']}>
                      <Admin />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="admin/request-logs"
                  element={
                    <ProtectedRoute allowedRoles={['admin']}>
                      <RequestLogs />
                    </ProtectedRoute>
                  }
                />

                {/* 标书项目管理 */}
                <Route path="projects" element={<ProjectManager />} />

                {/* 知识库管理 */}
                <Route path="knowledge" element={<KnowledgeBase />} />
                <Route path="materials" element={<MaterialLibrary />} />

                {/* 导出模板管理 */}
                <Route path="templates" element={<TemplateManage />} />

                {/* 标书知识库 */}
                <Route path="knowledge-library" element={<KnowledgeLibrary />} />
              </Route>

              {/* 默认重定向 */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ConfigProvider>
  );
}

export default App;
