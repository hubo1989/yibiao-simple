import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';
import { ThemeProvider, THEME_STORAGE_KEY } from './contexts/ThemeContext';

const mockAuthState = {
  isAuthenticated: false,
  isLoading: false,
  user: null,
};

const mockConfigProvider = jest.fn();

jest.mock('./contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => mockAuthState,
}));

jest.mock('antd', () => {
  const actual = jest.requireActual('antd');

  return {
    ...actual,
    ConfigProvider: ({ children, theme: antdTheme }: { children: React.ReactNode; theme?: any }) => {
      mockConfigProvider({ children, theme: antdTheme });
      return (
        <div
          data-testid="antd-config-provider"
          data-algorithm={antdTheme?.algorithm === actual.theme.defaultAlgorithm ? 'light' : 'dark'}
          data-color-primary={antdTheme?.token?.colorPrimary}
          data-color-bg-container={antdTheme?.token?.colorBgContainer}
        >
          {children}
        </div>
      );
    },
  };
});

jest.mock('./pages/Login', () => ({
  __esModule: true,
  default: () => <h1>Mock Login Page</h1>,
}));
jest.mock('./pages/Register', () => ({
  __esModule: true,
  default: () => <h1>Mock Register Page</h1>,
}));
jest.mock('./pages/ProjectList', () => ({
  __esModule: true,
  default: () => <div>Mock Project List</div>,
}));
jest.mock('./pages/ProjectWorkspace', () => ({
  __esModule: true,
  default: () => <div>Mock Project Workspace</div>,
}));
jest.mock('./pages/ProjectSettings', () => ({
  __esModule: true,
  default: () => <div>Mock Project Settings</div>,
}));
jest.mock('./pages/BidReview', () => ({
  __esModule: true,
  default: () => <div>Mock Bid Review</div>,
}));
jest.mock('./pages/Admin', () => ({
  __esModule: true,
  default: () => <div>Mock Admin</div>,
}));
jest.mock('./pages/KnowledgeBase', () => ({
  __esModule: true,
  default: () => <div>Mock Knowledge Base</div>,
}));
jest.mock('./pages/ProjectManager', () => ({
  __esModule: true,
  default: () => <div>Mock Project Manager</div>,
}));
jest.mock('./pages/RequestLogs', () => ({
  __esModule: true,
  default: () => <div>Mock Request Logs</div>,
}));
jest.mock('./layouts/BasicLayout', () => ({
  __esModule: true,
  default: () => <div>Mock Basic Layout</div>,
}));

describe('App routing', () => {
  let consoleWarnSpy: jest.SpyInstance;
  const originalWarn = console.warn;

  const renderApp = () => render(
    <ThemeProvider>
      <App />
    </ThemeProvider>,
  );

  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    mockAuthState.isAuthenticated = false;
    mockAuthState.isLoading = false;
    mockAuthState.user = null;
    mockConfigProvider.mockClear();
    consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation((message?: any, ...args: any[]) => {
      if (typeof message === 'string' && message.includes('React Router Future Flag Warning')) {
        return;
      }
      originalWarn(message, ...args);
    });
  });

  afterEach(() => {
    consoleWarnSpy.mockRestore();
  });

  it('uses the active theme mode when configuring Ant Design', async () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light');
    window.history.pushState({}, '', '/');

    renderApp();
    expect(await screen.findByTestId('antd-config-provider')).toHaveAttribute('data-algorithm', 'light');
    expect(screen.getByTestId('antd-config-provider')).toHaveAttribute('data-color-primary', 'var(--accent)');
    expect(screen.getByTestId('antd-config-provider')).toHaveAttribute('data-color-bg-container', 'var(--bg-surface)');
  });

  it('redirects unauthenticated users from the home route to login', async () => {
    window.history.pushState({}, '', '/');

    renderApp();

    expect(await screen.findByRole('heading', { name: 'Mock Login Page' })).toBeInTheDocument();
  });

  it('renders the register route directly', async () => {
    window.history.pushState({}, '', '/register');

    renderApp();

    expect(await screen.findByRole('heading', { name: 'Mock Register Page' })).toBeInTheDocument();
  });

  it('redirects unknown routes through the protected home route back to login', async () => {
    window.history.pushState({}, '', '/unknown');

    renderApp();

    expect(await screen.findByRole('heading', { name: 'Mock Login Page' })).toBeInTheDocument();
  });
});
