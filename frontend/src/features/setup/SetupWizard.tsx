import { useState } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';

type Props = {
  onComplete: () => void;
};

type Step = 1 | 2 | 3 | 4;

const STEP_LABELS: Record<Step, string> = {
  1: 'Welcome',
  2: 'Shop',
  3: 'Admin',
  4: 'Done',
};

export function SetupWizard({ onComplete }: Props) {
  const [step, setStep] = useState<Step>(1);
  const [shop, setShop] = useState({ name: '', address: '', phone: '', email: '' });
  const [admin, setAdmin] = useState({
    username: '',
    password: '',
    confirm: '',
    display_name: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  function validateShop(): boolean {
    const e: Record<string, string> = {};
    if (!shop.name.trim()) e.name = 'Shop name is required';
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
      await api('/setup/initialize', {
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
    return (
      <div className="setup-stepper">
        {([1, 2, 3, 4] as Step[]).map((n) => {
          const isActive = step === n;
          const isComplete = step > n;
          const cls = `step${isActive ? ' active' : ''}${isComplete ? ' complete' : ''}`;
          return (
            <div key={n} className={cls}>
              <div className="step-circle">{isComplete ? '✓' : n}</div>
              <span className="step-label">{STEP_LABELS[n]}</span>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="setup-wizard-page">
      <div className="setup-wizard-card">
        <Stepper />

        {step === 1 && (
          <>
            <div className="setup-step-content" style={{ textAlign: 'center' }}>
              <h1 style={{ fontSize: '1.6rem', margin: '0 0 0.5rem', letterSpacing: '-0.02em' }}>
                Welcome to <span style={{ color: 'var(--accent)' }}>Lovely Tech POS</span>
              </h1>
              <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
                Let's set up your shop in 3 quick steps — shop details, then your admin account.
              </p>
            </div>
            <div className="setup-actions" style={{ justifyContent: 'center' }}>
              <button className="primary" onClick={() => setStep(2)}>Get Started →</button>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div className="setup-step-content">
              <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>Shop information</h2>
              <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>
                This appears on receipts, login and header. You can change it later in Settings.
              </p>
              <div className="setup-form-row">
                <label>Shop Name *</label>
                <input
                  autoFocus
                  value={shop.name}
                  onChange={(e) => setShop({ ...shop, name: e.target.value })}
                  placeholder="e.g. Lovely Tech"
                  maxLength={150}
                />
                {errors.name && <span className="setup-error">{errors.name}</span>}
              </div>
              <div className="setup-form-row">
                <label>Address</label>
                <input
                  value={shop.address}
                  onChange={(e) => setShop({ ...shop, address: e.target.value })}
                  placeholder="Street, city"
                  maxLength={255}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div className="setup-form-row">
                  <label>Phone</label>
                  <input
                    value={shop.phone}
                    onChange={(e) => setShop({ ...shop, phone: e.target.value })}
                    placeholder="07X XXX XXXX"
                    maxLength={50}
                  />
                </div>
                <div className="setup-form-row">
                  <label>Email</label>
                  <input
                    type="email"
                    value={shop.email}
                    onChange={(e) => setShop({ ...shop, email: e.target.value })}
                    placeholder="shop@example.com"
                    maxLength={120}
                  />
                </div>
              </div>
            </div>
            <div className="setup-actions">
              <button className="btn-secondary" onClick={() => setStep(1)}>← Back</button>
              <button
                className="primary"
                onClick={() => { if (validateShop()) setStep(3); }}
              >
                Continue →
              </button>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div className="setup-step-content">
              <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>Admin account</h2>
              <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>
                This is the first admin account. You'll use it to log in after setup.
              </p>
              <div className="setup-form-row">
                <label>Username *</label>
                <input
                  autoFocus
                  value={admin.username}
                  onChange={(e) => setAdmin({ ...admin, username: e.target.value })}
                  placeholder="admin"
                  maxLength={80}
                  autoComplete="off"
                />
                {errors.username && <span className="setup-error">{errors.username}</span>}
              </div>
              <div className="setup-form-row">
                <label>Display Name *</label>
                <input
                  value={admin.display_name}
                  onChange={(e) => setAdmin({ ...admin, display_name: e.target.value })}
                  placeholder="Your name"
                  maxLength={150}
                />
                {errors.display_name && <span className="setup-error">{errors.display_name}</span>}
              </div>
              <div className="setup-form-row">
                <label>Password *</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={admin.password}
                    onChange={(e) => setAdmin({ ...admin, password: e.target.value })}
                    placeholder="At least 8 characters"
                    maxLength={200}
                    autoComplete="new-password"
                    style={{ width: '100%', paddingRight: '2.4rem' }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    style={{
                      position: 'absolute',
                      right: 6,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'transparent',
                      border: 0,
                      cursor: 'pointer',
                      fontSize: '1rem',
                      color: 'var(--muted)',
                    }}
                  >
                    {showPassword ? '🙈' : '👁'}
                  </button>
                </div>
                {errors.password && <span className="setup-error">{errors.password}</span>}
              </div>
              <div className="setup-form-row">
                <label>Confirm Password *</label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={admin.confirm}
                  onChange={(e) => setAdmin({ ...admin, confirm: e.target.value })}
                  placeholder="Re-enter password"
                  maxLength={200}
                  autoComplete="new-password"
                />
                {errors.confirm && <span className="setup-error">{errors.confirm}</span>}
              </div>
            </div>
            <div className="setup-actions">
              <button className="btn-secondary" onClick={() => setStep(2)} disabled={submitting}>
                ← Back
              </button>
              <button className="primary" onClick={submit} disabled={submitting}>
                {submitting ? 'Creating account…' : 'Create Account & Finish'}
              </button>
            </div>
          </>
        )}

        {step === 4 && (
          <>
            <div className="setup-step-content" style={{ textAlign: 'center', padding: '1rem 0' }}>
              <div
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: '50%',
                  background: 'rgba(22, 163, 74, 0.15)',
                  color: '#16a34a',
                  display: 'grid',
                  placeItems: 'center',
                  fontSize: '2rem',
                  margin: '0 auto 1rem',
                }}
              >
                ✓
              </div>
              <h2 style={{ fontSize: '1.35rem', margin: '0 0 0.5rem' }}>You're all set!</h2>
              <p className="muted" style={{ margin: '0 0 0.5rem', lineHeight: 1.6 }}>
                <b style={{ color: 'var(--text)' }}>{shop.name}</b> has been created with admin account{' '}
                <b style={{ color: 'var(--text)' }}>{admin.username}</b>.
              </p>
              <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                You can now log in with your admin credentials.
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