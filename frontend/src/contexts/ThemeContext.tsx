/**
 * 主题上下文
 * 管理深色 / 浅色模式、持久化和根节点 data-theme 同步
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from 'react';
import { MoonOutlined, SunOutlined } from '@ant-design/icons';

export type ThemeMode = 'dark' | 'light';

interface ThemeContextValue {
  theme: ThemeMode;
  isDark: boolean;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
}

interface ThemeProviderProps {
  children: React.ReactNode;
}

interface ThemeToggleProps {
  variant?: 'full' | 'icon';
  className?: string;
  style?: React.CSSProperties;
}

export const THEME_STORAGE_KEY = 'yibiao-theme-mode';

const ThemeContext = createContext<ThemeContextValue | null>(null);

function isThemeMode(value: string | null): value is ThemeMode {
  return value === 'dark' || value === 'light';
}

export function getStoredTheme(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'dark';
  }

  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeMode(stored) ? stored : 'dark';
  } catch {
    return 'dark';
  }
}

function applyThemeToDocument(theme: ThemeMode): void {
  if (typeof document === 'undefined') {
    return;
  }

  document.documentElement.setAttribute('data-theme', theme);
}

function persistTheme(theme: ThemeMode): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // ignore storage failures
  }
}

export function ThemeProvider({ children }: ThemeProviderProps): React.ReactElement {
  const [theme, setThemeState] = useState<ThemeMode>(() => getStoredTheme());

  useLayoutEffect(() => {
    applyThemeToDocument(theme);
  }, [theme]);

  useEffect(() => {
    persistTheme(theme);
  }, [theme]);

  const setTheme = useCallback((nextTheme: ThemeMode) => {
    setThemeState(nextTheme);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((current) => (current === 'dark' ? 'light' : 'dark'));
  }, []);

  const value = useMemo<ThemeContextValue>(() => ({
    theme,
    isDark: theme === 'dark',
    setTheme,
    toggleTheme,
  }), [theme, setTheme, toggleTheme]);

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }

  return context;
}

export function ThemeToggle({ variant = 'full', className, style }: ThemeToggleProps): React.ReactElement {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';
  const nextThemeLabel = isDark ? '浅色主题' : '深色主题';
  const nextThemeShortLabel = isDark ? '浅色模式' : '深色模式';
  const Icon = isDark ? SunOutlined : MoonOutlined;

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`切换到${nextThemeLabel}`}
      title={`切换到${nextThemeLabel}`}
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: variant === 'full' ? 8 : 0,
        height: 36,
        minWidth: variant === 'full' ? 112 : 36,
        padding: variant === 'full' ? '0 12px' : 0,
        borderRadius: 'var(--radius-full)',
        border: '1px solid var(--border)',
        background: 'var(--bg-elevated)',
        color: 'var(--text-primary)',
        boxShadow: 'var(--shadow-sm)',
        cursor: 'pointer',
        fontSize: 13,
        fontWeight: 600,
        lineHeight: 1,
        transition: 'all var(--duration-base) var(--ease-out)',
        whiteSpace: 'nowrap',
        ...style,
      }}
      onMouseEnter={(event) => {
        event.currentTarget.style.background = 'var(--bg-hover)';
        event.currentTarget.style.borderColor = 'var(--border-hover)';
      }}
      onMouseLeave={(event) => {
        event.currentTarget.style.background = 'var(--bg-elevated)';
        event.currentTarget.style.borderColor = 'var(--border)';
      }}
    >
      <Icon style={{ fontSize: 14, color: 'var(--accent)' }} />
      {variant === 'full' && <span>{nextThemeShortLabel}</span>}
    </button>
  );
}
