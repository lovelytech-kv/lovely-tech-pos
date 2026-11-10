import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';
import { RecoveryCodesDisplay } from '../users/RecoveryCodesDisplay';

type Props = { onComplete: () => void };

type MachineRole = 'SERVER' | 'CLIENT';
type JoinMode = 'SERVER_READY' | 'CLIENT_REQUIRES_AUTH' | 'SERVER_REQUIRES_SETUP';
type Step = -1 | 0 | 1 | 2 | 3 | 4 | 5;
type ConnResult = { ok: boolean; message: string; shopName?: string };

const STEP_LABELS: Record<0 | 1 | 2 | 3 | 4 | 5, string> = {
  0: 'Role',
  1: 'Welcome',
  2: 'Shop',
  3: 'Admin',
  4: 'Recovery',
  5: 'Done',
};

const URL_REGEX = /^https?:\/\/.+:\d+$/;

async function verifyAdmin(serverUrl: string, username: string, password: string): Promise<{ valid: boolean; shopName?: string; message?: string }> {
  try {
    const result = await api<{ valid: boolean; shop_name?: string; admin_display_name?: string; reason?: string; reason_message?: string }>('/machine/verify-admin', {
      method: 'POST',
      body: JSON.stringify({
        server_url: serverUrl,
        admin_username: username,
        admin_password: password,
      }),
    });
    if (result.valid) return { valid: true, shopName: result.shop_name || undefined };
    return { valid: false, message: result.reason_message || result.reason || 'Verification failed' };
  } catch (e) {
    return { valid: false, message: (e as Error).message || 'Verification failed' };
  }
}

export function SetupWizard({ onComplete }: Props) {
  const [step, setStep] = useState<Step>(0);
  const [joinMode, setJoinMode] = useState<JoinMode | null>(null);
  const [loadingMode, setLoadingMode] = useState(true);

  // Mode-select
  const [machineRole, setMachineRole] = useState<MachineRole>('SERVER');

  // Client connect
  const [clientServerUrl, setClientServerUrl] = useState('');
  const [clientUsername, setClientUsername] = useState('');
  const [clientPassword, setClientPassword] = useState('');
  const [clientMachineName, setClientMachineName] = useState('');
  const [showClientPassword, setShowClientPassword] = useState(false);
  const [clientTouched, setClientTouched] = useState<Record<string, boolean>>({});
  const [testingClient, setTestingClient] = useState(false);
  const [joiningClient, setJoiningClient] = useState(false);
  const [clientConn, setClientConn] = useState<ConnResult | null>(null);
  const [clientSubmitted, setClientSubmitted] = useState(false);

  // Server flow
  const [shop, setShop] = useState({ name: '', address: '', phone: '', email: '' });
  const [admin, setAdmin] = useState({ username: '', password: '', confirm: '', display_name: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [doneMode, setDoneMode] = useState<'SERVER' | 'CLIENT'>('SERVER');
  const [doneShopName, setDoneShopName] = useState('');
  const [doneAdminUsername, setDoneAdminUsername] = useState('');

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  // Load join_mode from backend
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const status = await api<{ join_mode?: string }>('/setup/status');
        if (!alive) return;
        const jm = (status.join_mode || 'SERVER_REQUIRES_SETUP') as JoinMode;
        setJoinMode(jm);
        if (jm === 'CLIENT_REQUIRES_AUTH') {
          setStep(-1);
        } else {
          setStep(0);
        }
      } catch {
        if (alive) {
          setJoinMode('SERVER_REQUIRES_SETUP');
          setStep(0);
        }
      } finally {
        if (alive) setLoadingMode(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  // Client form validation
  const clientUrlErr = useMemo(() => {
    const v = clientServerUrl.trim();
    if (!v) return 'Server URL is required';
    if (v.length > 255) return `Too long (${v.length}/255)`;
    if (!URL_REGEX.test(v)) return 'Format: http://host:port (e.g. http://192.168.1.10:8000)';
    return null;
  }, [clientServerUrl]);

  const clientUserErr = useMemo(() => {
    const v = clientUsername.trim();
    if (!v) return 'Username is required';
    if (v.length < 3) return 'At least 3 characters';
    if (v.length > 80) return 'Too long (max 80)';
    return null;
  }, [clientUsername]);

  const clientPwdErr = useMemo(() => {
    if (!clientPassword) return 'Password is required';
    if (clientPassword.length < 8) return 'At least 8 characters';
    if (clientPassword.length > 200) return 'Too long (max 200)';
    return null;
  }, [clientPassword]);

  const clientNameErr = useMemo(() => {
    if (clientMachineName.length > 100) return 'Too long (max 100)';
    return null;
  }, [clientMachineName]);

  const canClientTest = !clientUrlErr && !clientUserErr && !clientPwdErr && !testingClient && !joiningClient;
  const canClientJoin = canClientTest && clientConn?.ok === true && !joiningClient;

  async function testClientConn() {
    if (!canClientTest) return;
    setTestingClient(true);
    setClientConn(null);
    try {
      const result = await verifyAdmin(clientServerUrl.trim(), clientUsername.trim(), clientPassword);
      if (result.valid) {
        setClientConn({ ok: true, message: 'Connected', shopName: result.shopName });
      } else {
        setClientConn({ ok: false, message: result.message || 'Verification failed' });
      }
    } finally {
      setTestingClient(false);
    }
  }

  async function submitClientJoin() {
    setClientSubmitted(true);
    setClientTouched({ url: true, username: true, password: true, name: true });
    if (!canClientJoin) {
      toast.error('Please fix the highlighted fields and test the connection');
      return;
    }
    setJoiningClient(true);
    try {
      const result = await api<{ success: boolean; machine_role: string; server_url: string; shop_uuid: string }>('/machine/join', {
        method: 'POST',
        body: JSON.stringify({
          server_url: clientServerUrl.trim(),
          admin_username: clientUsername.trim(),
          admin_password: clientPassword,
          machine_name: clientMachineName.trim() || null,
        }),
      });
      setDoneMode('CLIENT');
      setDoneShopName(clientConn?.shopName || 'your shop server');
      setDoneAdminUsername(clientUsername.trim());
      setStep(5);
      toast.success(`Joined ${clientConn?.shopName || 'server'} successfully`);
    } catch (e) {
      toast.error((e as Error).message || 'Join failed');
      setClientConn({ ok: false, message: (e as Error).message || 'Join failed' });
    } finally {
      setJoiningClient(false);
    }
  }

  function validateShop(): boolean {
    const e: Record<string, string> = {};
    if (!shop.name.trim()) e.name = 'Shop name is required';
    else if (shop.name.trim().length > 150) e.name = `Too long (${shop.name.trim().length}/150)`;
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function validateAdmin(): boolean {
    const e: Record<string, string> = {};
    if (admin.username.trim().length < 3) e.username = 'At least 3 characters';
    else if (admin.username.trim().length > 80) e.username = 'Too long (max 80)';
    if (!admin.display_name.trim()) e.display_name = 'Display name is required';
    if (admin.password.length < 8) e.password = 'At least 8 characters';
    if (admin.password !== admin.confirm) e.confirm = 'Passwords do not match';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submitServer() {
    if (!validateAdmin()) return;
    setSubmitting(true);
    try {
      const result = await api<{ recovery_codes?: string[] }>('/setup/initialize', {
        method: 'POST',
        body: JSON.stringify({
          shop: {
            name: shop.name.trim(),
            address: shop.address.trim() || null,
            phone: shop.phone.trim() || null,
            email: shop.email.trim() || null,
          },
          admin: {
            username: admin.username.trim(),
            password: admin.password,
            display_name: admin.display_name.trim(),
          },
        }),
      });
      try {
        localStorage.removeItem('ltpos_token');
        localStorage.removeItem('ltpos_user');
      } catch { /* ignore */ }
      setDoneMode('SERVER');
      setDoneShopName(shop.name.trim());
      setDoneAdminUsername(admin.username.trim());
      setRecoveryCodes(result.recovery_codes || []);
      setStep(4);
    } catch (err) {
      const msg = (err as Error).message || '';
      if (/already init|409/i.test(msg)) {
        toast.error('Setup already completed. Reloading…');
        window.setTimeout(() => onComplete(), 1200);
      } else {
        toast.error(msg || 'Setup failed');
      }
    } finally {
      setSubmitting(false);
    }
  }

  function Stepper() {
    if (step === -1) {
      return (
        <div className="setup-stepper" style={{ gridTemplateColumns: '1fr' }}>
          <div className="step active">
            <div className="step-circle">🔗</div>
            <span className="step-label">Connect to Server</span>
          </div>
        </div>
      );
    }
    const steps: (0 | 1 | 2 | 3 | 4 | 5)[] = [0, 1, 2, 3, 4, 5];
    return (
      <div className="setup-stepper" style={{ gridTemplateColumns: `repeat(${steps.length}, 1fr)` }}>
        {steps.map((n) => {
          const isActive = step === n;
          const isComplete = step > n;
          const cls = `step${isActive ? ' active' : ''}${isComplete ? ' complete' : ''}`;
          return (
            <div key={n} className={cls}>
              <div className="step-circle">{isComplete ? '✓' : n === 0 ? '⚙' : n}</div>
              <span className="step-label">{STEP_LABELS[n]}</span>
            </div>
          );
        })}
      </div>
    );
  }

  if (loadingMode) {
    return (
      <div className="setup-wizard-page">
        <div className="setup-wizard-card" style={{ width: 'min(620px, 100%)', textAlign: 'center', padding: '2rem' }}>
          <span className="spinner spinner-lg" />
          <p className="muted" style={{ marginTop: '0.75rem' }}>Checking setup status…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="setup-wizard-page">
      <div className="setup-wizard-card" style={{ width: 'min(620px, 100%)' }}>
        <Stepper />

        {/* Step -1: CLIENT connect (standalone or chosen via step 0) */}
        {step === -1 && (
          <>
            <div className="setup-step-content">
              <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>Connect to your shop server</h2>
              <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>
                Enter the server URL and an existing admin account from that server. This laptop will be configured as a CLIENT.
              </p>

              {clientSubmitted && (clientUrlErr || clientUserErr || clientPwdErr) && (
                <div className="modal-error-banner">
                  <div className="modal-error-banner-title"><span>⚠</span> Please fix:</div>
                  <ul className="modal-error-banner-list">
                    {clientUrlErr && <li>{clientUrlErr}</li>}
                    {clientUserErr && <li>Username: {clientUserErr}</li>}
                    {clientPwdErr && <li>Password: {clientPwdErr}</li>}
                  </ul>
                </div>
              )}

              <div className="setup-form-row">
                <label>Server URL *</label>
                <div className="server-url-input-wrap">
                  <input
                    type="text"
                    value={clientServerUrl}
                    onChange={(e) => { setClientServerUrl(e.target.value); setClientConn(null); }}
                    onBlur={() => setClientTouched((t) => ({ ...t, url: true }))}
                    placeholder="http://192.168.1.10:8000"
                    maxLength={255}
                    className={(clientTouched.url || clientSubmitted) && clientUrlErr ? 'input-error' : ''}
                  />
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => void testClientConn()}
                    disabled={!canClientTest}
                  >
                    {testingClient ? 'Testing…' : 'Test'}
                  </button>
                </div>
                <small className="muted" style={{ fontSize: '0.7rem' }}>{clientServerUrl.length}/255 · Format: http://host:port</small>
                {(clientTouched.url || clientSubmitted) && clientUrlErr && <span className="setup-error">{clientUrlErr}</span>}
              </div>

              <div className="setup-form-row">
                <label>Admin Username *</label>
                <input
                  type="text"
                  value={clientUsername}
                  onChange={(e) => { setClientUsername(e.target.value); setClientConn(null); }}
                  onBlur={() => setClientTouched((t) => ({ ...t, username: true }))}
                  placeholder="admin"
                  maxLength={80}
                  autoComplete="off"
                  className={(clientTouched.username || clientSubmitted) && clientUserErr ? 'input-error' : ''}
                />
                <small className="muted" style={{ fontSize: '0.7rem' }}>{clientUsername.length}/80 · min 3</small>
                {(clientTouched.username || clientSubmitted) && clientUserErr && <span className="setup-error">{clientUserErr}</span>}
              </div>

              <div className="setup-form-row">
                <label>Admin Password *</label>
                <div className="pwd-wrapper">
                  <input
                    type={showClientPassword ? 'text' : 'password'}
                    value={clientPassword}
                    onChange={(e) => { setClientPassword(e.target.value); setClientConn(null); }}
                    onBlur={() => setClientTouched((t) => ({ ...t, password: true }))}
                    placeholder="Password"
                    maxLength={200}
                    autoComplete="off"
                    className={(clientTouched.password || clientSubmitted) && clientPwdErr ? 'input-error' : ''}
                  />
                  <button type="button" className="pwd-toggle-btn" onClick={() => setShowClientPassword((v) => !v)} aria-label={showClientPassword ? 'Hide password' : 'Show password'}>
                    {showClientPassword ? '🙈' : '👁'}
                  </button>
                </div>
                <small className="muted" style={{ fontSize: '0.7rem' }}>min 8 · from your server</small>
                {(clientTouched.password || clientSubmitted) && clientPwdErr && <span className="setup-error">{clientPwdErr}</span>}
              </div>

              <div className="setup-form-row">
                <label>Machine Name (optional)</label>
                <input
                  type="text"
                  value={clientMachineName}
                  onChange={(e) => setClientMachineName(e.target.value)}
                  onBlur={() => setClientTouched((t) => ({ ...t, name: true }))}
                  placeholder="e.g. Cashier Desk 2"
                  maxLength={100}
                  className={(clientTouched.name || clientSubmitted) && clientNameErr ? 'input-error' : ''}
                />
                <small className="muted" style={{ fontSize: '0.7rem' }}>{clientMachineName.length}/100</small>
                {clientNameErr && <span className="setup-error">{clientNameErr}</span>}
              </div>

              {clientConn && (
                <div className={`connection-status ${clientConn.ok ? 'ok' : 'fail'}`}>
                  {clientConn.ok ? '✓' : '✕'} {clientConn.message}
                  {clientConn.shopName && ` — ${clientConn.shopName}`}
                </div>
              )}
            </div>
            <div className="setup-actions">
              {joinMode === 'SERVER_REQUIRES_SETUP' && (
                <button className="btn-secondary" onClick={() => setStep(0)} disabled={joiningClient}>← Back</button>
              )}
              <button className="primary" onClick={() => void submitClientJoin()} disabled={!canClientJoin || joiningClient}>
                {joiningClient ? 'Joining…' : 'Join as Client'}
              </button>
            </div>
          </>
        )}

        {/* Step 0: mode selection */}
        {step === 0 && (
          <>
            <div className="setup-step-content">
              <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>Is this the main POS server for your shop?</h2>
              <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>Choose how this machine will participate on your shop's network.</p>

              <div className="setup-role-options">
                <label className={`setup-role-option ${machineRole === 'SERVER' ? 'selected' : ''}`}>
                  <input type="radio" name="role" value="SERVER" checked={machineRole === 'SERVER'} onChange={() => setMachineRole('SERVER')} style={{ display: 'none' }} />
                  <div className="role-icon">🖥</div>
                  <div>
                    <b>Yes, this is the server</b>
                    <p className="muted" style={{ margin: '0.2rem 0 0', fontSize: '0.78rem', lineHeight: 1.4 }}>
                      This laptop will store all your shop data. Other laptops will connect to it.
                    </p>
                  </div>
                </label>

                <label className={`setup-role-option ${machineRole === 'CLIENT' ? 'selected' : ''}`}>
                  <input type="radio" name="role" value="CLIENT" checked={machineRole === 'CLIENT'} onChange={() => setMachineRole('CLIENT')} style={{ display: 'none' }} />
                  <div className="role-icon">🔗</div>
                  <div>
                    <b>No, this connects to an existing server</b>
                    <p className="muted" style={{ margin: '0.2rem 0 0', fontSize: '0.78rem', lineHeight: 1.4 }}>
                      This laptop will connect to a server laptop already running on your shop's network. You need an existing admin account.
                    </p>
                  </div>
                </label>
              </div>
            </div>
            <div className="setup-actions">
              <button className="primary" onClick={() => setStep(machineRole === 'SERVER' ? 1 : -1)}>
                Continue →
              </button>
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <div className="setup-step-content" style={{ textAlign: 'center' }}>
              <h1 style={{ fontSize: '1.6rem', margin: '0 0 0.5rem', letterSpacing: '-0.02em' }}>
                Welcome to <span style={{ color: 'var(--accent)' }}>Lovely Tech POS</span>
              </h1>
              <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
                Let's set up your shop server. You'll create your shop and admin account.
              </p>
            </div>
            <div className="setup-actions" style={{ justifyContent: 'center' }}>
              <button className="btn-secondary" onClick={() => setStep(0)}>← Back</button>
              <button className="primary" onClick={() => setStep(2)}>Get Started →</button>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div className="setup-step-content">
              <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>Shop information</h2>
              <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>This appears on receipts, login and header.</p>
              <div className="setup-form-row">
                <label>Shop Name *</label>
                <input autoFocus value={shop.name} onChange={(e) => setShop({ ...shop, name: e.target.value })} placeholder="e.g. Lovely Tech" maxLength={150} className={errors.name ? 'input-error' : ''} />
                <small className="muted" style={{ fontSize: '0.7rem' }}>{shop.name.length}/150</small>
                {errors.name && <span className="setup-error">{errors.name}</span>}
              </div>
              <div className="setup-form-row">
                <label>Address</label>
                <input value={shop.address} onChange={(e) => setShop({ ...shop, address: e.target.value })} placeholder="Street, city" maxLength={255} />
                <small className="muted" style={{ fontSize: '0.7rem' }}>{shop.address.length}/255</small>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="setup-form-row">
                  <label>Phone</label>
                  <input value={shop.phone} onChange={(e) => setShop({ ...shop, phone: e.target.value })} placeholder="07X XXX XXXX" maxLength={50} />
                  <small className="muted" style={{ fontSize: '0.7rem' }}>{shop.phone.length}/50</small>
                </div>
                <div className="setup-form-row">
                  <label>Email</label>
                  <input type="email" value={shop.email} onChange={(e) => setShop({ ...shop, email: e.target.value })} placeholder="shop@example.com" maxLength={120} />
                  <small className="muted" style={{ fontSize: '0.7rem' }}>{shop.email.length}/120</small>
                </div>
              </div>
            </div>
            <div className="setup-actions">
              <button className="btn-secondary" onClick={() => setStep(1)}>← Back</button>
              <button className="primary" onClick={() => { if (validateShop()) setStep(3); }}>Continue →</button>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div className="setup-step-content">
              <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>Admin account</h2>
              <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>First admin account. Use this to log in after setup.</p>
              <div className="setup-form-row">
                <label>Username *</label>
                <input autoFocus value={admin.username} onChange={(e) => setAdmin({ ...admin, username: e.target.value })} placeholder="admin" maxLength={80} autoComplete="off" className={errors.username ? 'input-error' : ''} />
                <small className="muted" style={{ fontSize: '0.7rem' }}>At least 3 characters, must be unique</small>
                {errors.username && <span className="setup-error">{errors.username}</span>}
              </div>
              <div className="setup-form-row">
                <label>Display Name *</label>
                <input value={admin.display_name} onChange={(e) => setAdmin({ ...admin, display_name: e.target.value })} placeholder="Your name" maxLength={150} className={errors.display_name ? 'input-error' : ''} />
                {errors.display_name && <span className="setup-error">{errors.display_name}</span>}
              </div>
              <div className="setup-form-row">
                <label>Password *</label>
                <div className="pwd-wrapper">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={admin.password}
                    onChange={(e) => setAdmin({ ...admin, password: e.target.value })}
                    placeholder="At least 8 characters"
                    maxLength={200}
                    autoComplete="new-password"
                    className={errors.password ? 'input-error' : ''}
                  />
                  <button type="button" className="pwd-toggle-btn" onClick={() => setShowPassword((v) => !v)} aria-label={showPassword ? 'Hide password' : 'Show password'}>
                    {showPassword ? '🙈' : '👁'}
                  </button>
                </div>
                <small className="muted" style={{ fontSize: '0.7rem' }}>At least 8 characters ({admin.password.length}/8)</small>
                {errors.password && <span className="setup-error">{errors.password}</span>}
              </div>
              <div className="setup-form-row">
                <label>Confirm Password *</label>
                <input type={showPassword ? 'text' : 'password'} value={admin.confirm} onChange={(e) => setAdmin({ ...admin, confirm: e.target.value })} placeholder="Re-enter password" maxLength={200} autoComplete="new-password" className={errors.confirm ? 'input-error' : ''} />
                {errors.confirm && <span className="setup-error">{errors.confirm}</span>}
              </div>
            </div>
            <div className="setup-actions">
              <button className="btn-secondary" onClick={() => setStep(2)} disabled={submitting}>← Back</button>
              <button className="primary" onClick={submitServer} disabled={submitting}>{submitting ? 'Creating account…' : 'Create Account & Continue'}</button>
            </div>
          </>
        )}

        {step === 4 && (
          <>
            <div className="setup-step-content">
              <RecoveryCodesDisplay
                codes={recoveryCodes}
                title="Save Your Recovery Codes"
                subtitle="These codes let you reset your admin password if you forget it. Save them somewhere safe — they will NOT be shown again."
                onContinue={() => setStep(5)}
              />
            </div>
          </>
        )}

        {step === 5 && (
          <>
            <div className="setup-step-content" style={{ textAlign: 'center', padding: '1rem 0' }}>
              <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'rgba(22, 163, 74, 0.15)', color: '#16a34a', display: 'grid', placeItems: 'center', fontSize: '2rem', margin: '0 auto 1rem' }}>✓</div>
              <h2 style={{ fontSize: '1.35rem', margin: '0 0 0.5rem' }}>{doneMode === 'CLIENT' ? 'Connected!' : "You're all set!"}</h2>
              {doneMode === 'CLIENT' ? (
                <>
                  <p className="muted" style={{ margin: '0 0 0.5rem', lineHeight: 1.6 }}>
                    This laptop is now connected to <b style={{ color: 'var(--text)' }}>{doneShopName}</b> as a CLIENT.
                  </p>
                  <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                    Log in with your server admin credentials (<b style={{ color: 'var(--text)' }}>{doneAdminUsername}</b>).
                  </p>
                </>
              ) : (
                <>
                  <p className="muted" style={{ margin: '0 0 0.5rem', lineHeight: 1.6 }}>
                    <b style={{ color: 'var(--text)' }}>{doneShopName}</b> has been created with admin account <b style={{ color: 'var(--text)' }}>{doneAdminUsername}</b>.
                  </p>
                  <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                    Machine role: <b style={{ color: 'var(--text)' }}>SERVER</b>. Log in with your admin credentials.
                  </p>
                </>
              )}
            </div>
            <div className="setup-actions" style={{ justifyContent: 'center' }}>
              <button className="primary" onClick={onComplete}>Go to Login →</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default SetupWizard;