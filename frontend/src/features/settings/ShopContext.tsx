import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api } from '../../api/client';

type PublicProfile = {
  name: string;
  developer_phone: string | null;
  logo_base64: string | null;
  logo_mime: string | null;
  logo_base64_light: string | null;
  logo_mime_light: string | null;
  logo_base64_dark: string | null;
  logo_mime_dark: string | null;
};

type ShopContextValue = {
  profile: PublicProfile | null;
  loading: boolean;
  refetch: () => Promise<void>;
  getShopName: () => string;
  getLogoDataUrl: (forcedTheme?: 'light' | 'dark') => string | null;
  getDeveloperPhone: () => string;
};

const ShopContext = createContext<ShopContextValue | null>(null);

const DEFAULT_NAME = 'Lovely Tech';
const DEVELOPER_CACHE_KEY = 'ltpos_developer_info';
const DEVELOPER_PHONE_FALLBACK = import.meta.env.VITE_DEVELOPER_PHONE || '0770290008';

function readCachedDeveloperPhone(): string {
  try {
    const raw = localStorage.getItem(DEVELOPER_CACHE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as { developer_phone?: string } | null;
      if (parsed?.developer_phone) return parsed.developer_phone;
    }
  } catch {
    // Cache is optional; fall back to the build-time/default developer number.
  }
  return DEVELOPER_PHONE_FALLBACK;
}

export function ShopProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light');

  // Track the resolved data-theme attribute (updated by ThemeProvider)
  useEffect(() => {
    const el = document.documentElement;
    const read = () => setResolvedTheme(el.dataset.theme === 'dark' ? 'dark' : 'light');
    read();
    const obs = new MutationObserver(read);
    obs.observe(el, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);

  const refetch = useCallback(async () => {
    try {
      setLoading(true);
      const result = await api<PublicProfile>('/branch/public');
      setProfile(result);
      if (result.developer_phone) {
        try {
          localStorage.setItem(DEVELOPER_CACHE_KEY, JSON.stringify({
            developer_name: 'Lovely Tech',
            developer_phone: result.developer_phone,
          }));
        } catch {
          // Non-fatal: the API value is already in memory.
        }
      }
    } catch {
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const getShopName = useCallback(
    () => profile?.name || DEFAULT_NAME,
    [profile],
  );

  const getLogoDataUrl = useCallback(
    (forcedTheme?: 'light' | 'dark') => {
      const effective = forcedTheme || resolvedTheme;
      // Dark mode: only use dark logo if BOTH base64 and mime are present
      if (effective === 'dark' && profile?.logo_base64_dark && profile?.logo_mime_dark) {
        return `data:${profile.logo_mime_dark};base64,${profile.logo_base64_dark}`;
      }
      // Light mode (or fallback from dark): prefer light-specific, then legacy
      const lightB64 = profile?.logo_base64_light || profile?.logo_base64;
      const lightMime = profile?.logo_mime_light || profile?.logo_mime;
      if (lightB64 && lightMime) {
        return `data:${lightMime};base64,${lightB64}`;
      }
      // Last resort: if only dark logo exists, use it even in light mode
      if (profile?.logo_base64_dark && profile?.logo_mime_dark) {
        return `data:${profile.logo_mime_dark};base64,${profile.logo_base64_dark}`;
      }
      return null;
    },
    [profile, resolvedTheme],
  );

  const getDeveloperPhone = useCallback(
    () => profile?.developer_phone || readCachedDeveloperPhone(),
    [profile],
  );

  return (
    <ShopContext.Provider value={{ profile, loading, refetch, getShopName, getLogoDataUrl, getDeveloperPhone }}>
      {children}
    </ShopContext.Provider>
  );
}

export function useShopProfile(): ShopContextValue {
  const ctx = useContext(ShopContext);
  if (!ctx) throw new Error('useShopProfile must be used within ShopProvider');
  return ctx;
}