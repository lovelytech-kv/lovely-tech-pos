import { useState } from 'react';
import type { CSSProperties } from 'react';
import { AdminManualServerPanel } from '../../components/AdminManualServerPanel';
import { PermissionMatrix } from './PermissionMatrix';
import { useTheme, type Theme } from '../../theme/ThemeProvider';

const accents = [
  { name: 'Lovely Red', value: '#df3b32' }, { name: 'Crimson', value: '#c21f39' },
  { name: 'Ruby', value: '#b51f35' }, { name: 'Amber', value: '#d97706' }, { name: 'Blue', value: '#2563eb' },
];

export function SettingsPanel({ isAdmin }: { isAdmin: boolean }) {
  const { theme, accent, density, setTheme, setAccent, setDensity } = useTheme();
  const compact = density === 'compact';
  const [showManualConfig, setShowManualConfig] = useState(false);

  if (showManualConfig) {
    return <AdminManualServerPanel
      onConfigured={() => setShowManualConfig(false)}
      onBack={() => setShowManualConfig(false)}
      onRetry={async () => {}}
    />;
  }

  return <section className="settings-page">
    <div className="glass-panel settings-hero"><div><span className="eyebrow">PREFERENCES</span><h2>Settings & appearance</h2><p className="muted">Customize the POS workspace on this computer. These preferences stay local to this device.</p></div><span className="feature-badge">{isAdmin ? 'ADMIN + DEVICE' : 'DEVICE'}</span></div>
    {isAdmin && (
      <div className="glass-panel settings-card settings-about">
        <div className="settings-card-title"><div><h3>Server connection</h3><p className="muted">Automatic LAN discovery is the default. Manual override is a fallback for Admins when discovery fails.</p></div><span className="settings-symbol">⚙</span></div>
        <div className="settings-facts"><span><small>Manual override</small><b>Admin only</b></span></div>
        <div className="button-row" style={{ marginTop: '0.5rem' }}>
          <button className="primary" onClick={() => setShowManualConfig(true)}>Configure server manually</button>
        </div>
      </div>
    )}
    <div className="settings-grid">
      <div className="glass-panel settings-card"><div className="settings-card-title"><div><h3>Theme</h3><p className="muted">Switch the workspace between light and dark.</p></div><span className="settings-symbol">◐</span></div><div className="segmented-control" role="group" aria-label="Theme">{(['light','dark','system'] as Theme[]).map(x => <button key={x} className={theme === x ? 'selected' : ''} onClick={() => setTheme(x)}>{x === 'light' ? '☀ Light' : x === 'dark' ? '☾ Dark' : '◒ System'}</button>)}</div></div>
      <div className="glass-panel settings-card"><div className="settings-card-title"><div><h3>Accent colour</h3><p className="muted">Choose the highlight colour used across the POS.</p></div><span className="settings-symbol">✦</span></div><div className="accent-grid">{accents.map(a => <button key={a.value} className={`accent-choice ${accent === a.value ? 'selected' : ''}`} style={{ '--swatch': a.value } as CSSProperties} onClick={() => setAccent(a.value)}><span className="accent-swatch" /><span>{a.name}</span>{accent === a.value && <b>✓</b>}</button>)}</div></div>
      <div className="glass-panel settings-card"><div className="settings-card-title"><div><h3>Workspace density</h3><p className="muted">Use compact spacing when the POS screen needs more information.</p></div><span className="settings-symbol">▦</span></div><label className="toggle-row"><span><b>{compact ? 'Compact' : 'Comfortable'}</b><small>Card and control spacing</small></span><input type="checkbox" checked={compact} onChange={e => setDensity(e.target.checked ? 'compact' : 'comfortable')} /><i /></label></div>
      <div className="glass-panel settings-card settings-about"><div className="settings-card-title"><div><h3>Lovely Tech POS</h3><p className="muted">UI preferences only. Business rules, permissions and financial calculations remain server-controlled.</p></div><span className="brand-mark">LT</span></div><div className="settings-facts"><span><small>Role</small><b>{isAdmin ? 'Administrator' : 'Cashier'}</b></span><span><small>Theme</small><b>{theme}</b></span><span><small>Accent</small><b>{accents.find(a => a.value === accent)?.name || 'Custom'}</b></span></div></div>
      <PermissionMatrix />
    </div>
  </section>;
}