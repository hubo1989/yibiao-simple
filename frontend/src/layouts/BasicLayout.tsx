import React, { useState, useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { ProLayout } from '@ant-design/pro-components';
import { 
  ProjectOutlined, 
  SettingOutlined, 
  ReadOutlined,
  PictureOutlined,
  LogoutOutlined,
  UserOutlined,
  FolderOpenOutlined,
  FileTextOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import { Dropdown } from 'antd';
import { useAuth } from '../contexts/AuthContext';
import type { LayoutHeaderConfig, LayoutHeaderOutletContext } from './layoutHeader';

const BasicLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [pathname, setPathname] = useState(location.pathname);
  const [layoutHeader, setLayoutHeader] = useState<LayoutHeaderConfig | null>(null);

  useEffect(() => {
    setPathname(location.pathname);
  }, [location.pathname]);

  const menuData = [
    {
      path: '/',
      name: '工作台',
      icon: <ProjectOutlined />,
    },
    {
      path: '/projects',
      name: '标书管理',
      icon: <FolderOpenOutlined />,
    },
    {
      path: '/knowledge',
      name: '知识库管理',
      icon: <ReadOutlined />,
    },
    {
      path: '/materials',
      name: '素材库',
      icon: <PictureOutlined />,
    },
    {
      path: '/templates',
      name: '导出模板',
      icon: <FileTextOutlined />,
    },
    {
      path: '/knowledge-library',
      name: '章节模板库',
      icon: <DatabaseOutlined />,
    },
    ...(user?.role === 'admin' ? [{
      path: '/admin',
      name: '系统设置',
      icon: <SettingOutlined />,
    }] : []),
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const outletContext: LayoutHeaderOutletContext = {
    setLayoutHeader,
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <ProLayout
        title="拉卡拉标书智能体"
        logo={false}
        layout="mix"
        navTheme="light"
        fixSiderbar
        fixedHeader
        location={{
          pathname,
        }}
        route={{
          routes: menuData,
        }}
        menuItemRender={(item, dom) => (
          <div
            onClick={(e) => {
              e.preventDefault();
              setPathname(item.path || '/');
              navigate(item.path || '/');
            }}
          >
            {dom}
          </div>
        )}
        headerTitleRender={() => (
          <div style={{ display: 'inline-flex', alignItems: 'center' }}>
            <img
              src="/lakala_logo.png"
              alt="拉卡拉标书智能体"
              style={{ height: 32, width: 'auto', objectFit: 'contain' }}
            />
          </div>
        )}
        headerContentRender={() => (
          layoutHeader ? (
            <div style={{ width: '100%', minWidth: 0, paddingRight: 12 }}>
              {layoutHeader.content}
            </div>
          ) : null
        )}
        avatarProps={{
          src: 'https://gw.alipayobjects.com/zos/antfincdn/efFD%24IOql2/weixintupian_20170331104822.jpg',
          title: user?.username || 'User',
          size: 'small',
          render: (props, dom) => {
            return (
              <Dropdown
                menu={{
                  items: [
                    {
                      key: 'profile',
                      icon: <UserOutlined />,
                      label: '个人设置',
                    },
                    {
                      key: 'logout',
                      icon: <LogoutOutlined />,
                      label: '退出登录',
                      onClick: handleLogout,
                    },
                  ],
                }}
              >
                {dom}
              </Dropdown>
            );
          },
        }}
      >
        <>
          {layoutHeader?.subContent ? (
            <div style={{ backgroundColor: '#fff', borderBottom: '1px solid #e5e7eb' }}>
              <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 24px' }}>
                {layoutHeader.subContent}
              </div>
            </div>
          ) : null}
          <Outlet context={outletContext} />
        </>
      </ProLayout>
    </div>
  );
};

export default BasicLayout;
