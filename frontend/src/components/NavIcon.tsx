import type { ReactNode } from 'react';

type IconProps = { name: string; className?: string };

const ICONS: Record<string, ReactNode> = {
  Dashboard: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.6" />
      <rect x="14" y="3" width="7" height="7" rx="1.6" />
      <rect x="3" y="14" width="7" height="7" rx="1.6" />
      <rect x="14" y="14" width="7" height="7" rx="1.6" />
    </>
  ),
  Sales: (
    <>
      <circle cx="9" cy="20" r="1.4" />
      <circle cx="18" cy="20" r="1.4" />
      <path d="M2.5 3.5h2.2l2.2 11h10.6l2-7.5H6" />
    </>
  ),
  SalesHistory: (
    <>
      <path d="M6 3h12v18l-2.2-1.4L13.6 21 12 19.6 10.4 21 8.2 19.6 6 21z" />
      <path d="M9 8h6M9 12h6" />
    </>
  ),
  Items: (
    <>
      <path d="m12 3 9 4.5v9L12 21l-9-4.5v-9z" />
      <path d="M3 7.5 12 12l9-4.5M12 12v9" />
    </>
  ),
  Customers: (
    <>
      <circle cx="12" cy="8" r="3.2" />
      <path d="M4.5 20c.7-3.7 3.6-5.8 7.5-5.8s6.8 2.1 7.5 5.8" />
    </>
  ),
  Repairs: (
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  ),
  Warranty: (
    <>
      <path d="M12 3 20 6v5.5c0 4.7-3.2 8.3-8 9.5-4.8-1.2-8-4.8-8-9.5V6z" />
      <path d="m8.5 11.5 2.3 2.3 4.7-4.7" />
    </>
  ),
  Stock: (
    <>
      <path d="m12 3 9 4.5-9 4.5-9-4.5z" />
      <path d="m3 12 9 4.5 9-4.5M3 16.5 12 21l9-4.5" />
    </>
  ),
  Purchases: (
    <>
      <path d="M2.5 6h10v9h-10z" />
      <path d="M12.5 9.5h4l3 3V15h-7z" />
      <circle cx="6.5" cy="18" r="1.6" />
      <circle cx="16.5" cy="18" r="1.6" />
    </>
  ),
  'Cash/Day': (
    <>
      <rect x="2.5" y="6" width="19" height="12" rx="2" />
      <circle cx="12" cy="12" r="2.6" />
      <path d="M6 9.5v5M18 9.5v5" />
    </>
  ),
  Reports: (
    <>
      <path d="M3 21h18" />
      <path d="M6 21V11M11 21V5M16 21V14M21 21V8" />
    </>
  ),
  Returns: (
    <>
      <path d="M9 7 4 12l5 5" />
      <path d="M4 12h10a5 5 0 0 1 0 10h-2" />
    </>
  ),
  Expenses: (
    <>
      <path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H19a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5.5A2.5 2.5 0 0 1 3 17.5z" />
      <path d="M3 7.5h18" />
      <circle cx="16.5" cy="13.5" r="1.4" />
    </>
  ),
  Documents: (
    <>
      <path d="M6 2.5h7L19 8.5V21.5H6z" />
      <path d="M13 2.5v6h6" />
      <path d="M9 13h6M9 17h6" />
    </>
  ),
  Settings: (
    <>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 2.5V5M12 19v2.5M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M2.5 12H5M19 12h2.5M4.6 19.4l1.8-1.8M17.6 6.4l1.8-1.8" />
    </>
  ),
  Users: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M2.5 20c.6-3.4 3.2-5.4 6.5-5.4s5.9 2 6.5 5.4" />
      <path d="M15.5 5.4a3 3 0 0 1 0 5.2M18 14.8c2 .6 3.3 2.3 3.5 5.2" />
    </>
  ),
  Admin: (
    <>
      <path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h10M18 18h2" />
      <circle cx="16" cy="6" r="2" />
      <circle cx="10" cy="12" r="2" />
      <circle cx="16" cy="18" r="2" />
    </>
  ),
  Backup: (
    <>
      <ellipse cx="12" cy="5.5" rx="7" ry="3" />
      <path d="M5 5.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
      <path d="M5 11.5v6c0 1.7 3.1 3 7 3" />
      <path d="m16 17 2-2 2 2M18 15v6" />
    </>
  ),
};

export function NavIcon({ name, className }: IconProps) {
  return (
    <svg
      className={className ? `nav-svg ${className}` : 'nav-svg'}
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {ICONS[name] ?? ICONS.Items}
    </svg>
  );
}

export function ChevronIcon({ direction }: { direction: 'left' | 'right' }) {
  return (
    <svg
      className="nav-svg"
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {direction === 'left' ? <path d="m15 6-6 6 6 6" /> : <path d="m9 6 6 6-6 6" />}
    </svg>
  );
}
