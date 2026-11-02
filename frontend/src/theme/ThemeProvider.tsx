import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type Theme = 'light' | 'dark' | 'system';
export type Density = 'comfortable' | 'compact';

export interface ThemeContextValue {
  theme: Theme;
  accent: string;
  density: Density;
  performanceMode: boolean;
  setTheme: (theme: Theme) => void;
  setAccent: (accent: string) => void;
  setDensity: (density: Density) => void;
  setPerformanceMode: (enabled: boolean) => void;
  toggleTheme: () => void;
}

const STORAGE_KEYS = {
  theme: 'ltpos_theme',
  accent: 'ltpos_accent',
  density: 'ltpos_density',
  performance: 'ltpos_performance',
} as const;

const DEFAULT_THEME: Theme = 'light';
const DEFAULT_ACCENT = '#df3b32';
const DEFAULT_DENSITY: Density = 'comfortable';
const DEFAULT_PERFORMANCE = false;

const FALLBACK_ACCENT_RGB = '223, 59, 50';

function isTheme(value: string | null): value is Theme {
  return value === 'light' || value === 'dark' || value === 'system';
}

function isDensity(value: string | null): value is Density {
  return value === 'comfortable' || value === 'compact';
}

function readTheme(): Theme {
  if (typeof window === 'undefined') return DEFAULT_THEME;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.theme);
    return isTheme(raw) ? raw : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

function readAccent(): string {
  if (typeof window === 'undefined') return DEFAULT_ACCENT;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.accent);
    return raw && raw.trim().length > 0 ? raw : DEFAULT_ACCENT;
  } catch {
    return DEFAULT_ACCENT;
  }
}

function readDensity(): Density {
  if (typeof window === 'undefined') return DEFAULT_DENSITY;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.density);
    return isDensity(raw) ? raw : DEFAULT_DENSITY;
  } catch {
    return DEFAULT_DENSITY;
  }
}

function readPerformanceMode(): boolean {
  if (typeof window === 'undefined') return DEFAULT_PERFORMANCE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEYS.performance);
    if (raw === 'true') return true;
    if (raw === 'false') return false;
    return DEFAULT_PERFORMANCE;
  } catch {
    return DEFAULT_PERFORMANCE;
  }
}

function writeStorage(key: string, value: string): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // localStorage may be unavailable (private mode, quota, Tauri sandbox) — ignore.
  }
}

function getSystemTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return 'light';
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function hexToRgbTriplet(hex: string): string {
  const cleaned = hex.trim().replace(/^#/, '');
  if (cleaned.length === 3) {
    const r = Number.parseInt(cleaned[0] + cleaned[0], 16);
    const g = Number.parseInt(cleaned[1] + cleaned[1], 16);
    const b = Number.parseInt(cleaned[2] + cleaned[2], 16);
    if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) {
      return FALLBACK_ACCENT_RGB;
    }
    return `${r}, ${g}, ${b}`;
  }
  if (cleaned.length === 6) {
    const r = Number.parseInt(cleaned.slice(0, 2), 16);
    const g = Number.parseInt(cleaned.slice(2, 4), 16);
    const b = Number.parseInt(cleaned.slice(4, 6), 16);
    if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) {
      return FALLBACK_ACCENT_RGB;
    }
    return `${r}, ${g}, ${b}`;
  }
  return FALLBACK_ACCENT_RGB;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

interface ThemeProviderProps {
  children: ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(readTheme);
  const [accent, setAccentState] = useState<string>(readAccent);
  const [density, setDensityState] = useState<Density>(readDensity);
  const [performanceMode, setPerformanceModeState] = useState<boolean>(readPerformanceMode);
  const [systemTheme, setSystemTheme] = useState<'light' | 'dark'>(getSystemTheme);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    writeStorage(STORAGE_KEYS.theme, next);
  }, []);

  const setAccent = useCallback((next: string) => {
    setAccentState(next);
    writeStorage(STORAGE_KEYS.accent, next);
  }, []);

  const setDensity = useCallback((next: Density) => {
    setDensityState(next);
    writeStorage(STORAGE_KEYS.density, next);
  }, []);

  const setPerformanceMode = useCallback((next: boolean) => {
    setPerformanceModeState(next);
    writeStorage(STORAGE_KEYS.performance, next ? 'true' : 'false');
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((current) => {
      const next: Theme =
        current === 'light' ? 'dark' : current === 'dark' ? 'system' : 'light';
      writeStorage(STORAGE_KEYS.theme, next);
      return next;
    });
  }, []);

  // Listen to prefers-color-scheme only while theme === 'system'.
  useEffect(() => {
    if (theme !== 'system') return;
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;

    const mql = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = (matches: boolean) => {
      setSystemTheme(matches ? 'dark' : 'light');
    };

    apply(mql.matches);

    const handler = (event: MediaQueryListEvent) => apply(event.matches);

    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', handler);
      return () => mql.removeEventListener('change', handler);
    }
    if (typeof mql.addListener === 'function') {
      mql.addListener(handler);
      return () => mql.removeListener(handler);
    }
    return;
  }, [theme]);

  useEffect(() => {
    const resolved: 'light' | 'dark' = theme === 'system' ? systemTheme : theme;
    document.documentElement.dataset.theme = resolved;
  }, [theme, systemTheme]);

  useEffect(() => {
    document.documentElement.dataset.density = density;
  }, [density]);

  useEffect(() => {
    document.documentElement.dataset.performance = performanceMode ? 'on' : 'off';
  }, [performanceMode]);

  useEffect(() => {
    document.documentElement.style.setProperty('--accent', accent);
    document.documentElement.style.setProperty('--accent-rgb', hexToRgbTriplet(accent));
  }, [accent]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      accent,
      density,
      performanceMode,
      setTheme,
      setAccent,
      setDensity,
      setPerformanceMode,
      toggleTheme,
    }),
    [
      theme,
      accent,
      density,
      performanceMode,
      setTheme,
      setAccent,
      setDensity,
      setPerformanceMode,
      toggleTheme,
    ],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return ctx;
}