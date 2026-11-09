import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';
import { RecoveryCodesDisplay } from './RecoveryCodesDisplay';

type Status = {
  total: number;
  remaining: number;
  last_generated_at: string | null;
};

export function RecoveryCodesPanel({ isAdmin }: { isAdmin: boolean }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [showPasswordPrompt, setShowPasswordPrompt] = useState(false);
  const [adminPassword, setAdminPassword] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [newCodes, setNewCodes] = useState<string[] | null>(null);

  async function loadStatus() {
    try {
      setLoading(true);
      const result = await api<Status>('/auth/admin/recovery-codes/remaining', { method: 'POST' });
      setStatus(result);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isAdmin) void loadStatus();
  }, [isAdmin]);

  async function regenerate() {
    if (!adminPassword) {
      toast.error('Admin password is required');
      return;
    }
    try {
      setRegenerating(true);
      const result = await api<{ recovery_codes: string[] }>('/auth/admin/recovery-codes/regenerate', {
        method: 'POST',
        body: JSON.stringify({ admin_password: adminPassword }),
      });
      setNewCodes(result.recovery_codes);
      setShowPasswordPrompt(false);
      setAdminPassword('');
      await loadStatus();
    } catch (err) {
      const msg = (err as Error).message || '';
      toast.error(msg || 'Regenerate failed');
    } finally {
      setRegenerating(false);
    }
  }

  if (!isAdmin) return null;

  if (loading) {
    return (
      <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
        <div className="settings-card-title">
          <div><h3>Recovery Codes</h3><p className="muted">Loading…</p></div>
          <span className="settings-symbol">🔑</span>
        </div>
        <div style={{ textAlign: 'center', padding: '1rem' }}>
          <span className="spinner" />
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
        <div className="settings-card-title">
          <div>
            <h3>Recovery Codes</h3>
            <p className="muted">One-time codes for resetting your admin password if you forget it. Each code can be used once.</p>
          </div>
          <span className="settings-symbol">🔑</span>
        </div>

        <div style={{ display: 'grid', gap: '0.75rem' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '0.85rem 1rem',
              background: 'var(--surface-2)',
              borderRadius: 10,
              border: '1px solid var(--line)',
            }}
          >
            <div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text)' }}>
                {status?.remaining ?? 0} <span style={{ fontSize: '0.85rem', color: 'var(--muted)', fontWeight: 400 }}>of {status?.total ?? 0} remaining</span>
              </div>
              <div className="muted" style={{ fontSize: '0.75rem', marginTop: '0.15rem' }}>
                {status?.last_generated_at
                  ? `Last generated: ${new Date(status.last_generated_at).toLocaleString()}`
                  : 'No codes generated yet'}
              </div>
            </div>
            <button type="button" className="primary" onClick={() => setShowPasswordPrompt(true)}>
              Regenerate Codes
            </button>
          </div>

          <div className="recovery-warning" style={{ fontSize: '0.78rem' }}>
            <b>⚠ Regenerating will invalidate all current unused codes.</b> Save the new codes immediately — they are only shown once.
          </div>

          <details style={{ fontSize: '0.78rem' }}>
            <summary style={{ cursor: 'pointer', color: 'var(--muted)', fontWeight: 600 }}>
              Emergency recovery (if all codes lost)
            </summary>
            <div style={{ marginTop: '0.5rem', padding: '0.75rem', background: 'var(--surface-2)', borderRadius: 8, border: '1px solid var(--line)' }}>
              <p style={{ margin: '0 0 0.5rem', color: 'var(--muted)' }}>
                If you lose all recovery codes AND forget your password, run this command <b>on the server laptop</b>:
              </p>
              <pre style={{ margin: 0, padding: '0.5rem', background: 'var(--surface)', borderRadius: 6, fontFamily: 'var(--font-mono)', fontSize: '0.7rem', overflowX: 'auto' }}>
{`curl -X POST http://127.0.0.1:8000/api/v1/auth/emergency-reset \\
  -H "Content-Type: application/json" \\
  -d '{"username":"admin","new_password":"NEW_PASS","superuser_key":"YOUR_KEY"}'`}
              </pre>
              <p style={{ margin: '0.5rem 0 0', color: 'var(--muted)', fontSize: '0.72rem' }}>
                Requires <code>POS_EMERGENCY_KEY</code> set in <code>backend/.env</code>. Only works from localhost.
              </p>
            </div>
          </details>
        </div>
      </div>

      {showPasswordPrompt && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ width: 'min(400px, 100%)' }}>
            <div className="modal-header">
              <h3>Regenerate Recovery Codes</h3>
              <button className="modal-close" onClick={() => { setShowPasswordPrompt(false); setAdminPassword(''); }} aria-label="Close" disabled={regenerating}>×</button>
            </div>
            <div className="modal-body">
              <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>
                All current unused codes will be invalidated. Enter your admin password to confirm.
              </p>
              <div className="field">
                <label>Admin Password</label>
                <input
                  type="password"
                  autoFocus
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && !regenerating) void regenerate(); }}
                  autoComplete="off"
                />
              </div>
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => { setShowPasswordPrompt(false); setAdminPassword(''); }} disabled={regenerating}>Cancel</button>
              <button className="primary" onClick={regenerate} disabled={regenerating || !adminPassword}>
                {regenerating ? 'Generating…' : 'Regenerate'}
              </button>
            </div>
          </div>
        </div>
      )}

      {newCodes && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ width: 'min(620px, 100%)' }}>
            <div className="modal-header">
              <h3>New Recovery Codes</h3>
              <button className="modal-close" onClick={() => setNewCodes(null)} aria-label="Close">×</button>
            </div>
            <div className="modal-body">
              <RecoveryCodesDisplay
                codes={newCodes}
                title=""
                subtitle=""
                onClose={() => setNewCodes(null)}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}