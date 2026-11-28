import type { ReactNode } from 'react';

/**
 * Unified stroke icon family.
 *
 * Every icon is drawn on a 24x24 grid, inherits `currentColor`, and uses the
 * same stroke weight so mixed Unicode/emoji glyphs can be replaced without
 * changing layout. Unknown names fall back to `circle-question` (G9).
 */
export type IconName =
  // Navigation (18)
  | 'dashboard'
  | 'cart'
  | 'receipt-list'
  | 'package'
  | 'users'
  | 'wrench'
  | 'shield-check'
  | 'boxes'
  | 'truck-down'
  | 'cash-register'
  | 'chart'
  | 'return-undo'
  | 'wallet'
  | 'file-text'
  | 'settings'
  | 'people'
  | 'sliders'
  | 'database-upload'
  // Actions (13)
  | 'plus'
  | 'minus'
  | 'edit-pencil'
  | 'trash'
  | 'save'
  | 'close-x'
  | 'check'
  | 'search'
  | 'filter'
  | 'refresh'
  | 'download'
  | 'upload'
  | 'print'
  // Status (5)
  | 'success-check'
  | 'warning-triangle'
  | 'danger-circle'
  | 'info-circle'
  | 'spinner'
  // Empty states (4)
  | 'empty-cart'
  | 'empty-list'
  | 'empty-search'
  | 'empty-box'
  // Arrows (7)
  | 'chevron-left'
  | 'chevron-right'
  | 'chevron-up'
  | 'chevron-down'
  | 'arrow-left'
  | 'arrow-right'
  | 'external-link'
  // Fallback
  | 'circle-question';

const ICONS: Record<IconName, ReactNode> = {
  // ── Navigation ──────────────────────────────────────────────
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.6" />
      <rect x="14" y="3" width="7" height="7" rx="1.6" />
      <rect x="3" y="14" width="7" height="7" rx="1.6" />
      <rect x="14" y="14" width="7" height="7" rx="1.6" />
    </>
  ),
  cart: (
    <>
      <circle cx="9" cy="20" r="1.4" />
      <circle cx="18" cy="20" r="1.4" />
      <path d="M2.5 3.5h2.2l2.2 11h10.6l2-7.5H6" />
    </>
  ),
  'receipt-list': (
    <>
      <path d="M6 3h12v18l-2.2-1.4L13.6 21 12 19.6 10.4 21 8.2 19.6 6 21z" />
      <path d="M9 8h6M9 12h6" />
    </>
  ),
  package: (
    <>
      <path d="m12 3 9 4.5v9L12 21l-9-4.5v-9z" />
      <path d="M3 7.5 12 12l9-4.5M12 12v9" />
    </>
  ),
  users: (
    <>
      <circle cx="12" cy="8" r="3.2" />
      <path d="M4.5 20c.7-3.7 3.6-5.8 7.5-5.8s6.8 2.1 7.5 5.8" />
    </>
  ),
  wrench: (
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  ),
  'shield-check': (
    <>
      <path d="M12 3 20 6v5.5c0 4.7-3.2 8.3-8 9.5-4.8-1.2-8-4.8-8-9.5V6z" />
      <path d="m8.5 11.5 2.3 2.3 4.7-4.7" />
    </>
  ),
  boxes: (
    <>
      <path d="m12 3 9 4.5-9 4.5-9-4.5z" />
      <path d="m3 12 9 4.5 9-4.5M3 16.5 12 21l9-4.5" />
    </>
  ),
  'truck-down': (
    <>
      <path d="M2.5 6h10v9h-10z" />
      <path d="M12.5 9.5h4l3 3V15h-7z" />
      <circle cx="6.5" cy="18" r="1.6" />
      <circle cx="16.5" cy="18" r="1.6" />
      <path d="M19 2v5M17 5l2 2 2-2" />
    </>
  ),
  'cash-register': (
    <>
      <rect x="2.5" y="6" width="19" height="12" rx="2" />
      <circle cx="12" cy="12" r="2.6" />
      <path d="M6 9.5v5M18 9.5v5" />
    </>
  ),
  chart: (
    <>
      <path d="M3 21h18" />
      <path d="M6 21V11M11 21V5M16 21V14M21 21V8" />
    </>
  ),
  'return-undo': (
    <>
      <path d="M9 7 4 12l5 5" />
      <path d="M4 12h10a5 5 0 0 1 0 10h-2" />
    </>
  ),
  wallet: (
    <>
      <path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H19a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5.5A2.5 2.5 0 0 1 3 17.5z" />
      <path d="M3 7.5h18" />
      <circle cx="16.5" cy="13.5" r="1.4" />
    </>
  ),
  'file-text': (
    <>
      <path d="M6 2.5h7L19 8.5V21.5H6z" />
      <path d="M13 2.5v6h6" />
      <path d="M9 13h6M9 17h6" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 2.5V5M12 19v2.5M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M2.5 12H5M19 12h2.5M4.6 19.4l1.8-1.8M17.6 6.4l1.8-1.8" />
    </>
  ),
  people: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M2.5 20c.6-3.4 3.2-5.4 6.5-5.4s5.9 2 6.5 5.4" />
      <path d="M15.5 5.4a3 3 0 0 1 0 5.2M18 14.8c2 .6 3.3 2.3 3.5 5.2" />
    </>
  ),
  sliders: (
    <>
      <path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h10M18 18h2" />
      <circle cx="16" cy="6" r="2" />
      <circle cx="10" cy="12" r="2" />
      <circle cx="16" cy="18" r="2" />
    </>
  ),
  'database-upload': (
    <>
      <ellipse cx="12" cy="5.5" rx="7" ry="3" />
      <path d="M5 5.5v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
      <path d="M5 11.5v6c0 1.7 3.1 3 7 3" />
      <path d="m16 17 2-2 2 2M18 15v6" />
    </>
  ),

  // ── Actions ─────────────────────────────────────────────────
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  'edit-pencil': (
    <>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z" />
    </>
  ),
  trash: (
    <>
      <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
      <path d="M10 11v6M14 11v6" />
    </>
  ),
  save: (
    <>
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <path d="M17 21v-8H7v8M7 3v5h8" />
    </>
  ),
  'close-x': <path d="M18 6 6 18M6 6l12 12" />,
  check: <path d="M20 6 9 17l-5-5" />,
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>
  ),
  filter: <path d="M22 3H2l8 9.46V19l4 2v-8.54z" />,
  refresh: (
    <>
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </>
  ),
  download: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="m7 10 5 5 5-5M12 15V3" />
    </>
  ),
  upload: (
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="m17 8-5-5-5 5M12 3v12" />
    </>
  ),
  print: (
    <>
      <path d="M6 9V2h12v7" />
      <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
      <rect x="6" y="14" width="12" height="8" />
    </>
  ),

  // ── Status ──────────────────────────────────────────────────
  'success-check': (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12.5 2.5 2.5 5-5" />
    </>
  ),
  'warning-triangle': (
    <>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4M12 17h.01" />
    </>
  ),
  'danger-circle': (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5M12 16h.01" />
    </>
  ),
  'info-circle': (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 16v-5M12 8h.01" />
    </>
  ),
  spinner: <path d="M21 12a9 9 0 1 1-6.22-8.56" />,

  // ── Empty states ────────────────────────────────────────────
  'empty-cart': (
    <>
      <circle cx="9" cy="20" r="1.4" />
      <circle cx="18" cy="20" r="1.4" />
      <path d="M2.5 3.5h2.2l2.2 11h10.6l2-7.5H6" />
      <path d="M8 8.5h6" />
    </>
  ),
  'empty-list': (
    <>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M7 8h10M7 12h10M7 16h6" />
    </>
  ),
  'empty-search': (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3M8.5 8.5l5 5M13.5 8.5l-5 5" />
    </>
  ),
  'empty-box': (
    <>
      <path d="M21 8 12 3 3 8v8l9 5 9-5z" />
      <path d="M3 8l9 5 9-5M12 13v8" />
    </>
  ),

  // ── Arrows ──────────────────────────────────────────────────
  'chevron-left': <path d="m15 6-6 6 6 6" />,
  'chevron-right': <path d="m9 6 6 6-6 6" />,
  'chevron-up': <path d="m6 15 6-6 6 6" />,
  'chevron-down': <path d="m6 9 6 6 6-6" />,
  'arrow-left': <path d="M19 12H5M11 18l-6-6 6-6" />,
  'arrow-right': <path d="M5 12h14M13 6l6 6-6 6" />,
  'external-link': (
    <>
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <path d="M15 3h6v6M10 14 21 3" />
    </>
  ),

  // ── Fallback (G9) ───────────────────────────────────────────
  'circle-question': (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2-3 3.5M12 17h.01" />
    </>
  ),
};

type IconProps = {
  name: IconName;
  size?: number;
  className?: string;
  'aria-label'?: string;
};

export function Icon({ name, size = 18, className, ...rest }: IconProps) {
  const label = rest['aria-label'];
  const isSpinner = name === 'spinner';
  const classes = ['icon-svg', isSpinner ? 'icon-spinner' : '', className]
    .filter(Boolean)
    .join(' ');

  return (
    <svg
      className={classes}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? 'img' : undefined}
      aria-hidden={label ? undefined : true}
      aria-label={label}
      focusable="false"
    >
      {ICONS[name] ?? ICONS['circle-question']}
    </svg>
  );
}
