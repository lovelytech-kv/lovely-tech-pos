import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../../api/client';

type Props = {
  user: any;
  onDone: (u: any) => void;
  onLogout: () => void;
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
  return { checks, score, level };
}

export function ChangePassword({ user, onDone, onLogout }: Props) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [again, setAgain] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const s = useMemo(() => strength(next), [next]);
  const errCurrent = !current ? 'Temporary password is required' : null;
  const errNext = !next
    ? 'New password is required'
    : next.length < MIN_LEN
    ? `At least ${MIN_LEN} characters (${next.length}/${MIN_LEN})`
    : next === current
    ? 'New password must be different from the current one'
    : null;
  const errAgain = !again
    ? 'Please confirm the new password'
    : again !== next
    ? 'Passwords do not match'
    : null;
  const canSubmit = !errCurrent && !errNext && !errAgain && !busy;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    if (!canSubmit) {
      setError('Please fix the highlighted fields.');
      return;
    }
    try {
      setBusy(true);
      await api('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      const updated = { ...user, must_change_password: false };
      localStorage.setItem('ltpos_user', JSON.stringify(updated));
      onDone(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not change password');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card glass-card" onSubmit={submit} style={{ width: 'min(460px, 100%)' }}>
        <div className="login-card-head">
          <div>
            <span className="eyebrow">PASSWORD CHANGE REQUIRED</span>
            <h2>Set a new password</h2>
            <p>
              {user.display_name || user.username}, an Admin reset your password. Choose your own password to
              continue.
            </p>
          </div>
        </div>

        <label>
          Temporary password
          <input
            type={showPw ? 'text' : 'password'}
            autoComplete="current-password"
            placeholder="Temporary password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </label>

        <label>
          New password
          <div className="pwd-wrapper">
            <input
              type={showPw ? 'text' : 'password'}
              autoComplete="new-password"
              placeholder={`Min ${MIN_LEN} characters`}
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
            <button
              type="button"
              className="pwd-toggle-btn"
              onClick={() => setShowPw((v) => !v)}
              aria-label={showPw ? 'Hide passwords' : 'Show passwords'}
            >
              {showPw ? '🙈' : '👁'}
            </button>
          </div>
          <div className="pwd-strength-bar" aria-hidden="true">
            <div
              className={`pwd-strength-fill pwd-strength-${s.level}`}
              style={{ width: next.length === 0 ? '0%' : s.level === 'weak' ? '33%' : s.level === 'medium' ? '66%' : '100%' }}
            />
          </div>
          <div className={`pwd-strength-label pwd-strength-label-${s.level}`}>
            {next.length === 0 ? '' : s.level === 'weak' ? 'Weak' : s.level === 'medium' ? 'Medium' : 'Strong'}
          </div>
          <ul className="pwd-requirements">
            <li className={s.checks.length ? 'met' : 'not-met'}>
              <span className="req-icon">{s.checks.length ? '✓' : '○'}</span>
              At least {MIN_LEN} characters ({next.length}/{MIN_LEN})
            </li>
            <li className={s.checks.lower ? 'met' : 'not-met'}>
              <span className="req-icon">{s.checks.lower ? '✓' : '○'}</span>
              Contains lowercase letter
            </li>
            <li className={s.checks.upper ? 'met' : 'not-met'}>
              <span className="req-icon">{s.checks.upper ? '✓' : '○'}</span>
              Contains uppercase letter
            </li>
            <li className={s.checks.digit ? 'met' : 'not-met'}>
              <span className="req-icon">{s.checks.digit ? '✓' : '○'}</span>
              Contains number
            </li>
            <li className={s.checks.symbol ? 'met' : 'not-met'}>
              <span className="req-icon">{s.checks.symbol ? '✓' : '○'}</span>
              Contains symbol (!@#$…)
            </li>
          </ul>
          {next && next.length >= MIN_LEN && errNext && (
            <span className="field-error">{errNext}</span>
          )}
        </label>

        <label>
          Repeat new password
          <input
            type={showPw ? 'text' : 'password'}
            autoComplete="new-password"
            placeholder="Repeat new password"
            value={again}
            onChange={(e) => setAgain(e.target.value)}
          />
          {again && errAgain && <span className="field-error">{errAgain}</span>}
          {again && !errAgain && <span className="field-ok-inline">✓ Passwords match</span>}
        </label>

        {error && <div className="error login-error" role="alert">{error}</div>}

        <button
          aria-label="Change password"
          className="login-submit"
          disabled={!canSubmit}
          type="submit"
        >
          {busy ? 'Saving…' : 'Save new password'} <span>→</span>
        </button>
        <button type="button" className="link-button" onClick={onLogout}>
          Sign out
        </button>
      </form>
    </div>
  );
}