import { useState } from 'react';
import { AdminManualServerPanel } from '../../components/AdminManualServerPanel';
import { PermissionMatrix } from './PermissionMatrix';
import { ShopProfile } from './ShopProfile';
import { AccentPicker } from './AccentPicker';
import { AboutCard } from './AboutCard';
import { useTheme, type Theme } from '../../theme/ThemeProvider';
import { SessionTimeoutSettings } from './SessionTimeoutSettings';

const DEFAULT_DOC_KEY = 'ltpos_default_doc_type';
type DocType = 'SYSTEM_PRINTED' | 'MANUAL' | 'NO_PRINT';

function getDefaultDocType(): DocType {
  try {
    const v = localStorage.getItem(DEFAULT_DOC_KEY);
    if (v === 'SYSTEM_PRINTED' || v === 'MANUAL' || v === 'NO_PRINT') return v;
  } catch {
    // ignore
  }
  return 'SYSTEM_PRINTED';
}

export function SettingsPanel({ isAdmin }: { isAdmin: boolean }) {
  const { theme, density, setTheme, setDensity } = useTheme();
  const compact = density === 'compact';
  const [showManualConfig, setShowManualConfig] = useState(false);
  const [defaultDoc, setDefaultDoc] = useState<DocType>(() => getDefaultDocType());

  if (showManualConfig) {
    return <AdminManualServerPanel
      onConfigured={() => setShowManualConfig(false)}
      onBack={() => setShowManualConfig(false)}
      onRetry={async () => {}}
    />;
  }

  return <section className="settings-page">
    <div className="glass-panel settings-hero">
      <div>
        <span className="eyebrow">PREFERENCES</span>
        <h2>Settings &amp; appearance</h2>
        <p className="muted">Customize the POS workspace on this computer. These preferences stay local to this device.</p>
      </div>
      <span className="feature-badge">{isAdmin ? 'ADMIN + DEVICE' : 'DEVICE'}</span>
    </div>

    {isAdmin && (
      <div className="glass-panel settings-card settings-about">
        <div className="settings-card-title">
          <div>
            <h3>Server connection</h3>
            <p className="muted">Automatic LAN discovery is the default. Manual override is a fallback for Admins when discovery fails.</p>
          </div>
          <span className="settings-symbol">⚙</span>
        </div>
        <div className="settings-facts"><span><small>Manual override</small><b>Admin only</b></span></div>
        <div className="button-row" style={{ marginTop: '0.5rem' }}>
          <button className="primary" onClick={() => setShowManualConfig(true)}>Configure server manually</button>
        </div>
      </div>
    )}

    <div className="settings-grid">
      <ShopProfile isAdmin={isAdmin} />
      <AccentPicker />
      <div className="glass-panel settings-card">
        <div className="settings-card-title">
          <div><h3>Theme</h3><p className="muted">Switch the workspace between light and dark.</p></div>
          <span className="settings-symbol">◐</span>
        </div>
        <div className="segmented-control" role="group" aria-label="Theme">
          {(['light', 'dark', 'system'] as Theme[]).map((x) => (
            <button key={x} className={theme === x ? 'selected' : ''} onClick={() => setTheme(x)}>
              {x === 'light' ? '☀ Light' : x === 'dark' ? '☾ Dark' : '◒ System'}
            </button>
          ))}
        </div>
      </div>
      <div className="glass-panel settings-card">
        <div className="settings-card-title">
          <div><h3>Workspace density</h3><p className="muted">Use compact spacing when the POS screen needs more information.</p></div>
          <span className="settings-symbol">▦</span>
        </div>
        <label className="toggle-row">
          <span><b>{compact ? 'Compact' : 'Comfortable'}</b><small>Card and control spacing</small></span>
          <input type="checkbox" checked={compact} onChange={(e) => setDensity(e.target.checked ? 'compact' : 'comfortable')} />
          <i />
        </label>
      </div>
      <div className="glass-panel settings-card">
        <div className="settings-card-title">
          <div>
            <h3>Default invoice type</h3>
            <p className="muted">Applied to every new sale. You can still change it per sale.</p>
          </div>
          <span className="settings-symbol">🖨</span>
        </div>
        <div className="segmented-control" role="group" aria-label="Default invoice type">
          {(['SYSTEM_PRINTED', 'MANUAL', 'NO_PRINT'] as DocType[]).map((x) => (
            <button
              key={x}
              type="button"
              className={defaultDoc === x ? 'selected' : ''}
              onClick={() => {
                setDefaultDoc(x);
                try { localStorage.setItem(DEFAULT_DOC_KEY, x); } catch { /* ignore */ }
              }}
            >
              {x === 'SYSTEM_PRINTED' ? '🖨 Thermal' : x === 'MANUAL' ? '✍ Manual' : '✖ None'}
            </button>
          ))}
        </div>
        <p className="muted" style={{ marginTop: '0.5rem', fontSize: '0.75rem' }}>
          {defaultDoc === 'SYSTEM_PRINTED'
            ? 'Receipt dialog will open automatically after every sale.'
            : defaultDoc === 'MANUAL'
            ? 'You must enter a handwritten invoice number for every sale.'
            : 'No receipt will be printed.'}
        </p>
      </div>
      <div className="glass-panel settings-card settings-about">
        <div className="settings-card-title">
          <div>
            <h3>Lovely Tech POS</h3>
            <p className="muted">UI preferences only. Business rules, permissions and financial calculations remain server-controlled.</p>
          </div>
          <span className="brand-mark">LT</span>
        </div>
        <div className="settings-facts">
          <span><small>Role</small><b>{isAdmin ? 'Administrator' : 'Cashier'}</b></span>
          <span><small>Theme</small><b>{theme}</b></span>
          <span><small>Density</small><b>{density}</b></span>
        </div>
      </div>
      <PermissionMatrix />
      <SessionTimeoutSettings isAdmin={isAdmin} />
      <AboutCard />
    </div>
  </section>;
}