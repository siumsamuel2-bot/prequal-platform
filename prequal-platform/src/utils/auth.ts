export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  teams: Team[];
}

export interface Team {
  id: string;
  name: string;
  description?: string;
  role: string;
  joined_at?: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}

const AUTH_STATE_KEY = 'auth_state';

export const isAuthenticated = (): boolean => {
  const token = localStorage.getItem('access_token');
  return !!token;
};

export const getToken = (): string | null => {
  return localStorage.getItem('access_token');
};

export const setToken = (token: string): void => {
  localStorage.setItem('access_token', token);
};

export const removeToken = (): void => {
  localStorage.removeItem('access_token');
};

export const getAuthState = (): AuthState => {
  const saved = localStorage.getItem(AUTH_STATE_KEY);
  if (saved) {
    try {
      return JSON.parse(saved);
    } catch {
      return { user: null, token: null, isAuthenticated: false };
    }
  }
  return { user: null, token: null, isAuthenticated: false };
};

export const setAuthState = (state: AuthState): void => {
  localStorage.setItem(AUTH_STATE_KEY, JSON.stringify(state));
  if (state.token) {
    setToken(state.token);
  } else {
    removeToken();
  }
};

export const login = (token: string, user?: User): void => {
  setToken(token);
  if (user) {
    const state: AuthState = { token, user, isAuthenticated: true };
    setAuthState(state);
  }
};

export const logout = (): void => {
  removeToken();
  localStorage.removeItem(AUTH_STATE_KEY);
  window.location.href = '/login';
};

export const getCurrentUser = (): User | null => {
  const state = getAuthState();
  return state.user;
};

export const isAdmin = (): boolean => {
  const user = getCurrentUser();
  return user?.role === 'admin';
};

export const isManager = (): boolean => {
  const user = getCurrentUser();
  return user?.role === 'admin' || user?.role === 'manager';
};