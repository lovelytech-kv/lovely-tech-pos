import { useEffect, useState } from 'react';
import { api } from '../../api/client';
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

  async function save() {
    if (!cfg) return;
    try {
      setSaving(true);
      await api('/session-settings', { method: 'PUT', body: JSON.stringify(cfg) });
      toast.success('Session settings saved');
      await load();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (!isAdmin) return null;

  if (loading) {
    return (
      <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
        <div className="settings-card-title"><div><h3>Session Timeout</h3><p className="muted">Loading…</p></div><span className="settings-symbol">⏱</span></div>
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
        <span className="settings-symbol">⏱</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <div style={{ display: 'grid', gap: '0.75rem', padding: '0.75rem', background: 'var(--surface-2)', borderRadius: 10, border: '1px solid var(--line)' }}>
          <b style={{ fontSize: '0.85rem', color: 'var(--text)' }}>👑 Admin</b>
          <label style={labelStyle}>
            Idle logout (minutes)
            <input type="number" min={0} max={720} value={cfg.admin_minutes}
              onChange={(e) => setCfg({ ...cfg, admin_minutes: Math.max(0, Number(e.target.value) || 0) })}
              style={inputStyle} />
            <small style={{ color: 'var(--muted)', fontSize: '0.65rem' }}>0 = never idle-logout</small>
          </label>
          <label style={labelStyle}>
            Session lifetime (hours)
            <input type="number" min={0} max={8760} value={cfg.admin_hours}
              onChange={(e) => setCfg({ ...cfg, admin_hours: Math.max(0, Number(e.target.value) || 0) })}
              style={inputStyle} />
            <small style={{ color: 'var(--muted)', fontSize: '0.65rem' }}>0 = never expires (extends on every request)</small>
          </label>
        </div>

        <div style={{ display: 'grid', gap: '0.75rem', padding: '0.75rem', background: 'var(--surface-2)', borderRadius: 10, border: '1px solid var(--line)' }}>
          <b style={{ fontSize: '0.85rem', color: 'var(--text)' }}>🧑‍💼 Cashier</b>
          <label style={labelStyle}>
            Idle logout (minutes)
            <input type="number" min={0} max={720} value={cfg.cashier_minutes}
              onChange={(e) => setCfg({ ...cfg, cashier_minutes: Math.max(0, Number(e.target.value) || 0) })}
              style={inputStyle} />
            <small style={{ color: 'var(--muted)', fontSize: '0.65rem' }}>0 = never idle-logout</small>
          </label>
          <label style={labelStyle}>
            Session lifetime (hours)
            <input type="number" min={0} max={8760} value={cfg.cashier_hours}
              onChange={(e) => setCfg({ ...cfg, cashier_hours: Math.max(0, Number(e.target.value) || 0) })}
              style={inputStyle} />
            <small style={{ color: 'var(--muted)', fontSize: '0.65rem' }}>0 = never expires (extends on every request)</small>
          </label>
        </div>
      </div>

      <p className="muted" style={{ marginTop: '0.75rem', fontSize: '0.75rem' }}>
        ⓘ Session lifetime extends automatically on every API request. Users will only be logged out after being idle for the configured minutes, or after the absolute lifetime expires.
      </p>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.75rem' }}>
        <button className="primary" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save Session Settings'}</button>
      </div>
    </div>
  );
}