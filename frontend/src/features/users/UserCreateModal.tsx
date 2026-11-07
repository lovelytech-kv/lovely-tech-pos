import { useState } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';

type Props = { onClose: () => void; onSuccess: () => void };

const MIN_PWD = 8;

export function UserCreateModal({ onClose, onSuccess }: Props) {
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState<'ADMIN' | 'CASHIER'>('CASHIER');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [discount, setDiscount] = useState('0');
  const [mustChange, setMustChange] = useState(true);
  const [adminPassword, setAdminPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  function vUsername(v: string) {
    if (!v.trim()) return 'Username is required';
    if (v.trim().length < 3) return 'At least 3 characters';
    if (!/^[a-zA-Z0-9_.-]+$/.test(v.trim())) return 'Only letters, digits, dot, underscore, dash';
    return null;
  }
  function vDisplayName(v: string) { return v.trim() ? null : 'Display name is required'; }
  function vPassword(v: string) {
    if (!v) return 'Password is required';
    if (v.length < MIN_PWD) return `At least ${MIN_PWD} characters (${v.length}/${MIN_PWD})`;
    return null;
  }
  function vConfirm(c: string, p: string) {
    if (!c) return 'Please confirm the password';
    if (c !== p) return 'Passwords do not match';
    return null;
  }
  function vAdminPwd(v: string) { return v ? null : 'Admin password required'; }
  function vDiscount(v: string) {
    if (role !== 'CASHIER') return null;
    if (v === '') return 'Discount required (0 allowed)';
    const n = Number(v);
    if (!Number.isFinite(n)) return 'Must be a number';
    if (n < 0) return 'Cannot be negative';
    if (n > 100) return 'Maximum 100';
    return null;
  }

  const inlineErrs = {
    username: vUsername(username),
    displayName: vDisplayName(displayName),
    password: vPassword(password),
    confirm: vConfirm(confirm, password),
    adminPassword: vAdminPwd(adminPassword),
    discount: vDiscount(discount),
  };
  const allErrs = { ...inlineErrs, ...serverErrors };
  const errorList = Object.entries(allErrs).filter(([, v]) => !!v).map(([, v]) => v as string);
  const canSubmit = Object.values(inlineErrs).every((v) => !v);

  function markTouched(f: string) { setTouched((t) => ({ ...t, [f]: true })); }
  function showError(f: keyof typeof inlineErrs) { return !!inlineErrs[f] && (touched[f] || submitAttempted); }
  function serverErr(f: string) { return serverErrors[f]; }

  async function submit() {
    setSubmitAttempted(true);
    setTouched({ username: true, displayName: true, password: true, confirm: true, adminPassword: true, discount: true });
    if (!canSubmit) { toast.error('Please fix the highlighted fields'); return; }

    try {
      setBusy(true);
      setServerErrors({});
      await api(`/admin/users?admin_password=${encodeURIComponent(adminPassword)}`, {
        method: 'POST',
        body: JSON.stringify({
          username: username.trim(),
          password,
          display_name: displayName.trim(),
          role,
          discount_limit_percent: role === 'CASHIER' ? Number(discount) : 0,
          must_change_password: mustChange,
        }),
      });
      toast.success(`User ${username} created`);
      onSuccess();
    } catch (err) {
      const msg = (err as Error).message || '';
      toast.error(msg || 'Create user failed');
      if (/admin password|re-?auth|unauthorized|invalid/i.test(msg)) {
        setServerErrors((p) => ({ ...p, adminPassword: 'Incorrect admin password' }));
      } else if (/username.*taken|already exists|duplicate/i.test(msg)) {
        setServerErrors((p) => ({ ...p, username: 'Username already taken' }));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-header">
          <h3>Create User</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close" disabled={busy}>×</button>
        </div>
        <div className="modal-body">
          {submitAttempted && errorList.length > 0 && (
            <div className="modal-error-banner">
              <div className="modal-error-banner-title">
                <span>⚠</span> Please fix {errorList.length} {errorList.length === 1 ? 'error' : 'errors'}:
              </div>
              <ul className="modal-error-banner-list">
                {errorList.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}

          <div className="field">
            <label>Username * {username && !inlineErrs.username && <span className="field-ok">✓</span>}</label>
            <input value={username} onChange={(e) => { setUsername(e.target.value); if (serverErrors.username) setServerErrors((p) => { const n = { ...p }; delete n.username; return n; }); }} onBlur={() => markTouched('username')} maxLength={80} autoFocus className={showError('username') ? 'input-error' : ''} />
            <small className="muted" style={{ fontSize: '0.7rem' }}>Min 3 characters, must be unique</small>
            {showError('username') && <span className="field-error">{serverErr('username') || inlineErrs.username}</span>}
          </div>

          <div className="field">
            <label>Display Name * {displayName && !inlineErrs.displayName && <span className="field-ok">✓</span>}</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} onBlur={() => markTouched('displayName')} maxLength={150} className={showError('displayName') ? 'input-error' : ''} />
            {showError('displayName') && <span className="field-error">{inlineErrs.displayName}</span>}
          </div>

          <div className="field">
            <label>Role</label>
            <div className="segmented-control" role="group">
              <button type="button" className={role === 'CASHIER' ? 'selected' : ''} onClick={() => setRole('CASHIER')}>Cashier</button>
              <button type="button" className={role === 'ADMIN' ? 'selected' : ''} onClick={() => setRole('ADMIN')}>Admin</button>
            </div>
          </div>

          <div className="field">
            <label>Password * {password && !inlineErrs.password && <span className="field-ok">✓</span>}</label>
            <div className="pwd-wrapper">
              <input type={showPwd ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} onBlur={() => markTouched('password')} maxLength={200} autoComplete="new-password" className={showError('password') ? 'input-error' : ''} />
              <button type="button" className="pwd-toggle-btn" onClick={() => setShowPwd((v) => !v)} aria-label={showPwd ? 'Hide password' : 'Show password'}>{showPwd ? '🙈' : '👁'}</button>
            </div>
            <small className="muted" style={{ fontSize: '0.7rem' }}>At least {MIN_PWD} characters <span style={{ color: password.length >= MIN_PWD ? '#16a34a' : 'var(--muted)' }}>({password.length}/{MIN_PWD})</span></small>
            {showError('password') && <span className="field-error">{inlineErrs.password}</span>}
          </div>

          <div className="field">
            <label>Confirm Password * {confirm && !inlineErrs.confirm && <span className="field-ok">✓</span>}</label>
            <input type={showPwd ? 'text' : 'password'} value={confirm} onChange={(e) => setConfirm(e.target.value)} onBlur={() => markTouched('confirm')} maxLength={200} autoComplete="new-password" className={showError('confirm') ? 'input-error' : ''} />
            <small className="muted" style={{ fontSize: '0.7rem' }}>Must match the password above</small>
            {showError('confirm') && <span className="field-error">{inlineErrs.confirm}</span>}
          </div>

          {role === 'CASHIER' && (
            <div className="field">
              <label>Discount Limit % {discount && !inlineErrs.discount && <span className="field-ok">✓</span>}</label>
              <input type="text" inputMode="decimal" value={discount} onChange={(e) => { const v = e.target.value; if (v === '' || /^\d*\.?\d{0,2}$/.test(v)) setDiscount(v); }} onBlur={() => { markTouched('discount'); const n = Number(discount); if (discount === '' || !Number.isFinite(n)) setDiscount('0'); else if (n < 0) setDiscount('0'); else if (n > 100) setDiscount('100'); }} placeholder="0" className={showError('discount') ? 'input-error' : ''} />
              <small className="muted" style={{ fontSize: '0.7rem' }}>0–100 (percentage)</small>
              {showError('discount') && <span className="field-error">{inlineErrs.discount}</span>}
            </div>
          )}

          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem' }}>
            <input type="checkbox" checked={mustChange} onChange={(e) => setMustChange(e.target.checked)} /> Must change password on first login
          </label>

          <div className="field">
            <label>Admin Password (re-auth) *</label>
            <input type="password" value={adminPassword} onChange={(e) => { setAdminPassword(e.target.value); if (serverErrors.adminPassword) setServerErrors((p) => { const n = { ...p }; delete n.adminPassword; return n; }); }} onBlur={() => markTouched('adminPassword')} autoComplete="off" className={showError('adminPassword') ? 'input-error' : ''} />
            <small className="muted" style={{ fontSize: '0.7rem' }}>Required to confirm this action</small>
            {showError('adminPassword') && <span className="field-error">{serverErr('adminPassword') || inlineErrs.adminPassword}</span>}
          </div>
        </div>
        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="primary" onClick={submit} disabled={busy || !canSubmit}>{busy ? 'Creating…' : 'Create User'}</button>
        </div>
      </div>
    </div>
  );
}