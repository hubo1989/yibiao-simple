/**
 * 认证上下文
 * 管理用户认证状态、Token 存储和登录/登出方法
 */
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import type {
  User,
  Token,
  LoginRequest,
  RegisterRequest,
  AuthContextType,
  UserRole,
} from '../types/auth';
import { authApi, setAuthToken, clearAuthToken, getStoredToken, getStoredRefreshToken, setStoredTokens, clearStoredTokens } from '../services/api';

const AuthContext = createContext<AuthContextType | null>(null);

const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'auth_user';

export function getStoredUser(): User | null {
  const stored = localStorage.getItem(USER_KEY);
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      return null;
    }
  }
  return null;
}

function setStoredUser(user: User | null): void {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
}

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps): React.ReactElement {
  const [user, setUser] = useState<User | null>(() => getStoredUser());
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = useMemo(() => !!user && !!token, [user, token]);

  // 初始化：检查已存储的 token 并获取用户信息
  useEffect(() => {
    const initAuth = async () => {
      const storedToken = getStoredToken();
      const storedUser = getStoredUser();

      if (storedToken && storedUser) {
        setAuthToken(storedToken);
        setToken(storedToken);
        setUser(storedUser);

        // 验证 token 是否仍然有效
        try {
          const currentUser = await authApi.getMe();
          setUser(currentUser);
          setStoredUser(currentUser);
        } catch {
          // Token 无效，清除认证状态
          clearAuthToken();
          clearStoredTokens();
          setStoredUser(null);
          setUser(null);
          setToken(null);
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const login = useCallback(async (credentials: LoginRequest): Promise<void> => {
    const response = await authApi.login(credentials);
    const tokenData: Token = response.data;

    // 存储 token
    setStoredTokens(tokenData.access_token, tokenData.refresh_token);
    setAuthToken(tokenData.access_token);
    setToken(tokenData.access_token);

    // 获取用户信息
    const userData = await authApi.getMe();
    setUser(userData);
    setStoredUser(userData);
  }, []);

  const register = useCallback(async (data: RegisterRequest): Promise<void> => {
    const response = await authApi.register(data);
    const tokenData: Token = response.data;

    // 存储 token
    setStoredTokens(tokenData.access_token, tokenData.refresh_token);
    setAuthToken(tokenData.access_token);
    setToken(tokenData.access_token);

    // 获取用户信息
    const userData = await authApi.getMe();
    setUser(userData);
    setStoredUser(userData);
  }, []);

  const logout = useCallback((): void => {
    clearAuthToken();
    clearStoredTokens();
    setStoredUser(null);
    setUser(null);
    setToken(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<void> => {
    if (!token) return;

    try {
      const userData = await authApi.getMe();
      setUser(userData);
      setStoredUser(userData);
    } catch {
      logout();
    }
  }, [token, logout]);

  const value = useMemo<AuthContextType>(() => ({
    user,
    token,
    isAuthenticated,
    isLoading,
    login,
    register,
    logout,
    refreshUser,
  }), [user, token, isAuthenticated, isLoading, login, register, logout, refreshUser]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// 角色权限检查 hook
export function useHasRole(allowedRoles: UserRole[]): boolean {
  const { user } = useAuth();
  if (!user) return false;
  return allowedRoles.includes(user.role);
}

// 管理员权限检查 hook
export function useIsAdmin(): boolean {
  return useHasRole(['admin']);
}
