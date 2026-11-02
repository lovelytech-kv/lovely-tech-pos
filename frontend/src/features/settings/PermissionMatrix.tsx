import { useMemo, useState } from 'react';
import { currentUser } from '../../api/client';
import {
  DEFAULT_CASHIER_PERMISSIONS,
  PERMISSION_LABELS,
  loadPermissions,
  savePermissions,
  type Permission,
  type PermissionsStore,
} from '../../config/permissions';

const TAB_PERMISSIONS: Permission[] = [
  'dashboard.view',
  'sales.view',
  'items.view',
  'customers.view',
  'repairs.view',
  'warranty.view',
  'stock.view',
  'purchases.view',
  'cash.view',
  'reports.view',
  'returns.view',
  'expenses.view',
  'documents.view',
];

const ADMIN_ONLY_PERMISSIONS: Permission[] = [
  'settings.view',
  'admin.view',
  'backup.view',
];

const rowStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: '0.6rem',
  padding: '0.4rem 0',
} as const;

const groupHeadingStyle = {
  fontWeight: 600,
  fontSize: '0.8rem',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  opacity: 0.7,
  marginTop: '0.75rem',
} as const;

export function PermissionMatrix() {
  const [store, setStore] = useState<PermissionsStore>(() => loadPermissions());
  const user = currentUser();
  const isAdmin = (user?.role ?? '').toUpperCase() === 'ADMIN';
  const cashierSet = useMemo(() => new Set(store.CASHIER), [store.CASHIER]);

  if (!isAdmin) return null;

  const toggle = (permission: Permission) => {
    const nextCashier = cashierSet.has(permission)
      ? store.CASHIER.filter((p) => p !== permission)
      : [...store.CASHIER, permission];
    const next: PermissionsStore = { ADMIN: store.ADMIN, CASHIER: nextCashier };
    setStore(next);
    savePermissions(next);
  };

  const reset = () => {
    const next: PermissionsStore = {
      ADMIN: store.ADMIN,
      CASHIER: [...DEFAULT_CASHIER_PERMISSIONS],
    };
    setStore(next);
    savePermissions(next);
  };

  return (
    <div className='glass-panel settings-card' style={{ gridColumn: '1 / -1' }}>
      <div className='settings-card-title'>
        <div>
          <h3>Permissions (Cashier)</h3>
          <p className='muted'>
            Choose which tabs and screens the Cashier role can access on this device.
            Admin permissions are fixed and always granted.
          </p>
        </div>
        <span className='settings-symbol'>✓</span>
      </div>

      <div style={groupHeadingStyle}>Tabs &amp; Screens</div>
      {TAB_PERMISSIONS.map((permission) => {
        const meta = PERMISSION_LABELS[permission];
        return (
          <label
            key={permission}
            className='check'
            style={{ ...rowStyle, cursor: 'pointer' }}
          >
            <input
              type='checkbox'
              checked={cashierSet.has(permission)}
              onChange={() => toggle(permission)}
            />
            <span>
              <b>{meta.label}</b>
              <small style={{ display: 'block', opacity: 0.7 }}>{meta.description}</small>
            </span>
          </label>
        );
      })}

      <div style={groupHeadingStyle}>Admin Only</div>
      {ADMIN_ONLY_PERMISSIONS.map((permission) => {
        const meta = PERMISSION_LABELS[permission];
        return (
          <label
            key={permission}
            className='check'
            style={{ ...rowStyle, cursor: 'not-allowed', opacity: 0.65 }}
          >
            <input type='checkbox' checked disabled readOnly />
            <span>
              <b>{meta.label}</b>
              <small style={{ display: 'block', opacity: 0.7 }}>{meta.description}</small>
            </span>
          </label>
        );
      })}
      <small style={{ display: 'block', opacity: 0.7, fontStyle: 'italic', marginTop: '0.25rem' }}>
        Admin always has access to these.
      </small>
      <small style={{ display: 'block', opacity: 0.7, fontStyle: 'italic', marginTop: '0.6rem' }}>
        Changes apply on next page reload.
      </small>

      <div className='button-row' style={{ marginTop: '0.75rem' }}>
        <button className='primary' type='button' onClick={reset}>
          Reset to Defaults
        </button>
      </div>
    </div>
  );
}

export default PermissionMatrix;