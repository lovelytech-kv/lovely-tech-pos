import { ReactNode, useEffect, useState } from 'react';
import { checkServerHealth } from '../api/client';
import { ThemeToggle } from '../theme/ThemeToggle';
import { NAV_ITEMS, getNavForRole } from '../config/navigation';
import { loadPermissions, getDefaultPermissions, type Permission } from '../config/permissions';
import { useShopProfile } from '../features/settings/ShopContext';
import { AppHeader } from '../components/AppHeader';
import { ChevronIcon, NavIcon } from '../components/NavIcon';

type User = { display_name: string; role: string; branch_id: string };

type Props = {
  user: User;
  activeKey: string;
  onNavigate: (key: string) => void;
  onLogout: () => void;
  children: ReactNode;
  headerActions?: ReactNode;
};

const SIDEBAR_STORAGE_KEY = 'ltpos_sidebar_collapsed';

function loadSidebarCollapsed(): boolean {
  try {
    const raw = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (raw === null) return true;
    return raw === '1';
  } catch {
    return true;
  }
}

export function DashboardLayout({ user, activeKey, onNavigate, onLogout, children, headerActions }: Props) {
  const [serverState, setServerState] = useState<'checking' | 'online' | 'offline'>('checking');
  const [collapsed, setCollapsed] = useState<boolean>(loadSidebarCollapsed);
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
    return () => { alive = false; window.clearInterval(timer); };
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? '1' : '0');
    } catch {
      // ignore storage errors
    }
  }, [collapsed]);

  const activeLabel = NAV_ITEMS.find((item) => item.key === activeKey)?.label ?? shopName;

  return (
    <main className={`v0-shell${collapsed ? ' sidebar-collapsed' : ''}`}>
      <aside className={`v0-sidebar glass-card${collapsed ? ' is-collapsed' : ''}`}>
        <div className="v0-sidebar-head">
          <button className="v0-brand" onClick={() => onNavigate('Dashboard')} aria-label="Go to dashboard" title={shopName}>
            {logoUrl ? (
              <img src={logoUrl} alt="" style={{ width: 39, height: 39, borderRadius: 12, objectFit: 'contain', background: 'var(--surface-2)' }} />
            ) : (
              <span className="brand-mark">{shopName.slice(0, 2).toUpperCase()}</span>
            )}
            <span className="brand-text"><strong>{shopName}</strong><small>POS System</small></span>
          </button>
          <button
            className="v0-sidebar-toggle"
            onClick={() => setCollapsed((value) => !value)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronIcon direction="right" /> : <ChevronIcon direction="left" />}
          </button>
        </div>
        <div className="v0-sidebar-scroll">
          <div className="v0-sidebar-label">Workspace</div>
          <nav className="v0-nav" aria-label="Main navigation">
            {primaryItems.map((item) => (
              <button
                key={item.key}
                className={activeKey === item.key ? 'active' : ''}
                onClick={() => onNavigate(item.key)}
                title={item.label}
                aria-current={activeKey === item.key ? 'page' : undefined}
              >
                <span className="nav-icon"><NavIcon name={item.icon} /></span>
                <span className="nav-label">{item.label}</span>
                {item.key === 'Sales' && <b className="nav-badge">POS</b>}
              </button>
            ))}
          </nav>
          <div className="v0-sidebar-label more-label">More</div>
          <nav className="v0-nav v0-nav-secondary" aria-label="Secondary navigation">
            {moreItems.map((item) => (
              <button
                key={item.key}
                className={activeKey === item.key ? 'active' : ''}
                onClick={() => onNavigate(item.key)}
                title={item.label}
                aria-current={activeKey === item.key ? 'page' : undefined}
              >
                <span className="nav-icon"><NavIcon name={item.icon} /></span>
                <span className="nav-label">{item.label}</span>
              </button>
            ))}
            {adminItems.map((item) => (
              <button
                key={item.key}
                className={activeKey === item.key ? 'active' : ''}
                onClick={() => onNavigate(item.key)}
                title={item.label}
                aria-current={activeKey === item.key ? 'page' : undefined}
              >
                <span className="nav-icon"><NavIcon name={item.icon} /></span>
                <span className="nav-label">{item.label}</span>
              </button>
            ))}
          </nav>
        </div>
        <div className="v0-sidebar-footer">
          <div className={`v0-connection connection-${serverState}`} aria-live="polite" title={serverState === 'online' ? 'LAN connected' : serverState === 'offline' ? 'LAN offline' : 'Checking LAN…'}><span className="online-dot" /><span><b>{serverState === 'online' ? 'LAN connected' : serverState === 'offline' ? 'LAN offline' : 'Checking LAN…'}</b><small>Branch {user.branch_id}</small></span></div>
          <button className="v0-user-mini" onClick={onLogout} title={`Logout ${user.display_name}`}><span className="avatar">{user.display_name.slice(0,2).toUpperCase()}</span><span><b>{user.display_name}</b><small>{user.role} · Logout</small></span><span className="logout-arrow">↗</span></button>
        </div>
      </aside>

      <section className="v0-main">
        <AppHeader title={activeLabel} user={user} onLogout={onLogout}>
          <span className={`header-status header-${serverState}`} aria-live="polite"><i className="online-dot" /> {serverState === 'online' ? 'Online' : serverState === 'offline' ? 'Offline' : 'Checking…'}</span>
          <ThemeToggle />
          <button className="icon-button app-header-notifications" aria-label="Notifications">♢</button>
          {headerActions}
        </AppHeader>
        <div className="v0-content">{children}</div>
      </section>
    </main>
  );
}