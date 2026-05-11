/**
 * AppShell — AI Native 全局布局
 * 替代 ProLayout，提供极简导航 + 暗色主题
 */
import React, { useState, useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Dropdown } from 'antd';
import {
  ProjectOutlined,
  DashboardOutlined,
  SettingOutlined,
  ReadOutlined,
  PictureOutlined,
  LogoutOutlined,
  UserOutlined,
  FolderOpenOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  SearchOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { SparkleIcon } from '../components/ui/AIElements';
import type { LayoutHeaderConfig, LayoutHeaderOutletContext } from './layoutHeader';

/* ─── 菜单定义 ─── */
interface MenuItem {
  path: string;
  name: string;
  icon: React.ReactNode;
  adminOnly?: boolean;
}

const menuItems: MenuItem[] = [
  { path: '/', name: '工作台', icon: <ProjectOutlined /> },
  { path: '/dashboard', name: '进度看板', icon: <DashboardOutlined /> },
  { path: '/projects', name: '标书管理', icon: <FolderOpenOutlined /> },
  { path: '/knowledge', name: '知识库', icon: <ReadOutlined /> },
  { path: '/materials', name: '素材库', icon: <PictureOutlined /> },
  { path: '/templates', name: '导出模板', icon: <FileTextOutlined /> },
  { path: '/knowledge-library', name: '章节模板', icon: <DatabaseOutlined /> },
  { path: '/admin', name: '系统设置', icon: <SettingOutlined />, adminOnly: true },
];

const AppShell: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [layoutHeader, setLayoutHeader] = useState<LayoutHeaderConfig | null>(null);

  /* 在项目工作区页面自动折叠侧边栏 */
  const isProjectPage = location.pathname.match(/^\/project\//);

  const filteredMenu = menuItems.filter((item) => {
    if (item.adminOnly && user?.role !== 'admin') return false;
    return true;
  });

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const outletContext: LayoutHeaderOutletContext = {
    setLayoutHeader,
  };

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        background: 'var(--bg-primary)',
        overflow: 'hidden',
      }}
    >
      {/* ─── 左侧导航 ─── */}
      {!isProjectPage && (
        <aside
          style={{
            width: sidebarCollapsed ? 64 : 220,
            background: 'var(--bg-surface)',
            borderRight: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            transition: 'width 200ms cubic-bezier(0.16, 1, 0.3, 1)',
            flexShrink: 0,
            zIndex: 10,
          }}
        >
          {/* Logo */}
          <div
            style={{
              height: 56,
              display: 'flex',
              alignItems: 'center',
              padding: '0 16px',
              gap: 10,
              borderBottom: '1px solid var(--border-subtle)',
              cursor: 'pointer',
            }}
            onClick={() => navigate('/')}
          >
            <SparkleIcon size={22} color="var(--accent)" />
            {!sidebarCollapsed && (
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                  whiteSpace: 'nowrap',
                }}
              >
                易标AI
              </span>
            )}
          </div>

          {/* 菜单 */}
          <nav style={{ flex: 1, padding: '8px', overflowY: 'auto' }}>
            {filteredMenu.map((item) => {
              const active = location.pathname === item.path ||
                (item.path !== '/' && location.pathname.startsWith(item.path));
              const isHome = item.path === '/' && location.pathname === '/';

              return (
                <div
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: sidebarCollapsed ? '10px' : '10px 12px',
                    borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer',
                    marginBottom: 2,
                    background: (active || isHome) ? 'var(--bg-hover)' : 'transparent',
                    color: (active || isHome) ? 'var(--accent-light)' : 'var(--text-secondary)',
                    transition: 'all 150ms ease',
                    justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                    fontSize: 14,
                  }}
                  title={sidebarCollapsed ? item.name : undefined}
                  onMouseEnter={(e) => {
                    if (!active && !isHome) {
                      e.currentTarget.style.background = 'var(--bg-hover)';
                      e.currentTarget.style.color = 'var(--text-primary)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active && !isHome) {
                      e.currentTarget.style.background = 'transparent';
                      e.currentTarget.style.color = 'var(--text-secondary)';
                    }
                  }}
                >
                  <span style={{ fontSize: 16, display: 'flex', alignItems: 'center' }}>
                    {item.icon}
                  </span>
                  {!sidebarCollapsed && <span>{item.name}</span>}
                </div>
              );
            })}
          </nav>

          {/* 底部折叠按钮 */}
          <div
            style={{
              padding: '12px',
              borderTop: '1px solid var(--border-subtle)',
              display: 'flex',
              justifyContent: sidebarCollapsed ? 'center' : 'flex-end',
            }}
          >
            <div
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              style={{
                cursor: 'pointer',
                color: 'var(--text-muted)',
                padding: '4px',
                borderRadius: 'var(--radius-xs)',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </div>
          </div>
        </aside>
      )}

      {/* ─── 右侧内容区 ─── */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          overflow: 'hidden',
        }}
      >
        {/* 顶部导航栏 */}
        <header
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg-surface)',
            flexShrink: 0,
            gap: 16,
          }}
        >
          {/* 左侧：自定义 header content */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {layoutHeader?.content || (
              isProjectPage && (
                <div
                  onClick={() => navigate('/')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    cursor: 'pointer',
                    color: 'var(--text-secondary)',
                    fontSize: 14,
                  }}
                >
                  <SparkleIcon size={18} color="var(--accent)" />
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>易标AI</span>
                </div>
              )
            )}
          </div>

          {/* 中间：搜索 */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 16px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border)',
              background: 'var(--bg-input)',
              color: 'var(--text-muted)',
              fontSize: 13,
              cursor: 'pointer',
              minWidth: 200,
              maxWidth: 360,
            }}
          >
            <SearchOutlined style={{ fontSize: 14 }} />
            <span>搜索...</span>
            <span
              style={{
                marginLeft: 'auto',
                padding: '2px 6px',
                borderRadius: 4,
                background: 'var(--bg-elevated)',
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
              }}
            >
              ⌘K
            </span>
          </div>

          {/* 右侧：用户 */}
          <Dropdown
            menu={{
              items: [
                { key: 'profile', icon: <UserOutlined />, label: '个人设置' },
                { type: 'divider' as const },
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出登录',
                  onClick: handleLogout,
                },
              ],
            }}
            placement="bottomRight"
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: 'pointer',
                padding: '4px 8px',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  background: 'var(--accent-grad)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {user?.username?.charAt(0).toUpperCase() || 'U'}
              </div>
              <span
                style={{
                  color: 'var(--text-secondary)',
                  fontSize: 13,
                  fontWeight: 500,
                }}
              >
                {user?.username || 'User'}
              </span>
            </div>
          </Dropdown>
        </header>

        {/* subContent 区域 */}
        {layoutHeader?.subContent && (
          <div
            style={{
              borderBottom: '1px solid var(--border)',
              background: 'var(--bg-surface)',
            }}
          >
            <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 24px' }}>
              {layoutHeader.subContent}
            </div>
          </div>
        )}

        {/* 内容区 */}
        <main
          style={{
            flex: 1,
            overflow: 'auto',
            background: 'var(--bg-primary)',
          }}
        >
          <Outlet context={outletContext} />
        </main>
      </div>
    </div>
  );
};

export default AppShell;
