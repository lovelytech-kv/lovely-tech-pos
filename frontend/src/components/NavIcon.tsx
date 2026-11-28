import { Icon, type IconName } from './Icon';

type IconProps = { name: string; className?: string };

/**
 * Navigation icon names are kept in `config/navigation.ts` for readability.
 * This map translates them to the unified icon family in `Icon.tsx`.
 */
const NAV_ICON_NAMES: Record<string, IconName> = {
  Dashboard: 'dashboard',
  Sales: 'cart',
  SalesHistory: 'receipt-list',
  Items: 'package',
  Customers: 'users',
  Repairs: 'wrench',
  Warranty: 'shield-check',
  Stock: 'boxes',
  Purchases: 'truck-down',
  'Cash/Day': 'cash-register',
  Reports: 'chart',
  Returns: 'return-undo',
  Expenses: 'wallet',
  Documents: 'file-text',
  Settings: 'settings',
  Admin: 'sliders',
  Users: 'people',
  Backup: 'database-upload',
};

export function NavIcon({ name, className }: IconProps) {
  const iconName = NAV_ICON_NAMES[name] ?? 'package';
  return (
    <Icon
      name={iconName}
      size={18}
      className={className ? `nav-svg ${className}` : 'nav-svg'}
    />
  );
}

export function ChevronIcon({ direction }: { direction: 'left' | 'right' }) {
  return (
    <Icon
      name={direction === 'left' ? 'chevron-left' : 'chevron-right'}
      size={16}
      className='nav-svg'
    />
  );
}
