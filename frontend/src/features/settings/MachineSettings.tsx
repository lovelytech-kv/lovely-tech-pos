import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';

type MachineRole = 'SERVER' | 'CLIENT';

interface MachineIdentity {
  machine_role: MachineRole;
  machine_name: string | null;
  server_url: string | null;
  registered_at: string;
  last_seen_at: string | null;
}

type ConnResult = { ok: boolean; message: string; shopName?: string };

const URL_REGEX = /^https?:\/\/.+:\d+$/;

async function verifyAdmin(serverUrl: string, username: string, password: string): Promise<{ valid: boolean; shopName?: string; message?: string }> {
  try {
    const result = await api<{ valid: boolean; shop_name?: string; reason_message?: string }>('/machine/verify-admin', {
      method: 'POST',
      body: JSON.stringify({
        server_url: serverUrl,
        admin_username: username,
        admin_password: password,
      }),
    });
    if (result.valid) return { valid: true, shopName: result.shop_name || undefined };
    return { valid: false, message: result.reason_message || 'Verification failed' };
  } catch (e) {
    return { valid: false, message: (e as Error).message || 'Verification failed' };
  }
}

export function MachineSettings({ isAdmin }: { isAdmin: boolean }) {
  const [identity, setIdentity] = useState<MachineIdentity | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [nameTouched, setNameTouched] = useState(false);
  const [savingName, setSavingName] = useState(false);

  const [testingConn, setTestingConn] = useState(false);
  const [connResult, setConnResult] = useState<ConnResult | null>(null);

  // Role change modal (existing)
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [newRole, setNewRole] = useState<MachineRole>('SERVER');
  const [newServerUrl, setNewServerUrl] = useState('');
  const [newName, setNewName] = useState('');
  const [savingRole, setSavingRole] = useState(false);
  const [roleSubmitAttempted, setRoleSubmitAttempted] = useState(false);
  const [roleTouched, setRoleTouched] = useState<Record<string, boolean>>({});
  const [roleConnResult, setRoleConnResult] = useState<ConnResult | null>(null);

  // Chunk 13 — reconnect modal (CLIENT mode only)
  const [showReconnectModal, setShowReconnectModal] = useState(false);
  const [reconnectUrl, setReconnectUrl] = useState('');
  const [reconnectUser, setReconnectUser] = useState('');
  const [reconnectPwd, setReconnectPwd] = useState('');
  const [showReconnectPwd, setShowReconnectPwd] = useState(false);
  const [reconnectTouched, setReconnectTouched] = useState<Record<string, boolean>>({});
  const [reconnectTesting, setReconnectTesting] = useState(false);
  const [reconnectJoining, setReconnectJoining] = useState(false);
  const [reconnectConn, setReconnectConn] = useState<ConnResult | null>(null);
  const [reconnectSubmitted, setReconnectSubmitted] = useState(false);

  async function load() {
    try {
      setLoading(true);
      setLoadError(null);
      const result = await api<MachineIdentity>('/machine/identity');
      setIdentity(result);
      setName(result.machine_name ?? '');
    } catch (e) {
      setLoadError((e as Error).message || 'Failed to load machine identity');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const nameErr = useMemo(() => {
    const t = name.trim();
    if (t.length === 0) return null;
    if (t.length > 100) return `Too long (${t.length}/100)`;
    return null;
  }, [name]);

  const nameChanged = identity ? name.trim() !== (identity.machine_name ?? '') : false;
  const canSaveName = isAdmin && nameChanged && !nameErr && !savingName;

  async function saveName() {
    if (!canSaveName) return;
    try {
      setSavingName(true);
      const result = await api<MachineIdentity>('/machine/identity', {
        method: 'PUT',
        body: JSON.stringify({
          machine_role: identity!.machine_role,
          machine_name: name.trim() || null,
          server_url: identity!.machine_role === 'CLIENT' ? identity!.server_url : null,
        }),
      });
      setIdentity(result);
      setName(result.machine_name ?? '');
      toast.success('Machine name saved. Audit log recorded.');
    } catch (e) {
      toast.error((e as Error).message || 'Save failed');
    } finally {
      setSavingName(false);
    }
  }

  // Test using health+shop public (existing Chunk 12b pattern)
  async function testConnection() {
    if (!identity?.server_url) { setConnResult({ ok: false, message: 'No server URL configured' }); return; }
    setTestingConn(true);
    setConnResult(null);
    const clean = identity.server_url.replace(/\/$/, '');
    const apiBase = clean.endsWith('/api/v1') ? clean : `${clean}/api/v1`;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 5000);
    try {
      for (const u of [`${apiBase}/health`, `${clean}/health`]) {
        try {
          const res = await fetch(u, { signal: controller.signal, cache: 'no-store' });
          if (res.ok) {
            const body = await res.json();
            if (body?.status === 'ok') {
              let shopName: string | undefined;
              try {
                const s = await fetch(`${apiBase}/branch/public`, { signal: controller.signal, cache: 'no-store' });
                if (s.ok) { const p = await s.json(); if (typeof p?.name === 'string') shopName = p.name; }
              } catch { /* ignore */ }
              setConnResult({ ok: true, message: 'Connected', shopName });
              return;
            }
          }
        } catch { /* try next */ }
      }
      setConnResult({ ok: false, message: 'Server not reachable' });
    } catch {
      setConnResult({ ok: false, message: 'Server not reachable' });
    } finally {
      window.clearTimeout(timer);
      setTestingConn(false);
    }
  }

  const roleUrlErr = useMemo(() => {
    if (newRole !== 'CLIENT') return null;
    const t = newServerUrl.trim();
    if (!t) return 'Server URL is required for CLIENT mode';
    if (t.length > 255) return `Too long (${t.length}/255)`;
    if (!URL_REGEX.test(t)) return 'Format: http://host:port';
    return null;
  }, [newRole, newServerUrl]);

  const roleNameErr = useMemo(() => {
    const t = newName.trim();
    if (t.length === 0) return null;
    if (t.length > 100) return `Too long (${t.length}/100)`;
    return null;
  }, [newName]);

  const canSubmitRole = !savingRole && (newRole === 'SERVER' || (!roleUrlErr && roleConnResult?.ok === true)) && !roleNameErr;

  function openRoleModal() {
    if (!identity) return;
    setNewRole(identity.machine_role);
    setNewServerUrl(identity.server_url ?? '');
    setNewName(identity.machine_name ?? '');
    setRoleConnResult(null);
    setRoleTouched({});
    setRoleSubmitAttempted(false);
    setShowRoleModal(true);
  }
  function closeRoleModal() {
    if (savingRole) return;
    setShowRoleModal(false);
    setRoleConnResult(null);
  }

  async function testRoleConn() {
    if (!newServerUrl.trim() || roleUrlErr) {
      setRoleConnResult({ ok: false, message: roleUrlErr ?? 'Enter a valid URL first' });
      return;
    }
    const r = await verifyAdmin(newServerUrl.trim(), 'placeholder', 'placeholder');
    // For role change we just need to know the server is reachable — use public health endpoint
    const clean = newServerUrl.trim().replace(/\/$/, '');
    const apiBase = clean.endsWith('/api/v1') ? clean : `${clean}/api/v1`;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 5000);
    try {
      for (const u of [`${apiBase}/health`, `${clean}/health`]) {
        try {
          const res = await fetch(u, { signal: controller.signal, cache: 'no-store' });
          if (res.ok) {
            const body = await res.json();
            if (body?.status === 'ok') { setRoleConnResult({ ok: true, message: 'Connected' }); return; }
          }
        } catch { /* next */ }
      }
      setRoleConnResult({ ok: false, message: 'Server not reachable' });
    } finally {
      window.clearTimeout(timer);
      if (!roleConnResult) { /* noop */ }
      void r; // avoid unused
    }
  }

  async function submitRoleChange() {
    setRoleSubmitAttempted(true);
    setRoleTouched({ newRole: true, newServerUrl: true, newName: true });
    if (!canSubmitRole) { toast.error('Please fix the highlighted fields'); return; }
    try {
      setSavingRole(true);
      await api<MachineIdentity>('/machine/identity', {
        method: 'PUT',
        body: JSON.stringify({
          machine_role: newRole,
          machine_name: newName.trim() || null,
          server_url: newRole === 'CLIENT' ? newServerUrl.trim() : null,
        }),
      });
      toast.success('Machine role updated. Audit log recorded. Reloading…');
      window.setTimeout(() => window.location.reload(), 1200);
    } catch (e) {
      toast.error((e as Error).message || 'Role change failed');
      setSavingRole(false);
    }
  }

  // Reconnect flow
  const reconnectUrlErr = useMemo(() => {
    const t = reconnectUrl.trim();
    if (!t) return 'Server URL is required';
    if (t.length > 255) return `Too long (${t.length}/255)`;
    if (!URL_REGEX.test(t)) return 'Format: http://host:port';
    return null;
  }, [reconnectUrl]);
  const reconnectUserErr = useMemo(() => {
    const t = reconnectUser.trim();
    if (!t) return 'Username is required';
    if (t.length < 3) return 'At least 3 characters';
    return null;
  }, [reconnectUser]);
  const reconnectPwdErr = useMemo(() => {
    if (!reconnectPwd) return 'Password is required';
    if (reconnectPwd.length < 8) return 'At least 8 characters';
    return null;
  }, [reconnectPwd]);
  const canReconnectTest = !reconnectUrlErr && !reconnectUserErr && !reconnectPwdErr && !reconnectTesting && !reconnectJoining;
  const canReconnectJoin = canReconnectTest && reconnectConn?.ok === true && !reconnectJoining;

  function openReconnectModal() {
    if (!identity) return;
    setReconnectUrl(identity.server_url ?? '');
    setReconnectUser('');
    setReconnectPwd('');
    setReconnectConn(null);
    setReconnectTouched({});
    setReconnectSubmitted(false);
    setShowReconnectModal(true);
  }
  function closeReconnectModal() {
    if (reconnectJoining) return;
    setShowReconnectModal(false);
    setReconnectConn(null);
  }

  async function testReconnect() {
    if (!canReconnectTest) return;
    setReconnectTesting(true);
    setReconnectConn(null);
    try {
      const r = await verifyAdmin(reconnectUrl.trim(), reconnectUser.trim(), reconnectPwd);
      setReconnectConn(r.valid ? { ok: true, message: 'Connected', shopName: r.shopName } : { ok: false, message: r.message || 'Verification failed' });
    } finally {
      setReconnectTesting(false);
    }
  }

  async function submitReconnect() {
    setReconnectSubmitted(true);
    setReconnectTouched({ url: true, username: true, password: true });
    if (!canReconnectJoin) { toast.error('Please fix the highlighted fields and test connection'); return; }
    try {
      setReconnectJoining(true);
      await api('/machine/join', {
        method: 'POST',
        body: JSON.stringify({
          server_url: reconnectUrl.trim(),
          admin_username: reconnectUser.trim(),
          admin_password: reconnectPwd,
          machine_name: identity?.machine_name || null,
        }),
      });
      toast.success('Reconnected. Reloading…');
      window.setTimeout(() => window.location.reload(), 1200);
    } catch (e) {
      toast.error((e as Error).message || 'Reconnect failed');
      setReconnectJoining(false);
    }
  }

  if (loading) {
    return (
      <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
        <div className="settings-card-title"><div><h3>Machine Role &amp; Connection</h3><p className="muted">Loading…</p></div><span className="settings-symbol">🖥</span></div>
        <div style={{ textAlign: 'center', padding: '1rem' }}><span className="spinner" /></div>
      </div>
    );
  }
  if (loadError || !identity) {
    return (
      <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
        <div className="settings-card-title"><div><h3>Machine Role &amp; Connection</h3><p className="muted">Could not load machine identity.</p></div><span className="settings-symbol">🖥</span></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <p className="muted" style={{ margin: 0, fontSize: '0.8rem' }}>{loadError ?? 'Machine identity not available'}</p>
          <button type="button" className="btn-secondary" onClick={() => void load()}>Retry</button>
        </div>
      </div>
    );
  }

  const isServer = identity.machine_role === 'SERVER';

  return (
    <>
      <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
        <div className="settings-card-title">
          <div><h3>Machine Role &amp; Connection</h3><p className="muted">This laptop's role on the shop network. Role changes require reboot.</p></div>
          <span className="settings-symbol">🖥</span>
        </div>
        <div style={{ display: 'grid', gap: '0.85rem' }}>
          <div className="machine-info-grid">
            <div>
              <small>Current Role</small>
              <div><span className={`machine-role-badge ${isServer ? 'role-server' : 'role-client'}`}>{isServer ? '🖥 SERVER' : '🔗 CLIENT'}</span></div>
            </div>
            <div><small>Registered</small><b style={{ fontSize: '0.82rem' }}>{identity.registered_at ? new Date(identity.registered_at).toLocaleString() : '—'}</b></div>
            <div><small>Last Seen</small><b style={{ fontSize: '0.82rem' }}>{identity.last_seen_at ? new Date(identity.last_seen_at).toLocaleString() : '—'}</b></div>
          </div>

          {isServer ? (
            <p className="muted" style={{ fontSize: '0.78rem', margin: 0 }}>This machine stores all shop data. Other laptops connect to it over the LAN.</p>
          ) : (
            <div className="server-url-input-wrap">
              <div style={{ flex: 1 }}>
                <small className="muted" style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.03em' }}>Connected Server</small>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
                  {identity.server_url || <span style={{ color: '#dc2626' }}>⚠ No server URL configured</span>}
                </div>
              </div>
              <button type="button" className="btn-secondary" onClick={() => void testConnection()} disabled={testingConn || !identity.server_url}>
                {testingConn ? 'Testing…' : 'Test Connection'}
              </button>
            </div>
          )}

          {connResult && (
            <div className={`connection-status ${connResult.ok ? 'ok' : 'fail'}`}>
              {connResult.ok ? '✓' : '✕'} {connResult.message}{connResult.shopName && ` — ${connResult.shopName}`}
            </div>
          )}

          <div className="setup-form-row" style={{ marginTop: '0.25rem' }}>
            <label>Machine Name <span className="muted" style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>(optional, max 100)</span></label>
            <input value={name} onChange={(e) => setName(e.target.value)} onBlur={() => setNameTouched(true)} maxLength={100} disabled={!isAdmin || savingName} placeholder="e.g. Cashier Desk 1" className={nameTouched && nameErr ? 'input-error' : ''} />
            <small className="muted" style={{ fontSize: '0.7rem' }}>{name.length}/100</small>
            {nameTouched && nameErr && <span className="field-error">{nameErr}</span>}
          </div>

          {isAdmin && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button type="button" className="primary" onClick={() => void saveName()} disabled={!canSaveName}>{savingName ? 'Saving…' : 'Save Machine Name'}</button>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {!isServer && (
                  <button type="button" className="btn-secondary" onClick={openReconnectModal}>Reconnect to Server…</button>
                )}
                <button type="button" className="btn-secondary" onClick={openRoleModal} style={{ color: '#dc2626', borderColor: 'rgba(220, 38, 38, 0.3)' }}>Change Role…</button>
              </div>
            </div>
          )}
          {!isAdmin && <p className="muted" style={{ fontSize: '0.75rem', margin: 0 }}>Only admin can edit machine settings.</p>}
        </div>
      </div>

      {/* Role change modal (unchanged from Chunk 12b) */}
      {showRoleModal && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ width: 'min(520px, 100%)' }}>
            <div className="modal-header">
              <h3>Change Machine Role</h3>
              <button className="modal-close" onClick={closeRoleModal} disabled={savingRole} aria-label="Close">×</button>
            </div>
            <div className="modal-body">
              <div className="recovery-warning" style={{ marginBottom: '0.5rem' }}>
                <b>⚠ Warning:</b> Changing machine role will affect which server this machine connects to. The app will reload after saving.
              </div>
              {roleSubmitAttempted && (roleUrlErr || roleNameErr) && (
                <div className="modal-error-banner">
                  <div className="modal-error-banner-title"><span>⚠</span> Please fix:</div>
                  <ul className="modal-error-banner-list">
                    {roleUrlErr && <li>{roleUrlErr}</li>}
                    {roleNameErr && <li>{roleNameErr}</li>}
                  </ul>
                </div>
              )}
              <div className="field">
                <label>Role</label>
                <div className="segmented-control" role="group">
                  <button type="button" className={newRole === 'SERVER' ? 'selected' : ''} onClick={() => { setNewRole('SERVER'); setRoleConnResult(null); }} disabled={savingRole}>SERVER</button>
                  <button type="button" className={newRole === 'CLIENT' ? 'selected' : ''} onClick={() => setNewRole('CLIENT')} disabled={savingRole}>CLIENT</button>
                </div>
              </div>
              {newRole === 'CLIENT' && (
                <div className="field">
                  <label>Server URL *</label>
                  <div className="server-url-input-wrap">
                    <input type="text" value={newServerUrl} onChange={(e) => { setNewServerUrl(e.target.value); setRoleConnResult(null); }} onBlur={() => setRoleTouched((t) => ({ ...t, newServerUrl: true }))} placeholder="http://192.168.1.10:8000" maxLength={255} disabled={savingRole} className={(roleTouched.newServerUrl || roleSubmitAttempted) && roleUrlErr ? 'input-error' : ''} />
                    <button type="button" className="btn-secondary" onClick={() => void testRoleConn()} disabled={savingRole || !newServerUrl.trim()}>
                      Test
                    </button>
                  </div>
                  <small className="muted" style={{ fontSize: '0.7rem' }}>Format: http://host:port · must test successfully before saving</small>
                  {(roleTouched.newServerUrl || roleSubmitAttempted) && roleUrlErr && <span className="field-error">{roleUrlErr}</span>}
                  {roleConnResult && <div className={`connection-status ${roleConnResult.ok ? 'ok' : 'fail'}`}>{roleConnResult.ok ? '✓' : '✕'} {roleConnResult.message}{roleConnResult.shopName && ` — ${roleConnResult.shopName}`}</div>}
                </div>
              )}
              <div className="field">
                <label>Machine Name (optional)</label>
                <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} onBlur={() => setRoleTouched((t) => ({ ...t, newName: true }))} maxLength={100} disabled={savingRole} placeholder="e.g. Cashier Desk 1" className={(roleTouched.newName || roleSubmitAttempted) && roleNameErr ? 'input-error' : ''} />
                <small className="muted" style={{ fontSize: '0.7rem' }}>{newName.length}/100</small>
                {(roleTouched.newName || roleSubmitAttempted) && roleNameErr && <span className="field-error">{roleNameErr}</span>}
              </div>
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={closeRoleModal} disabled={savingRole}>Cancel</button>
              <button className="primary" onClick={() => void submitRoleChange()} disabled={!canSubmitRole}>{savingRole ? 'Saving…' : 'Change Role & Reload'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Reconnect modal (Chunk 13) */}
      {showReconnectModal && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ width: 'min(520px, 100%)' }}>
            <div className="modal-header">
              <h3>Reconnect to Server</h3>
              <button className="modal-close" onClick={closeReconnectModal} disabled={reconnectJoining} aria-label="Close">×</button>
            </div>
            <div className="modal-body">
              <p className="muted" style={{ fontSize: '0.82rem', margin: 0 }}>
                Verify with an admin account from the server. Current machine name and local data are preserved.
              </p>
              {reconnectSubmitted && (reconnectUrlErr || reconnectUserErr || reconnectPwdErr) && (
                <div className="modal-error-banner">
                  <div className="modal-error-banner-title"><span>⚠</span> Please fix:</div>
                  <ul className="modal-error-banner-list">
                    {reconnectUrlErr && <li>{reconnectUrlErr}</li>}
                    {reconnectUserErr && <li>{reconnectUserErr}</li>}
                    {reconnectPwdErr && <li>{reconnectPwdErr}</li>}
                  </ul>
                </div>
              )}
              <div className="field">
                <label>Server URL *</label>
                <div className="server-url-input-wrap">
                  <input type="text" value={reconnectUrl} onChange={(e) => { setReconnectUrl(e.target.value); setReconnectConn(null); }} onBlur={() => setReconnectTouched((t) => ({ ...t, url: true }))} placeholder="http://192.168.1.10:8000" maxLength={255} className={(reconnectTouched.url || reconnectSubmitted) && reconnectUrlErr ? 'input-error' : ''} />
                  <button type="button" className="btn-secondary" onClick={() => void testReconnect()} disabled={!canReconnectTest}>{reconnectTesting ? 'Testing…' : 'Test'}</button>
                </div>
                <small className="muted" style={{ fontSize: '0.7rem' }}>{reconnectUrl.length}/255</small>
                {(reconnectTouched.url || reconnectSubmitted) && reconnectUrlErr && <span className="field-error">{reconnectUrlErr}</span>}
              </div>
              <div className="field">
                <label>Admin Username *</label>
                <input type="text" value={reconnectUser} onChange={(e) => { setReconnectUser(e.target.value); setReconnectConn(null); }} onBlur={() => setReconnectTouched((t) => ({ ...t, username: true }))} placeholder="admin" maxLength={80} autoComplete="off" className={(reconnectTouched.username || reconnectSubmitted) && reconnectUserErr ? 'input-error' : ''} />
                {(reconnectTouched.username || reconnectSubmitted) && reconnectUserErr && <span className="field-error">{reconnectUserErr}</span>}
              </div>
              <div className="field">
                <label>Admin Password *</label>
                <div className="pwd-wrapper">
                  <input type={showReconnectPwd ? 'text' : 'password'} value={reconnectPwd} onChange={(e) => { setReconnectPwd(e.target.value); setReconnectConn(null); }} onBlur={() => setReconnectTouched((t) => ({ ...t, password: true }))} placeholder="Password" maxLength={200} autoComplete="off" className={(reconnectTouched.password || reconnectSubmitted) && reconnectPwdErr ? 'input-error' : ''} />
                  <button type="button" className="pwd-toggle-btn" onClick={() => setShowReconnectPwd((v) => !v)} aria-label={showReconnectPwd ? 'Hide password' : 'Show password'}>{showReconnectPwd ? '🙈' : '👁'}</button>
                </div>
                {(reconnectTouched.password || reconnectSubmitted) && reconnectPwdErr && <span className="field-error">{reconnectPwdErr}</span>}
              </div>
              {reconnectConn && (
                <div className={`connection-status ${reconnectConn.ok ? 'ok' : 'fail'}`}>
                  {reconnectConn.ok ? '✓' : '✕'} {reconnectConn.message}{reconnectConn.shopName && ` — ${reconnectConn.shopName}`}
                </div>
              )}
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={closeReconnectModal} disabled={reconnectJoining}>Cancel</button>
              <button className="primary" onClick={() => void submitReconnect()} disabled={!canReconnectJoin || reconnectJoining}>{reconnectJoining ? 'Reconnecting…' : 'Reconnect'}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}