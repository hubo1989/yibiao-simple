import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { ThemeProvider, ThemeToggle, useTheme, THEME_STORAGE_KEY } from './ThemeContext';

function ThemeStateProbe() {
  const { theme, isDark } = useTheme();

  return (
    <div>
      <div data-testid="theme-value">{theme}</div>
      <div data-testid="theme-mode">{isDark ? 'dark' : 'light'}</div>
    </div>
  );
}

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('defaults to dark theme and syncs the root data-theme attribute', () => {
    render(
      <ThemeProvider>
        <ThemeStateProbe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId('theme-value')).toHaveTextContent('dark');
    expect(screen.getByTestId('theme-mode')).toHaveTextContent('dark');
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  it('hydrates the saved theme preference from localStorage', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light');

    render(
      <ThemeProvider>
        <ThemeStateProbe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId('theme-value')).toHaveTextContent('light');
    expect(screen.getByTestId('theme-mode')).toHaveTextContent('light');
    expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  });

  it('toggles theme mode and persists the new choice', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
        <ThemeStateProbe />
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: '切换到浅色主题' }));

    expect(screen.getByTestId('theme-value')).toHaveTextContent('light');
    expect(screen.getByTestId('theme-mode')).toHaveTextContent('light');
    expect(document.documentElement).toHaveAttribute('data-theme', 'light');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });
});
