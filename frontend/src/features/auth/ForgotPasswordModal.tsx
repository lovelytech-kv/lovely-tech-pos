import { useMemo, useState } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';

type Props = {
  onClose: () => void;
  onSuccess: (username: string) => void;
};

const MIN_LEN = 8;

function strength(pwd: string) {
  const checks = {
    length: pwd.length >= MIN_LEN,
    lower: /[a-z]/.test(pwd),
    upper: /[A-Z]/.test(pwd),
    digit: /\d/.test(pwd),
    symbol: /[^a-zA-Z0-9]/.test(pwd),
  };
  const score = [checks.lower, checks.upper, checks.digit, checks.symbol].filter(Boolean).length;
  let level: 'weak' | 'medium' | 'strong' = 'weak';
  if (checks.length && score >= 3) level = 'strong';
  else if (checks.length && score >= 2) level = 'medium';
  return { checks, level };
}

export function ForgotPasswordModal({ onClose, onSuccess }: Props) {
  const [step, setStep] = useState<1 | 2>(1);
  const [username, setUsername] = useState('');
  const [code, setCode] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const s = useMemo(() => strength(newPassword), [newPassword]);
  const errPwd = !newPassword
    ? 'Password is required'
    : newPassword.length < MIN_LEN
    ? `At least ${MIN_LEN} characters (${newPassword.length}/${MIN_LEN})`
    : null;
  const errConfirm = !confirm
    ? 'Please confirm the password'
    : confirm !== newPassword
    ? 'Passwords do not match'
    : null;
  const canSubmitReset = !errPwd && !errConfirm;

  async function verifyCode() {
    setError('');
    if (!username.trim()) {
      setError('Enter your username');
      return;
    }
    if (!code.trim()) {
      setError('Enter one of your recovery codes');
      return;
    }
    try {
      setBusy(true);
      const result = await api<{ valid: boolean; reset_token: string | null }>('/auth/forgot-password-verify', {
        method: 'POST',
        body: JSON.stringify({
          username: username.trim(),
          recovery_code: code.trim(),
        }),
      });
      if (!result.valid || !result.reset_token) {
        setError('Invalid username or recovery code');
        return;
      }
      setResetToken(result.reset_token);
      setStep(2);
    } catch (err) {
      const msg = (err as Error).message || '';
      if (/too many failed/i.test(msg)) {
        setError(msg);
      } else {
        setError('Invalid username or recovery code');
      }
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword() {
    setError('');
    if (!canSubmitReset) {
      setError('Please fix the highlighted fields.');
      return;
    }
    try {
      setBusy(true);
      await api('/auth/reset-password-with-token', {
        method: 'POST',
        body: JSON.stringify({
          reset_token: resetToken,
          new_password: newPassword,
        }),
      });
      toast.success('Password reset. You can now log in.');
      onSuccess(username.trim());
    } catch (err) {
      const msg = (err as Error).message || '';
      if (/invalid or expired/i.test(msg)) {
        setError('Reset token expired or already used. Please start again.');
      } else {
        setError(msg || 'Reset failed');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-header">
          <h3>{step === 1 ? 'Forgot Password — Step 1 of 2' : 'Forgot Password — Step 2 of 2'}</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close" disabled={busy}>×</button>
        </div>
        <div className="modal-body">
          {step === 1 && (
            <>
              <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>
                Enter your username and one of your recovery codes. Recovery codes were shown when you set up your admin account or last regenerated them.
              </p>
              <div className="field">
                <label>Username</label>
                <input
                  autoFocus
                  value={username}
                  onChange={(e) => { setUsername(e.target.value); setError(''); }}
                  placeholder="e.g. admin"
                  maxLength={80}
                />
              </div>
              <div className="field">
                <label>Recovery Code</label>
                <input
                  value={code}
                  onChange={(e) => { setCode(e.target.value.toUpperCase()); setError(''); }}
                  placeholder="XXXX-XXXX-XXXX"
                  style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.05em', textTransform: 'uppercase' }}
                  maxLength={20}
                />
                <small className="muted" style={{ fontSize: '0.7rem' }}>
                  Format: XXXX-XXXX-XXXX · Each code can be used once
                </small>
              </div>
              {error && <div className="error login-error" role="alert">{error}</div>}
            </>
          )}

          {step === 2 && (
            <>
              <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>
                Code verified. Set a new password for <b>{username}</b>.
              </p>
              <div className="field">
                <label>New Password</label>
                <div className="pwd-wrapper">
                  <input
                    autoFocus
                    type={showPw ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => { setNewPassword(e.target.value); setError(''); }}
                    placeholder={`Min ${MIN_LEN} characters`}
                    autoComplete="new-password"
                    maxLength={200}
                  />
                  <button type="button" className="pwd-toggle-btn" onClick={() => setShowPw((v) => !v)} aria-label={showPw ? 'Hide passwords' : 'Show passwords'}>
                    {showPw ? '🙈' : '👁'}
                  </button>
                </div>
                <div className="pwd-strength-bar" aria-hidden="true">
                  <div
                    className={`pwd-strength-fill pwd-strength-${s.level}`}
                    style={{ width: newPassword.length === 0 ? '0%' : s.level === 'weak' ? '33%' : s.level === 'medium' ? '66%' : '100%' }}
                  />
                </div>
                <div className={`pwd-strength-label pwd-strength-label-${s.level}`}>
                  {newPassword.length === 0 ? '' : s.level === 'weak' ? 'Weak' : s.level === 'medium' ? 'Medium' : 'Strong'}
                </div>
                <ul className="pwd-requirements">
                  <li className={s.checks.length ? 'met' : 'not-met'}><span className="req-icon">{s.checks.length ? '✓' : '○'}</span>At least {MIN_LEN} characters ({newPassword.length}/{MIN_LEN})</li>
                  <li className={s.checks.lower ? 'met' : 'not-met'}><span className="req-icon">{s.checks.lower ? '✓' : '○'}</span>Contains lowercase letter</li>
                  <li className={s.checks.upper ? 'met' : 'not-met'}><span className="req-icon">{s.checks.upper ? '✓' : '○'}</span>Contains uppercase letter</li>
                  <li className={s.checks.digit ? 'met' : 'not-met'}><span className="req-icon">{s.checks.digit ? '✓' : '○'}</span>Contains number</li>
                  <li className={s.checks.symbol ? 'met' : 'not-met'}><span className="req-icon">{s.checks.symbol ? '✓' : '○'}</span>Contains symbol</li>
                </ul>
                {errPwd && newPassword.length >= MIN_LEN === false && <span className="field-error">{errPwd}</span>}
              </div>
              <div className="field">
                <label>Confirm New Password</label>
                <input
                  type={showPw ? 'text' : 'password'}
                  value={confirm}
                  onChange={(e) => { setConfirm(e.target.value); setError(''); }}
                  placeholder="Repeat new password"
                  autoComplete="new-password"
                  maxLength={200}
                />
                {errConfirm && <span className="field-error">{errConfirm}</span>}
                {confirm && !errConfirm && <span className="field-ok-inline">✓ Passwords match</span>}
              </div>
              {error && <div className="error login-error" role="alert">{error}</div>}
            </>
          )}
        </div>
        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          {step === 1 ? (
            <button className="primary" onClick={verifyCode} disabled={busy || !username.trim() || !code.trim()}>
              {busy ? 'Verifying…' : 'Verify Code'}
            </button>
          ) : (
            <button className="primary" onClick={resetPassword} disabled={busy || !canSubmitReset}>
              {busy ? 'Resetting…' : 'Reset Password'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}