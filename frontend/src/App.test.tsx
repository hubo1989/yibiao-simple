import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import App from './App';

// Mock axios
jest.mock('axios', () => ({
  create: jest.fn(() => ({
    defaults: { headers: { common: {} } },
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
    get: jest.fn(),
    post: jest.fn(),
  })),
}));

// Mock react-markdown
jest.mock('react-markdown', () => {
  return function MockReactMarkdown({ children }: { children: React.ReactNode }) {
    return <div data-testid="mock-markdown">{children}</div>;
  };
});

// Mock rehype-highlight
jest.mock('rehype-highlight', () => () => null);

describe('App', () => {
  it('renders login page when not authenticated', async () => {
    render(<App />);

    // Since user is not authenticated, should show login page
    await waitFor(() => {
      // Use getByRole for the heading
      expect(screen.getByRole('heading', { name: /登录 AI 写标书助手/i })).toBeInTheDocument();
    });
  });

  it('shows register link on login page', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /注册新账户/i })).toBeInTheDocument();
    });
  });

  it('shows login button', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^登录$/i })).toBeInTheDocument();
    });
  });
});
