export type Permission =
  | 'dashboard.view'
  | 'sales.view'
  | 'items.view'
  | 'customers.view'
  | 'repairs.view'
  | 'warranty.view'
  | 'stock.view'
  | 'purchases.view'
  | 'cash.view'
  | 'reports.view'
  | 'returns.view'
  | 'expenses.view'
  | 'documents.view'
  | 'settings.view'
  | 'admin.view'
  | 'backup.view'
  | 'theme.accent.change';

export const DEFAULT_CASHIER_PERMISSIONS: Permission[] = [
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

export const DEFAULT_ADMIN_PERMISSIONS: Permission[] = [
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
  'settings.view',
  'admin.view',
  'backup.view',
  'theme.accent.change',
];

export function getDefaultPermissions(role: 'ADMIN' | 'CASHIER'): Permission[] {
  return role === 'ADMIN'
    ? [...DEFAULT_ADMIN_PERMISSIONS]
    : [...DEFAULT_CASHIER_PERMISSIONS];
}

export interface PermissionMeta {
  label: string;
  description: string;
  adminOnly?: boolean;
}

export const PERMISSION_LABELS: Record<Permission, PermissionMeta> = {
  'dashboard.view': { label: 'Dashboard', description: 'View the workspace overview' },
  'sales.view': { label: 'Sales / POS', description: 'Create sales, print receipts' },
  'items.view': { label: 'Items / Inventory', description: 'Browse and manage inventory items' },
  'customers.view': { label: 'Customers', description: 'View and manage customer records' },
  'repairs.view': { label: 'Repairs', description: 'Track repair jobs and statuses' },
  'warranty.view': { label: 'Warranty', description: 'Manage warranty claims and history' },
  'stock.view': { label: 'Stock', description: 'View stock levels and adjustments' },
  'purchases.view': { label: 'Purchases', description: 'Record supplier purchases' },
  'cash.view': { label: 'Cash / Day', description: 'Open and close daily cash' },
  'reports.view': { label: 'Reports', description: 'View sales and performance reports' },
  'returns.view': { label: 'Returns', description: 'Process customer returns' },
  'expenses.view': { label: 'Expenses', description: 'Record shop expenses' },
  'documents.view': { label: 'Documents', description: 'Access documents and attachments' },
  'settings.view': { label: 'Settings', description: 'Change device preferences and permissions', adminOnly: true },
  'admin.view': { label: 'Admin', description: 'Access admin tools and system controls', adminOnly: true },
  'backup.view': { label: 'Backup', description: 'Run and restore system backups', adminOnly: true },
  'theme.accent.change': {
    label: 'Accent color',
    description: 'Change the primary accent color of the UI',
    adminOnly: false,
  },
};

export interface PermissionsStore {
  ADMIN: Permission[];
  CASHIER: Permission[];
}

const STORAGE_KEY = 'ltpos_permissions';

function defaults(): PermissionsStore {
  return {
    ADMIN: [...DEFAULT_ADMIN_PERMISSIONS],
    CASHIER: [...DEFAULT_CASHIER_PERMISSIONS],
  };
}

function normalizeStore(raw: unknown): PermissionsStore {
  if (!raw || typeof raw !== 'object') return defaults();
  const value = raw as Partial<PermissionsStore>;
  if (!Array.isArray(value.ADMIN) || !Array.isArray(value.CASHIER)) return defaults();
  const allowed = new Set<Permission>(DEFAULT_ADMIN_PERMISSIONS);
  const cashier = (value.CASHIER as unknown[])
    .filter((p): p is Permission => typeof p === 'string' && allowed.has(p as Permission))
    .filter((p) => p !== 'settings.view' && p !== 'admin.view' && p !== 'backup.view');
  return {
    ADMIN: [...DEFAULT_ADMIN_PERMISSIONS],
    CASHIER: cashier,
  };
}

export function loadPermissions(): PermissionsStore {
  if (typeof window === 'undefined') return defaults();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaults();
    return normalizeStore(JSON.parse(raw));
  } catch {
    return defaults();
  }
}

export function savePermissions(p: PermissionsStore): void {
  if (typeof window === 'undefined') return;
  try {
    const safe: PermissionsStore = {
      ADMIN: [...DEFAULT_ADMIN_PERMISSIONS],
      CASHIER: p.CASHIER.filter(
        (perm) => perm !== 'settings.view' && perm !== 'admin.view' && perm !== 'backup.view',
      ),
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(safe));
  } catch {
    // ignore
  }
}