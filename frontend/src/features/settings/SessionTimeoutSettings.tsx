import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { Icon } from '../../components/Icon';
import { toast } from '../../ui/toast';

type Cfg = {
  admin_minutes: number;
  cashier_minutes: number;
  admin_hours: number;
  cashier_hours: number;
};

const inputStyle: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  border: '1px solid var(--line)',
  borderRadius: 8,
  background: 'var(--surface)',
  color: 'var(--text)',
  fontSize: '0.875rem',
  width: '100%',
};

const labelStyle: React.CSSProperties = {
  display: 'grid',
  gap: '0.3rem',
  fontSize: '0.75rem',
  color: 'var(--muted)',
  fontWeight: 600,
};

export function SessionTimeoutSettings({ isAdmin }: { isAdmin: boolean }) {
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false);
  const [adminPassword, setAdminPassword] = useState('');
  const [saveError, setSaveError] = useState('');

  async function load() {
    try {
      setLoading(true);
      const result = await api<Cfg>('/session-settings');
      setCfg(result);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  function requestSave() {
    if (!cfg || saving) return;
    setAdminPassword('');
    setSaveError('');
    setPromptOpen(true);
  }

  function cancelSave() {
    if (saving) return;
    setPromptOpen(false);
    setAdminPassword('');
    setSaveError('');
  }

  async function confirmSave() {
    if (!cfg || saving) return;
    if (!adminPassword.trim()) {
      setSaveError('Admin password is required.');
      return;
    }
    try {
      setSaving(true);
      setSaveError('');
      await api('/session-settings', {
        method: 'PUT',
        body: JSON.stringify({ ...cfg, admin_password: adminPassword }),
        // Wrong re-auth password returns 401 — do not treat it as an expired session.
        skipAuthLogout: true,
      });
      setPromptOpen(false);
      setAdminPassword('');
      toast.success('Session settings saved');
      await load();
    } catch (e) {
      const msg = (e as Error).message || '';
      // current_user() 401s are genuine session loss; reauth.py 401s are wrong-password.
      // Anchored to avoid matching "Admin re-authentication required for session settings change".
      const sessionGone = /^(session expired or revoked|session locked due to inactivity|authentication required|user inactive)$/i.test(msg);
      if (sessionGone) {
        localStorage.removeItem('ltpos_token');
        localStorage.removeItem('ltpos_user');
        window.dispatchEvent(new CustomEvent('ltpos:session-expired'));
        return;
      }
      setSaveError(msg);
    } finally {
      setSaving(false);
    }
  }

  if (!isAdmin) return null;

  if (loading) {
    return (
      <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
        <div className="settings-card-title"><div><h3>Session Timeout</h3><p className="muted">Loading…</p></div><span className="settings-symbol"><Icon name="clock" size={20} /></span></div>
        <div style={{ textAlign: 'center', padding: '1rem' }}><span className="spinner" /></div>
      </div>
    );
  }

  if (!cfg) return null;

  return (
    <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
      <div className="settings-card-title">
        <div>
          <h3>Session Timeout</h3>
          <p className="muted">Controls when users are automatically logged out. Active users are never kicked out mid-action.</p>
        </div>
        <span className="settings-symbol"><Icon name="clock" size={20} /></span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div style={{ display: 'grid', gap: '0.75rem', padding: '0.75rem', background: 'var(--surface-2)', borderRadius: 10, border: '1px solid var(--line)' }}>
          <b style={{ fontSize: '0.85rem', color: 'var(--text)' }}><Icon name="crown" size={14} /> Admin</b>
          <label style={labelStyle}>
            Idle logout (minutes)
            <input type="number" min={1} max={720} value={cfg.admin_minutes}
              onChange={(e) => setCfg({ ...cfg, admin_minutes: Math.max(1, Number(e.target.value) || 1) })}
              style={inputStyle} />
            <small style={{ color: 'var(--muted)', fontSize: '0.65rem' }}>Minimum 1 minute</small>
          </label>
          <label style={labelStyle}>
            Session lifetime (hours)
            <input type="number" min={1} max={8760} value={cfg.admin_hours}
              onChange={(e) => setCfg({ ...cfg, admin_hours: Math.max(1, Number(e.target.value) || 1) })}
              style={inputStyle} />
            <small style={{ color: 'var(--muted)', fontSize: '0.65rem' }}>Minimum 1 hour; fixed at login</small>
          </label>
        </div>

        <div style={{ display: 'grid', gap: '0.75rem', padding: '0.75rem', background: 'var(--surface-2)', borderRadius: 10, border: '1px solid var(--line)' }}>
          <b style={{ fontSize: '0.85rem', color: 'var(--text)' }}><Icon name="briefcase" size={14} /> Cashier</b>
          <label style={labelStyle}>
            Idle logout (minutes)
            <input type="number" min={1} max={720} value={cfg.cashier_minutes}
              onChange={(e) => setCfg({ ...cfg, cashier_minutes: Math.max(1, Number(e.target.value) || 1) })}
              style={inputStyle} />
            <small style={{ color: 'var(--muted)', fontSize: '0.65rem' }}>Minimum 1 minute</small>
          </label>
          <label style={labelStyle}>
            Session lifetime (hours)
            <input type="number" min={1} max={8760} value={cfg.cashier_hours}
              onChange={(e) => setCfg({ ...cfg, cashier_hours: Math.max(1, Number(e.target.value) || 1) })}
              style={inputStyle} />
            <small style={{ color: 'var(--muted)', fontSize: '0.65rem' }}>Minimum 1 hour; fixed at login</small>
          </label>
        </div>
      </div>

      <p className="muted" style={{ marginTop: '0.75rem', fontSize: '0.75rem' }}>
        <Icon name="info-circle" size={13} /> Idle logout and absolute session lifetime are enforced separately. The absolute lifetime is fixed when the user logs in and does not extend with activity.
      </p>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.75rem' }}>
        <button className="primary" onClick={requestSave} disabled={saving}>{saving ? 'Saving…' : 'Save Session Settings'}</button>
      </div>

      {promptOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Confirm session settings change"
          onKeyDown={(e) => { if (e.key === 'Escape') cancelSave(); }}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'grid', placeItems: 'center', zIndex: 50, padding: '1rem' }}
        >
          <div className="glass-panel" style={{ width: '100%', maxWidth: 420, padding: '1.25rem', display: 'grid', gap: '0.75rem' }}>
            <h3 style={{ margin: 0 }}>Confirm with admin password</h3>
            <p className="muted" style={{ margin: 0, fontSize: '0.8rem' }}>Changing session timeouts is a sensitive Admin action.</p>
            <input
              type="password"
              autoFocus
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') void confirmSave(); }}
              placeholder="Admin password"
              aria-label="Admin password"
              disabled={saving}
              style={inputStyle}
            />
            {saveError && <p role="alert" style={{ margin: 0, color: '#dc2626', fontSize: '0.8rem' }}>{saveError}</p>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button type="button" className="btn-ghost" onClick={cancelSave} disabled={saving}>Cancel</button>
              <button type="button" className="primary" onClick={() => void confirmSave()} disabled={saving}>{saving ? 'Saving…' : 'Confirm Save'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
