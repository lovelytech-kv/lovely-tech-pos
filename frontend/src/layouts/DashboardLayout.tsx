import { ReactNode, useEffect, useRef, useState } from 'react';
import { checkServerHealth } from '../api/client';

type User = { display_name: string; role: string; branch_id: string };

type Props = {
  user: User;
  activeKey: string;
  onNavigate: (key: string) => void;
  onLogout: () => void;
  children: ReactNode;
};

const primary = [
  ['Dashboard', 'Overview'], ['Sales', 'POS'], ['Items', 'Inventory'], ['Customers', 'Customers'],
  ['Repairs', 'Repairs'], ['Warranty', 'Warranty'], ['Stock', 'Stock'], ['Purchases', 'Purchases'],
  ['Cash/Day', 'Cash / Day'], ['Reports', 'Reports'],
] as const;
const more = [['Returns', 'Returns'], ['Expenses', 'Expenses'], ['Documents', 'Documents'], ['Settings', 'Settings']] as const;

const glyph: Record<string, string> = { Dashboard:'⌂', Sales:'▣', Items:'▤', Customers:'♙', Repairs:'⚒', Warranty:'✓', Stock:'▦', Purchases:'⇩', 'Cash/Day':'◉', Reports:'▥', Returns:'↩', Expenses:'¤', Documents:'▧', Settings:'⚙', Admin:'◆', Backup:'↥' };

export function DashboardLayout({ user, activeKey, onNavigate, onLogout, children }: Props) {
  const [serverState, setServerState] = useState<'checking'|'online'|'offline'>('checking');
  const searchRef = useRef<HTMLInputElement>(null);
  const isAdmin = user.role.toUpperCase() === 'ADMIN';
  useEffect(() => {
    const theme = (localStorage.getItem('ltpos_theme') || 'light') as 'light'|'dark'|'system';
    const accent = localStorage.getItem('ltpos_accent') || '#df3b32';
    const density = localStorage.getItem('ltpos_density') || 'comfortable';
    const resolved = theme === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : theme;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.dataset.density = density;
    document.documentElement.style.setProperty('--accent', accent);
    const n = parseInt(accent.replace('#',''), 16);
    document.documentElement.style.setProperty('--accent-rgb', `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`);
  }, []);
  useEffect(() => {
    let alive = true;
    const check = async () => {
      try { await checkServerHealth(); if (alive) setServerState('online'); }
      catch { if (alive) setServerState('offline'); }
    };
    check();
    const timer = window.setInterval(check, 15000);
    const focusSearch = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
    };
    window.addEventListener('keydown', focusSearch);
    return () => { alive = false; window.clearInterval(timer); window.removeEventListener('keydown', focusSearch); };
  }, []);
  const activeLabel = [...primary, ...more, ...(isAdmin ? [['Admin','Admin'],['Backup','Backup']] as const : [])].find(([, key]) => key === activeKey)?.[0] ?? 'Lovely Tech POS';
  return (
    <main className="v0-shell">
      <aside className="v0-sidebar glass-card">
        <button className="v0-brand" onClick={() => onNavigate('Dashboard')} aria-label="Go to dashboard">
          <span className="brand-mark">LT</span>
          <span><strong>Lovely Tech</strong><small>POS System</small></span>
        </button>
        <div className="v0-sidebar-scroll">
          <div className="v0-sidebar-label">Workspace</div>
          <nav className="v0-nav" aria-label="Main navigation">
            {primary.map(([key, label]) => <button key={key} className={activeKey === key ? 'active' : ''} onClick={() => onNavigate(key)}><span className="nav-icon">{glyph[key]}</span><span>{label}</span>{key === 'Sales' && <b className="nav-badge">POS</b>}</button>)}
          </nav>
          <div className="v0-sidebar-label more-label">More</div>
          <nav className="v0-nav v0-nav-secondary">
            {more.map(([key, label]) => <button key={key} className={activeKey === key ? 'active' : ''} onClick={() => onNavigate(key)}><span className="nav-icon">{glyph[key]}</span><span>{label}</span></button>)}
            {isAdmin && <><button className={activeKey === 'Admin' ? 'active' : ''} onClick={() => onNavigate('Admin')}><span className="nav-icon">{glyph.Admin}</span><span>Admin</span></button><button className={activeKey === 'Backup' ? 'active' : ''} onClick={() => onNavigate('Backup')}><span className="nav-icon">{glyph.Backup}</span><span>Backup</span></button></>}
          </nav>
        </div>
        <div className="v0-sidebar-footer">
          <div className={`v0-connection connection-${serverState}`} aria-live="polite"><span className="online-dot" /><span><b>{serverState === 'online' ? 'LAN connected' : serverState === 'offline' ? 'LAN offline' : 'Checking LAN…'}</b><small>Branch {user.branch_id}</small></span></div>
          <button className="v0-user-mini" onClick={onLogout}><span className="avatar">{user.display_name.slice(0,2).toUpperCase()}</span><span><b>{user.display_name}</b><small>{user.role} · Logout</small></span><span className="logout-arrow">↗</span></button>
        </div>
      </aside>

      <section className="v0-main">
        <header className="v0-header glass-card">
          <div><span className="breadcrumb">Lovely Tech <b>/</b> {activeLabel}</span><h1>{activeLabel}</h1></div>
          <div className="v0-header-actions">
            <label className="global-search"><span>⌕</span><input ref={searchRef} aria-label="Quick search" placeholder="Search products, customers, invoices..." onKeyDown={(e) => { if (e.key === 'Escape') (e.currentTarget as HTMLInputElement).blur(); }} /><kbd>Ctrl K</kbd></label>
            <span className={`header-status header-${serverState}`} aria-live="polite"><i className="online-dot" /> {serverState === 'online' ? 'Online' : serverState === 'offline' ? 'Offline' : 'Checking…'}</span>
            <button className="icon-button" aria-label="Notifications">♢</button>
            <button className="header-avatar" aria-label="Account" onClick={onLogout}>{user.display_name.slice(0,1).toUpperCase()}</button>
          </div>
        </header>
        <div className="v0-content">{children}</div>
      </section>
    </main>
  );
}
