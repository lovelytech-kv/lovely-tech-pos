import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api } from '../../api/client';

type PublicProfile = {
  name: string;
  logo_base64: string | null;
  logo_mime: string | null;
};

type ShopContextValue = {
  profile: PublicProfile | null;
  loading: boolean;
  refetch: () => Promise<void>;
  getShopName: () => string;
  getLogoDataUrl: () => string | null;
};

const ShopContext = createContext<ShopContextValue | null>(null);

const DEFAULT_NAME = 'Lovely Tech';

export function ShopProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      setLoading(true);
      const result = await api<PublicProfile>('/branch/public');
      setProfile(result);
    } catch {
      // Backend unavailable — fall back to defaults. Header will show "Lovely Tech".
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

  const getLogoDataUrl = useCallback(() => {
    if (!profile?.logo_base64 || !profile?.logo_mime) return null;
    return `data:${profile.logo_mime};base64,${profile.logo_base64}`;
  }, [profile]);

  return (
    <ShopContext.Provider value={{ profile, loading, refetch, getShopName, getLogoDataUrl }}>
      {children}
    </ShopContext.Provider>
  );
}

export function useShopProfile(): ShopContextValue {
  const ctx = useContext(ShopContext);
  if (!ctx) throw new Error('useShopProfile must be used within ShopProvider');
  return ctx;
}