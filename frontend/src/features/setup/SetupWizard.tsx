import { useState } from 'react';
import { api, login } from '../../api/client';
import { toast } from '../../ui/toast';
import { RecoveryCodesDisplay } from '../users/RecoveryCodesDisplay';

type Props = { onComplete: () => void };

type MachineRole = 'SERVER' | 'CLIENT';
type Step = 0 | 1 | 2 | 3 | 4 | 5;

const STEP_LABELS: Record<Step, string> = {
  0: 'Role',
  1: 'Welcome',
  2: 'Shop',
  3: 'Admin',
  4: 'Recovery',
  5: 'Done',
};

const URL_REGEX = /^https?:\/\/.+:\d+$/;

type ConnResult = { ok: boolean; message: string; shopName?: string };

async function testServerUrl(url: string): Promise<ConnResult> {
  const clean = url.replace(/\/$/, '');
  const apiBase = clean.endsWith('/api/v1') ? clean : `${clean}/api/v1`;
  const candidates = [`${apiBase}/health`, `${clean}/health`];

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 5000);

  try {
    let health: { status?: string } | null = null;
    let lastStatus: number | null = null;

    for (const u of candidates) {
      try {
        const res = await fetch(u, { signal: controller.signal, cache: 'no-store' });
        if (res.ok) {
          try { health = await res.json(); } catch { health = null; }
          if (health?.status === 'ok') break;
          health = null;
        } else {
          lastStatus = res.status;
        }
      } catch (e) {
        if ((e as Error).name === 'AbortError') throw e;
      }
    }

    if (!health || health.status !== 'ok') {
      if (lastStatus !== null) return { ok: false, message: `HTTP ${lastStatus}` };
      return { ok: false, message: 'Cannot reach server' };
    }

    let shopName: string | undefined;
    try {
      const shop = await fetch(`${apiBase}/branch/public`, { signal: controller.signal, cache: 'no-store' });
      if (shop.ok) {
        const s = await shop.json();
        if (typeof s?.name === 'string') shopName = s.name;
      }
    } catch { /* optional */ }
    return { ok: true, message: 'Connected', shopName };
  } catch (err) {
    if ((err as Error).name === 'AbortError') return { ok: false, message: 'Timeout (5s)' };
    return { ok: false, message: 'Cannot reach server' };
  } finally {
    window.clearTimeout(timer);
  }
}

export function SetupWizard({ onComplete }: Props) {
  const [step, setStep] = useState<Step>(0);

  // Step 0 state
  const [machineRole, setMachineRole] = useState<MachineRole>('SERVER');
  const [serverUrl, setServerUrl] = useState('');
  const [serverUrlTouched, setServerUrlTouched] = useState(false);
  const [testingConn, setTestingConn] = useState(false);
  const [connResult, setConnResult] = useState<ConnResult | null>(null);

  // Shop state
  const [shop, setShop] = useState({ name: '', address: '', phone: '', email: '' });

  // Admin state
  const [admin, setAdmin] = useState({ username: '', password: '', confirm: '', display_name: '' });
  const [showPassword, setShowPassword] = useState(false);

  // Recovery state
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const urlErr = (() => {
    if (machineRole !== 'CLIENT') return null;
    const trimmed = serverUrl.trim();
    if (!trimmed) return 'Server URL is required for CLIENT mode';
    if (!URL_REGEX.test(trimmed)) return 'Format: http://host:port (e.g. http://192.168.1.10:8000)';
    return null;
  })();

  const canProceed0 = (() => {
    if (machineRole === 'SERVER') return true;
    if (urlErr) return false;
    if (!connResult?.ok) return false;
    return true;
  })();

  async function testConn() {
    if (urlErr || !serverUrl.trim()) {
      setConnResult({ ok: false, message: urlErr ?? 'Enter a URL first' });
      return;
    }
    setTestingConn(true);
    setConnResult(null);
    try {
      const result = await testServerUrl(serverUrl.trim());
      setConnResult(result);
    } finally {
      setTestingConn(false);
    }
  }

  function validateShop(): boolean {
    const e: Record<string, string> = {};
    if (!shop.name.trim()) e.name = 'Shop name is required';
    if (shop.name.trim().length > 150) e.name = `Too long (${shop.name.trim().length}/150)`;
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function validateAdmin(): boolean {
    const e: Record<string, string> = {};
    if (admin.username.trim().length < 3) e.username = 'At least 3 characters';
    if (!admin.display_name.trim()) e.display_name = 'Display name is required';
    if (admin.password.length < 8) e.password = 'At least 8 characters';
    if (admin.password !== admin.confirm) e.confirm = 'Passwords do not match';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function submit() {
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

      // Save machine role (Chunk 12b) — requires auth, so use temporary auto-login
      try {
        await login(admin.username.trim(), admin.password);
        await api('/machine/identity', {
          method: 'PUT',
          body: JSON.stringify({
            machine_role: machineRole,
            machine_name: null,
            server_url: machineRole === 'CLIENT' ? serverUrl.trim() : null,
          }),
        });
      } catch (putErr) {
        toast.error('Setup complete, but machine role could not be saved. You can change it in Settings later.');
        console.warn('[SetupWizard] machine identity PUT failed:', putErr);
      } finally {
        try {
          localStorage.removeItem('ltpos_token');
          localStorage.removeItem('ltpos_user');
        } catch { /* ignore */ }
      }

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
    const steps: Step[] = [0, 1, 2, 3, 4, 5];
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

  return (
    <div className="setup-wizard-page">
      <div className="setup-wizard-card" style={{ width: 'min(620px, 100%)' }}>
        <Stepper />

        {step === 0 && (
          <>
            <div className="setup-step-content">
              <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>Is this the main POS server for your shop?</h2>
              <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>
                Choose how this machine will participate on your shop's network.
              </p>

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
                      This laptop will connect to a server laptop already running on your shop's network.
                    </p>
                  </div>
                </label>
              </div>

              {machineRole === 'CLIENT' && (
                <div className="setup-form-row" style={{ marginTop: '0.75rem' }}>
                  <label>Server URL *</label>
                  <div className="server-url-input-wrap">
                    <input
                      type="text"
                      value={serverUrl}
                      onChange={(e) => { setServerUrl(e.target.value); setConnResult(null); }}
                      onBlur={() => setServerUrlTouched(true)}
                      placeholder="http://192.168.1.10:8000"
                      maxLength={255}
                      className={(serverUrlTouched || serverUrl) && urlErr ? 'input-error' : ''}
                    />
                    <button type="button" className="btn-secondary" onClick={() => void testConn()} disabled={testingConn || !serverUrl.trim()}>
                      {testingConn ? 'Testing…' : 'Test'}
                    </button>
                  </div>
                  <small className="muted" style={{ fontSize: '0.7rem' }}>Format: http://host:port · must test successfully before continuing</small>
                  {(serverUrlTouched || serverUrl) && urlErr && <span className="setup-error">{urlErr}</span>}
                  {connResult && (
                    <div className={`connection-status ${connResult.ok ? 'ok' : 'fail'}`}>
                      {connResult.ok ? '✓' : '✕'} {connResult.message}
                      {connResult.shopName && ` — ${connResult.shopName}`}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="setup-actions">
              <button className="primary" onClick={() => setStep(1)} disabled={!canProceed0}>
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
                {machineRole === 'SERVER'
                  ? "Let's set up your shop server. You'll create your shop and admin account."
                  : `This machine will connect to ${serverUrl || 'the server'}. Set up local admin details.`}
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
              <button className="primary" onClick={submit} disabled={submitting}>{submitting ? 'Creating account…' : 'Create Account & Continue'}</button>
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
              <h2 style={{ fontSize: '1.35rem', margin: '0 0 0.5rem' }}>You're all set!</h2>
              <p className="muted" style={{ margin: '0 0 0.5rem', lineHeight: 1.6 }}>
                <b style={{ color: 'var(--text)' }}>{shop.name}</b> has been created with admin account <b style={{ color: 'var(--text)' }}>{admin.username}</b>.
              </p>
              <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                Machine role: <b style={{ color: 'var(--text)' }}>{machineRole}</b>. Log in with your admin credentials.
              </p>
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