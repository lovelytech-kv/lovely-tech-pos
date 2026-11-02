export type NavGroup = 'primary' | 'more' | 'admin';

export interface NavItem {
  key: string;
  label: string;
  icon: string;
  group: NavGroup;
  permission: string;
  adminOnly?: boolean;
}

export const NAV_GLYPHS: Record<string, string> = {
  Dashboard: '⌂',
  Sales: '▣',
  Items: '▤',
  Customers: '♙',
  Repairs: '⚒',
  Warranty: '✓',
  Stock: '▦',
  Purchases: '⇩',
  'Cash/Day': '◉',
  Reports: '▥',
  Returns: '↩',
  Expenses: '¤',
  Documents: '▧',
  Settings: '⚙',
  Admin: '◆',
  Backup: '↥',
};

export const NAV_ITEMS: NavItem[] = [
  { key: 'Dashboard', label: 'Overview', icon: NAV_GLYPHS.Dashboard, group: 'primary', permission: 'dashboard.view' },
  { key: 'Sales', label: 'POS', icon: NAV_GLYPHS.Sales, group: 'primary', permission: 'sales.view' },
  { key: 'Items', label: 'Inventory', icon: NAV_GLYPHS.Items, group: 'primary', permission: 'items.view' },
  { key: 'Customers', label: 'Customers', icon: NAV_GLYPHS.Customers, group: 'primary', permission: 'customers.view' },
  { key: 'Repairs', label: 'Repairs', icon: NAV_GLYPHS.Repairs, group: 'primary', permission: 'repairs.view' },
  { key: 'Warranty', label: 'Warranty', icon: NAV_GLYPHS.Warranty, group: 'primary', permission: 'warranty.view' },
  { key: 'Stock', label: 'Stock', icon: NAV_GLYPHS.Stock, group: 'primary', permission: 'stock.view' },
  { key: 'Purchases', label: 'Purchases', icon: NAV_GLYPHS.Purchases, group: 'primary', permission: 'purchases.view' },
  { key: 'Cash/Day', label: 'Cash / Day', icon: NAV_GLYPHS['Cash/Day'], group: 'primary', permission: 'cash.view' },
  { key: 'Reports', label: 'Reports', icon: NAV_GLYPHS.Reports, group: 'primary', permission: 'reports.view' },
  { key: 'Returns', label: 'Returns', icon: NAV_GLYPHS.Returns, group: 'more', permission: 'returns.view' },
  { key: 'Expenses', label: 'Expenses', icon: NAV_GLYPHS.Expenses, group: 'more', permission: 'expenses.view' },
  { key: 'Documents', label: 'Documents', icon: NAV_GLYPHS.Documents, group: 'more', permission: 'documents.view' },
  { key: 'Settings', label: 'Settings', icon: NAV_GLYPHS.Settings, group: 'more', permission: 'settings.view', adminOnly: true },
  { key: 'Admin', label: 'Admin', icon: NAV_GLYPHS.Admin, group: 'admin', permission: 'admin.view', adminOnly: true },
  { key: 'Backup', label: 'Backup', icon: NAV_GLYPHS.Backup, group: 'admin', permission: 'backup.view', adminOnly: true },
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