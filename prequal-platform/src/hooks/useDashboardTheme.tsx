import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

export type DashboardTheme = 'light' | 'dark';

export interface DashboardThemeState {
  theme: DashboardTheme;
  toggleTheme: () => void;
  setTheme: (theme: DashboardTheme) => void;
  /** Recharts-compatible palette that stays legible in the active theme. */
  chartColors: {
    primary: string;
    secondary: string;
    success: string;
    warning: string;
    danger: string;
    info: string;
    grid: string;
    axis: string;
    tooltipBg: string;
    tooltipBorder: string;
  };
}

const STORAGE_KEY = 'prequal_dashboard_theme';

const LIGHT_CHART_COLORS = {
  primary: '#3b82f6',
  secondary: '#8b5cf6',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#06b6d4',
  grid: '#e5e7eb',
  axis: '#6b7280',
  tooltipBg: '#ffffff',
  tooltipBorder: '#e5e7eb',
};

const DARK_CHART_COLORS = {
  primary: '#60a5fa',
  secondary: '#a78bfa',
  success: '#34d399',
  warning: '#fbbf24',
  danger: '#f87171',
  info: '#22d3ee',
  grid: '#374151',
  axis: '#9ca3af',
  tooltipBg: '#111827',
  tooltipBorder: '#374151',
};

const readInitialTheme = (): DashboardTheme => {
  if (typeof window === 'undefined') return 'light';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const applyTheme = (theme: DashboardTheme) => {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', theme);
};

export const DashboardThemeContext = createContext<DashboardThemeState>({
  theme: 'light',
  toggleTheme: () => undefined,
  setTheme: () => undefined,
  chartColors: LIGHT_CHART_COLORS,
});

export const DashboardThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<DashboardTheme>(readInitialTheme);

  useEffect(() => {
    applyTheme(theme);
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const setTheme = useCallback((next: DashboardTheme) => setThemeState(next), []);
  const toggleTheme = useCallback(
    () => setThemeState((prev) => (prev === 'light' ? 'dark' : 'light')),
    [],
  );

  const value = useMemo<DashboardThemeState>(
    () => ({
      theme,
      toggleTheme,
      setTheme,
      chartColors: theme === 'dark' ? DARK_CHART_COLORS : LIGHT_CHART_COLORS,
    }),
    [theme, toggleTheme, setTheme],
  );

  return (
    <DashboardThemeContext.Provider value={value}>{children}</DashboardThemeContext.Provider>
  );
};

export function useDashboardTheme(): DashboardThemeState {
  return useContext(DashboardThemeContext);
}
