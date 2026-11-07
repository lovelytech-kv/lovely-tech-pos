import { useState } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';
import type { UserRow } from './UserManagement';

type Props = { user: UserRow; onClose: () => void; onSuccess: () => void };

export function UserEditModal({ user, onClose, onSuccess }: Props) {
  const [displayName, setDisplayName] = useState(user.display_name);
  const [discount, setDiscount] = useState(String(user.discount_limit_percent ?? 0));
  const [isActive, setIsActive] = useState(user.is_active);
  const [mustChange, setMustChange] = useState(user.must_change_password);
  const [adminPassword, setAdminPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  function vDisplayName(v: string) { return v.trim() ? null : 'Display name is required'; }
  function vDiscount(v: string) {
    if (user.role !== 'CASHIER') return null;
    const n = Number(v);
    if (v === '') return 'Discount required';
    if (!Number.isFinite(n)) return 'Must be a number';
    if (n < 0) return 'Cannot be negative';
    if (n > 100) return 'Maximum 100';
    return null;
  }
  function vAdminPassword(v: string) { return v ? null : 'Admin password required'; }

  const inlineErrs = {
    displayName: vDisplayName(displayName),
    discount: vDiscount(discount),
    adminPassword: vAdminPassword(adminPassword),
  };
  const allErrs = { ...inlineErrs, ...serverErrors };
  const errorList = Object.entries(allErrs).filter(([, v]) => !!v).map(([, v]) => v as string);
  const canSubmit = Object.values(inlineErrs).every((v) => !v);

  function markTouched(f: string) { setTouched((t) => ({ ...t, [f]: true })); }
  function showError(f: keyof typeof inlineErrs) { return !!inlineErrs[f] && (touched[f] || submitAttempted); }
  function serverErr(f: string) { return serverErrors[f]; }

  async function submit() {
    setSubmitAttempted(true);
    setTouched({ displayName: true, discount: true, adminPassword: true });
    if (!canSubmit) { toast.error('Please fix the highlighted fields'); return; }
    try {
      setBusy(true);
      setServerErrors({});
      await api(`/admin/users/${encodeURIComponent(user.user_id)}?admin_password=${encodeURIComponent(adminPassword)}`, {
        method: 'PUT',
        body: JSON.stringify({
          version: user.version,
          display_name: displayName.trim(),
          discount_limit_percent: user.role === 'CASHIER' ? Number(discount) : Number(user.discount_limit_percent ?? 0),
          is_active: isActive,
          must_change_password: mustChange,
        }),
      });
      toast.success('User updated');
      onSuccess();
    } catch (err) {
      const msg = (err as Error).message || '';
      toast.error(msg || 'Update failed');
      if (/version|modified elsewhere|reload/i.test(msg)) {
        setServerErrors((p) => ({ ...p, adminPassword: 'User changed elsewhere — close and refresh' }));
      } else if (/admin password|re-?auth|unauthorized|invalid/i.test(msg)) {
        setServerErrors((p) => ({ ...p, adminPassword: 'Incorrect admin password' }));
      }
    } finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <div className="modal-header">
          <h3>Edit User — {user.username}</h3>
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
          <div className="field"><label>Username</label><input value={user.username} readOnly disabled /></div>
          <div className="field"><label>Role</label><input value={user.role} readOnly disabled /></div>
          <div className="field">
            <label>Display Name * {displayName && !inlineErrs.displayName && <span className="field-ok">✓</span>}</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} onBlur={() => markTouched('displayName')} maxLength={150} className={showError('displayName') ? 'input-error' : ''} />
            {showError('displayName') && <span className="field-error">{inlineErrs.displayName}</span>}
          </div>
          {user.role === 'CASHIER' && (
            <div className="field">
              <label>Discount Limit % {discount && !inlineErrs.discount && <span className="field-ok">✓</span>}</label>
              <input
                type="text"
                inputMode="decimal"
                value={discount}
                onChange={(e) => { const v = e.target.value; if (v === '' || /^\d*\.?\d{0,2}$/.test(v)) setDiscount(v); }}
                onBlur={() => { markTouched('discount'); const n = Number(discount); if (discount === '' || !Number.isFinite(n)) setDiscount('0'); else if (n < 0) setDiscount('0'); else if (n > 100) setDiscount('100'); }}
                className={showError('discount') ? 'input-error' : ''}
              />
              <small className="muted" style={{ fontSize: '0.7rem' }}>0–100 (percentage)</small>
              {showError('discount') && <span className="field-error">{inlineErrs.discount}</span>}
            </div>
          )}
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem' }}>
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} /> Active
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem' }}>
            <input type="checkbox" checked={mustChange} onChange={(e) => setMustChange(e.target.checked)} /> Must change password on next login
          </label>
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
          <button className="primary" onClick={submit} disabled={busy || !canSubmit}>{busy ? 'Saving…' : 'Save'}</button>
        </div>
      </div>
    </div>
  );
}