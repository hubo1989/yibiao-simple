import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

const mockAuthState = {
  isAuthenticated: false,
  isLoading: false,
  user: null,
};

jest.mock('./contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => mockAuthState,
}));

jest.mock('./pages/Login', () => () => <h1>Mock Login Page</h1>);
jest.mock('./pages/Register', () => () => <h1>Mock Register Page</h1>);
jest.mock('./pages/ProjectList', () => () => <div>Mock Project List</div>);
jest.mock('./pages/ProjectWorkspace', () => () => <div>Mock Project Workspace</div>);
jest.mock('./pages/ProjectSettings', () => () => <div>Mock Project Settings</div>);
jest.mock('./pages/BidReview', () => () => <div>Mock Bid Review</div>);
jest.mock('./pages/Admin', () => () => <div>Mock Admin</div>);
jest.mock('./pages/KnowledgeBase', () => () => <div>Mock Knowledge Base</div>);
jest.mock('./pages/ProjectManager', () => () => <div>Mock Project Manager</div>);
jest.mock('./pages/RequestLogs', () => () => <div>Mock Request Logs</div>);
jest.mock('./layouts/BasicLayout', () => () => <div>Mock Basic Layout</div>);

describe('App routing', () => {
  let consoleWarnSpy: jest.SpyInstance;
  const originalWarn = console.warn;

  beforeEach(() => {
    mockAuthState.isAuthenticated = false;
    mockAuthState.isLoading = false;
    mockAuthState.user = null;
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

  it('redirects unauthenticated users from the home route to login', async () => {
    window.history.pushState({}, '', '/');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Mock Login Page' })).toBeInTheDocument();
  });

  it('renders the register route directly', async () => {
    window.history.pushState({}, '', '/register');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Mock Register Page' })).toBeInTheDocument();
  });

  it('redirects unknown routes through the protected home route back to login', async () => {
    window.history.pushState({}, '', '/unknown');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Mock Login Page' })).toBeInTheDocument();
  });
});
