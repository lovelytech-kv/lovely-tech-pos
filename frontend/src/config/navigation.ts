export type NavGroup = 'primary' | 'more' | 'admin';

export interface NavItem {
  key: string;
  label: string;
  icon: string;
  group: NavGroup;
  permission: string;
  adminOnly?: boolean;
}

// Icon names map to the inline SVG set in components/NavIcon.tsx (no emoji).
export const NAV_ITEMS: NavItem[] = [
  { key: 'Dashboard', label: 'Overview', icon: 'Dashboard', group: 'primary', permission: 'dashboard.view' },
  { key: 'Sales', label: 'POS', icon: 'Sales', group: 'primary', permission: 'sales.view' },
  { key: 'SalesHistory', label: 'Sales History', icon: 'SalesHistory', group: 'primary', permission: 'sales.view' },
  { key: 'Items', label: 'Items', icon: 'Items', group: 'primary', permission: 'items.view' },
  { key: 'Customers', label: 'Customers', icon: 'Customers', group: 'primary', permission: 'customers.view' },
  { key: 'Repairs', label: 'Repairs', icon: 'Repairs', group: 'primary', permission: 'repairs.view' },
  { key: 'Warranty', label: 'Warranty', icon: 'Warranty', group: 'primary', permission: 'warranty.view' },
  { key: 'Stock', label: 'Stock', icon: 'Stock', group: 'primary', permission: 'stock.view' },
  { key: 'Purchases', label: 'Purchases', icon: 'Purchases', group: 'primary', permission: 'purchases.view' },
  { key: 'Cash/Day', label: 'Cash / Day', icon: 'Cash/Day', group: 'primary', permission: 'cash.view' },
  { key: 'Reports', label: 'Reports', icon: 'Reports', group: 'primary', permission: 'reports.view' },
  { key: 'Returns', label: 'Returns', icon: 'Returns', group: 'more', permission: 'returns.view' },
  { key: 'Expenses', label: 'Expenses', icon: 'Expenses', group: 'more', permission: 'expenses.view' },
  { key: 'Documents', label: 'Documents', icon: 'Documents', group: 'more', permission: 'documents.view' },
  { key: 'Settings', label: 'Settings', icon: 'Settings', group: 'more', permission: 'settings.view', adminOnly: true },
  { key: 'Admin', label: 'Admin', icon: 'Admin', group: 'admin', permission: 'admin.view', adminOnly: true },
  { key: 'Users', label: 'Users', icon: 'Users', group: 'admin', permission: 'admin.view', adminOnly: true },
  { key: 'Backup', label: 'Backup', icon: 'Backup', group: 'admin', permission: 'backup.view', adminOnly: true },
];

export function getNavForRole(
  role: 'ADMIN' | 'CASHIER',
  permissions: string[],
): NavItem[] {
  const isAdmin = role === 'ADMIN';
  return NAV_ITEMS.filter((item) => {
    if (item.adminOnly && !isAdmin) return false;
    if (isAdmin) return true;
    return permissions.includes(item.permission);
  });
}
