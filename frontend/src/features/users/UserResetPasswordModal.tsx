import { useState } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';
import type { UserRow } from './UserManagement';

type Props = { user: UserRow; onClose: () => void; onSuccess: () => void };

const MIN_PWD = 8;

export function UserResetPasswordModal({ user, onClose, onSuccess }: Props) {
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  function vNewPwd(v: string) {
    if (!v) return 'Password is required';
    if (v.length < MIN_PWD) return `At least ${MIN_PWD} characters (${v.length}/${MIN_PWD})`;
    return null;
  }
  function vConfirm(c: string, p: string) {
    if (!c) return 'Please confirm';
    if (c !== p) return 'Passwords do not match';
    return null;
  }
  function vAdmin(v: string) { return v ? null : 'Admin password required'; }

  const inlineErrs = {
    newPassword: vNewPwd(newPassword),
    confirm: vConfirm(confirm, newPassword),
    adminPassword: vAdmin(adminPassword),
  };
  const allErrs = { ...inlineErrs, ...serverErrors };
  const errorList = Object.entries(allErrs).filter(([, v]) => !!v).map(([, v]) => v as string);
  const canSubmit = Object.values(inlineErrs).every((v) => !v);

  function markTouched(f: string) { setTouched((t) => ({ ...t, [f]: true })); }
  function showError(f: keyof typeof inlineErrs) { return !!inlineErrs[f] && (touched[f] || submitAttempted); }
  function serverErr(f: string) { return serverErrors[f]; }

  async function submit() {
    setSubmitAttempted(true);
    setTouched({ newPassword: true, confirm: true, adminPassword: true });
    if (!canSubmit) { toast.error('Please fix the highlighted fields'); return; }
    try {
      setBusy(true);
      setServerErrors({});
      await api(`/admin/users/${encodeURIComponent(user.user_id)}/reset-password?admin_password=${encodeURIComponent(adminPassword)}`, {
        method: 'POST',
        body: JSON.stringify({ new_password: newPassword }),
      });
      toast.success(`Password reset for ${user.username}`);
      onSuccess();
    } catch (err) {
      const msg = (err as Error).message || '';
      toast.error(msg || 'Reset failed');
      if (/admin password|re-?auth|unauthorized|invalid/i.test(msg)) {
        setServerErrors((p) => ({ ...p, adminPassword: 'Incorrect admin password' }));
      }
    } finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-header">
          <h3>Reset Password — {user.username}</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close" disabled={busy}>×</button>
        </div>
        <div className="modal-body">
          {submitAttempted && errorList.length > 0 && (
            <div className="modal-error-banner">
              <div className="modal-error-banner-title"><span>⚠</span> Please fix {errorList.length} {errorList.length === 1 ? 'error' : 'errors'}:</div>
              <ul className="modal-error-banner-list">
                {errorList.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}
          <p className="muted" style={{ fontSize: '0.8rem', margin: 0 }}>
            User will be forced to change password on next login.
          </p>
          <div className="field">
            <label>New Password * {newPassword && !inlineErrs.newPassword && <span className="field-ok">✓</span>}</label>
            <div className="pwd-wrapper">
              <input
                type={showPwd ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                onBlur={() => markTouched('newPassword')}
                maxLength={200}
                autoComplete="new-password"
                className={showError('newPassword') ? 'input-error' : ''}
              />
              <button type="button" className="pwd-toggle-btn" onClick={() => setShowPwd((v) => !v)} aria-label={showPwd ? 'Hide password' : 'Show password'}>
                {showPwd ? '🙈' : '👁'}
              </button>
            </div>
            <small className="muted" style={{ fontSize: '0.7rem' }}>
              At least {MIN_PWD} characters <span style={{ color: newPassword.length >= MIN_PWD ? '#16a34a' : 'var(--muted)' }}>({newPassword.length}/{MIN_PWD})</span>
            </small>
            {showError('newPassword') && <span className="field-error">{inlineErrs.newPassword}</span>}
          </div>
          <div className="field">
            <label>Confirm New Password * {confirm && !inlineErrs.confirm && <span className="field-ok">✓</span>}</label>
            <input
              type={showPwd ? 'text' : 'password'}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              onBlur={() => markTouched('confirm')}
              maxLength={200}
              autoComplete="new-password"
              className={showError('confirm') ? 'input-error' : ''}
            />
            <small className="muted" style={{ fontSize: '0.7rem' }}>Must match the password above</small>
            {showError('confirm') && <span className="field-error">{inlineErrs.confirm}</span>}
          </div>
          <div className="field">
            <label>Admin Password (re-auth) *</label>
            <input
              type="password"
              value={adminPassword}
              onChange={(e) => { setAdminPassword(e.target.value); if (serverErrors.adminPassword) setServerErrors((p) => { const n = { ...p }; delete n.adminPassword; return n; }); }}
              onBlur={() => markTouched('adminPassword')}
              autoComplete="off"
              className={showError('adminPassword') ? 'input-error' : ''}
            />
            <small className="muted" style={{ fontSize: '0.7rem' }}>Required to confirm this action</small>
            {showError('adminPassword') && <span className="field-error">{serverErr('adminPassword') || inlineErrs.adminPassword}</span>}
          </div>
        </div>
        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="primary" onClick={submit} disabled={busy || !canSubmit}>{busy ? 'Resetting…' : 'Reset Password'}</button>
        </div>
      </div>
    </div>
  );
}