import { useEffect, useState } from 'react';

// Auto-detect vendor logo files placed in frontend/src/assets/vendor/.
// Expected names (case-insensitive): logo-light.* and logo-dark.*
// Supported extensions: png, jpg, jpeg, svg, webp
const vendorLogos = import.meta.glob('../../assets/vendor/logo-*.{png,jpg,jpeg,svg,webp}', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>;

function pickVendorLogo(theme: 'light' | 'dark'): string | null {
  const keys = Object.keys(vendorLogos);
  if (keys.length === 0) return null;
  const lightKey = keys.find((k) => /logo-light\./i.test(k));
  const darkKey = keys.find((k) => /logo-dark\./i.test(k));
  if (theme === 'dark') {
    if (darkKey) return vendorLogos[darkKey];
    if (lightKey) return vendorLogos[lightKey];
    return vendorLogos[keys[0]] ?? null;
  }
  if (lightKey) return vendorLogos[lightKey];
  if (darkKey) return vendorLogos[darkKey];
  return vendorLogos[keys[0]] ?? null;
}

function useCurrentTheme(): 'light' | 'dark' {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  useEffect(() => {
    const el = document.documentElement;
    const read = () => setTheme(el.dataset.theme === 'dark' ? 'dark' : 'light');
    read();
    const obs = new MutationObserver(read);
    obs.observe(el, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);
  return theme;
}

function VendorLogoFallback({ size }: { size: number }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: Math.round(size * 0.23),
        background: 'linear-gradient(135deg, #e5493d, #a82820)',
        color: '#fff',
        display: 'grid',
        placeItems: 'center',
        fontSize: Math.round(size * 0.34),
        fontWeight: 800,
        letterSpacing: '-0.03em',
        flexShrink: 0,
      }}
    >
      LT
    </div>
  );
}

export function AboutCard() {
  const theme = useCurrentTheme();
  const logo = pickVendorLogo(theme);

  return (
    <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
      <div className="settings-card-title">
        <div>
          <h3>About</h3>
          <p className="muted">Software information and vendor details.</p>
        </div>
        <span className="settings-symbol">ⓘ</span>
      </div>

      <div style={{ display: 'grid', gap: '1rem' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '1rem',
            padding: '1rem',
            background: 'var(--surface-2)',
            borderRadius: 12,
            border: '1px solid var(--line)',
          }}
        >
          {logo ? (
            <img
              src={logo}
              alt="Vendor logo"
              style={{
                width: 64,
                height: 64,
                objectFit: 'contain',
                display: 'block',
                flexShrink: 0,
              }}
            />
          ) : (
            <VendorLogoFallback size={64} />
          )}
          <div>
            <div
              style={{
                fontSize: '1.15rem',
                fontWeight: 700,
                color: 'var(--text)',
                letterSpacing: '-0.02em',
              }}
            >
              Lovely Tech
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
              Mobile Phone Repair &amp; Accessories POS
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: '0.25rem' }}>
              Version <b style={{ color: 'var(--text)' }}>v0.4.0</b>
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gap: '0.5rem', fontSize: '0.85rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--line)' }}>
            <span className="muted">Vendor</span>
            <b style={{ color: 'var(--text)' }}>Lovely Tech</b>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--line)' }}>
            <span className="muted">Made in</span>
            <b style={{ color: 'var(--text)' }}>Sri Lanka 🇱🇰</b>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--line)' }}>
            <span className="muted">Built with</span>
            <b style={{ color: 'var(--text)' }}>React + FastAPI + Tauri</b>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0' }}>
            <span className="muted">Support</span>
            <b style={{ color: 'var(--text)' }}>Lovely Tech Support</b>
          </div>
        </div>

        <p className="muted" style={{ fontSize: '0.7rem', textAlign: 'center', margin: 0 }}>
          © 2026 Lovely Tech. All rights reserved.
        </p>
      </div>
    </div>
  );
}

export default AboutCard;