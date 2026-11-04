import { ReactNode, useEffect, useRef, useState } from 'react';
import { checkServerHealth } from '../api/client';
import { ThemeToggle } from '../theme/ThemeToggle';
import { NAV_ITEMS, getNavForRole } from '../config/navigation';
import { loadPermissions, getDefaultPermissions, type Permission } from '../config/permissions';
import { useShopProfile } from '../features/settings/ShopContext';

type User = { display_name: string; role: string; branch_id: string };

type Props = {
  user: User;
  activeKey: string;
  onNavigate: (key: string) => void;
  onLogout: () => void;
  children: ReactNode;
};

export function DashboardLayout({ user, activeKey, onNavigate, onLogout, children }: Props) {
  const [serverState, setServerState] = useState<'checking' | 'online' | 'offline'>('checking');
  const searchRef = useRef<HTMLInputElement>(null);
  const isAdmin = user.role.toUpperCase() === 'ADMIN';
  const { getShopName, getLogoDataUrl } = useShopProfile();

  const shopName = getShopName();
  const logoUrl = getLogoDataUrl();

  const role = isAdmin ? 'ADMIN' : 'CASHIER';
  const permissions: Permission[] = loadPermissions()[role] ?? getDefaultPermissions(role);
  const navItems = getNavForRole(role, permissions);
  const primaryItems = navItems.filter((item) => item.group === 'primary');
  const moreItems = navItems.filter((item) => item.group === 'more');
  const adminItems = navItems.filter((item) => item.group === 'admin');

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

  const activeLabelSource = isAdmin ? NAV_ITEMS : NAV_ITEMS.filter((item) => !item.adminOnly);
  const activeLabel = activeLabelSource.find((item) => item.label === activeKey)?.key ?? shopName;

  return (
    <main className="v0-shell">
      <aside className="v0-sidebar glass-card">
        <button className="v0-brand" onClick={() => onNavigate('Dashboard')} aria-label="Go to dashboard">
          {logoUrl ? (
            <img src={logoUrl} alt="" style={{ width: 39, height: 39, borderRadius: 12, objectFit: 'contain', background: 'var(--surface-2)' }} />
          ) : (
            <span className="brand-mark">{shopName.slice(0, 2).toUpperCase()}</span>
          )}
          <span><strong>{shopName}</strong><small>POS System</small></span>
        </button>
        <div className="v0-sidebar-scroll">
          <div className="v0-sidebar-label">Workspace</div>
          <nav className="v0-nav" aria-label="Main navigation">
            {primaryItems.map((item) => (
              <button
                key={item.key}
                className={activeKey === item.key ? 'active' : ''}
                onClick={() => onNavigate(item.key)}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.label}</span>
                {item.key === 'Sales' && <b className="nav-badge">POS</b>}
              </button>
            ))}
          </nav>
          <div className="v0-sidebar-label more-label">More</div>
          <nav className="v0-nav v0-nav-secondary">
            {moreItems.map((item) => (
              <button
                key={item.key}
                className={activeKey === item.key ? 'active' : ''}
                onClick={() => onNavigate(item.key)}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
            {adminItems.map((item) => (
              <button
                key={item.key}
                className={activeKey === item.key ? 'active' : ''}
                onClick={() => onNavigate(item.key)}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        </div>
        <div className="v0-sidebar-footer">
          <div className={`v0-connection connection-${serverState}`} aria-live="polite"><span className="online-dot" /><span><b>{serverState === 'online' ? 'LAN connected' : serverState === 'offline' ? 'LAN offline' : 'Checking LAN…'}</b><small>Branch {user.branch_id}</small></span></div>
          <button className="v0-user-mini" onClick={onLogout}><span className="avatar">{user.display_name.slice(0,2).toUpperCase()}</span><span><b>{user.display_name}</b><small>{user.role} · Logout</small></span><span className="logout-arrow">↗</span></button>
        </div>
      </aside>

      <section className="v0-main">
        <header className="v0-header glass-card">
          <div><span className="breadcrumb">{shopName} <b>/</b> {activeLabel}</span><h1>{activeLabel}</h1></div>
          <div className="v0-header-actions">
            <label className="global-search"><span>⌕</span><input ref={searchRef} aria-label="Quick search" placeholder="Search products, customers, invoices..." onKeyDown={(e) => { if (e.key === 'Escape') (e.currentTarget as HTMLInputElement).blur(); }} /><kbd>Ctrl K</kbd></label>
            <span className={`header-status header-${serverState}`} aria-live="polite"><i className="online-dot" /> {serverState === 'online' ? 'Online' : serverState === 'offline' ? 'Offline' : 'Checking…'}</span>
            <ThemeToggle />
            <button className="icon-button" aria-label="Notifications">♢</button>
            <button className="header-avatar" aria-label="Account" onClick={onLogout}>{user.display_name.slice(0,1).toUpperCase()}</button>
          </div>
        </header>
        <div className="v0-content">{children}</div>
      </section>
    </main>
  );
}