/**
 * 主应用组件
 */
import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const ProjectList = lazy(() => import('./pages/ProjectList'));
const ProjectWorkspace = lazy(() => import('./pages/ProjectWorkspace'));
const ProjectSettings = lazy(() => import('./pages/ProjectSettings'));
const BidReview = lazy(() => import('./pages/BidReview'));
const Admin = lazy(() => import('./pages/Admin'));
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase'));
const MaterialLibrary = lazy(() => import('./pages/MaterialLibrary'));
const ProjectManager = lazy(() => import('./pages/ProjectManager'));
const RequestLogs = lazy(() => import('./pages/RequestLogs'));
const BasicLayout = lazy(() => import('./layouts/BasicLayout'));
const TemplateManage = lazy(() => import('./pages/TemplateManage'));
const KnowledgeLibrary = lazy(() => import('./pages/KnowledgeLibrary'));

const routeFallback = (
  <div
    style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #f5f7fb 0%, #eef3f8 100%)',
    }}
  >
    <Spin size="large" fullscreen tip="正在加载页面..." />
  </div>
);

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={routeFallback}>
          <Routes>
            {/* 公开路由 */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* 受保护的路由 */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <BasicLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<ProjectList />} />
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
  );
}

export default App;
