import { useEffect, useState } from 'react';
import { api, checkServerHealth } from '../../api/client';
import { money } from '../../services/money';

type HomeDashboardUser = { display_name: string; role: string; branch_id?: string };

type HomeDashboardProps = {
  user: HomeDashboardUser;
  onNavigate: (key: string) => void;
};

const HIDDEN_KEY = 'ltpos_home_hidden_widgets';

const QUICK_ACTIONS: { key: string; icon: string; label: string }[] = [
  { key: 'Sales', icon: '＋', label: 'New Sale' },
  { key: 'Repairs', icon: '⚒', label: 'New Repair' },
  { key: 'Customers', icon: '♙', label: 'Find Customer' },
  { key: 'Documents', icon: '↻', label: 'Reprint' },
  { key: 'Reports', icon: '▥', label: 'Reports' },
  { key: 'Cash/Day', icon: '◉', label: 'Cash / Day' },
];

function loadHidden(): string[] {
  try {
    const raw = localStorage.getItem(HIDDEN_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

function saveHidden(ids: string[]): void {
  try {
    localStorage.setItem(HIDDEN_KEY, JSON.stringify(ids));
  } catch {
    // ignore
  }
}

export function HomeDashboard({ user, onNavigate }: HomeDashboardProps) {
  const isAdmin = user.role.toUpperCase() === 'ADMIN';

  const [now, setNow] = useState<Date>(new Date());
  const [salesSummary, setSalesSummary] = useState<any>(null);
  const [dayStatus, setDayStatus] = useState<any>(null);
  const [targets, setTargets] = useState<any[]>([]);
  const [pendingCosts, setPendingCosts] = useState<any[]>([]);
  const [lanStatus, setLanStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [hidden, setHidden] = useState<string[]>(loadHidden);

  // Live clock — updates every second, cleaned up on unmount.
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  // Load dashboard data — one try/catch per endpoint so a single failure cannot crash the screen.
  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    (async () => {
      try {
        setSalesSummary(
          await api('/reports/sales-summary', {
            method: 'POST',
            body: JSON.stringify({ start: today, end: today }),
          }),
        );
      } catch (e) {
        console.warn('[HomeDashboard] sales-summary failed:', e);
      }
      try {
        setDayStatus(await api('/day/status'));
      } catch (e) {
        console.warn('[HomeDashboard] day/status failed:', e);
      }
      try {
        await checkServerHealth();
        setLanStatus('online');
      } catch {
        setLanStatus('offline');
      }
      if (isAdmin) {
        try {
          setTargets(
            await api('/reports/target-progress', {
              method: 'POST',
              body: JSON.stringify({ start: today, end: today }),
            }),
          );
        } catch (e) {
          console.warn('[HomeDashboard] target-progress failed:', e);
        }
        try {
          setPendingCosts(await api('/purchases/pending-costs'));
        } catch (e) {
          console.warn('[HomeDashboard] pending-costs failed:', e);
        }
      }
    })();
  }, [isAdmin]);

  const dateStr = new Intl.DateTimeFormat('en-GB', {
    weekday: 'long',
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  }).format(now);
  const timeStr = new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(now);

  const closeWidget = (id: string) => {
    const next = hidden.includes(id) ? hidden : [...hidden, id];
    setHidden(next);
    saveHidden(next);
  };
  const restoreAll = () => {
    setHidden([]);
    saveHidden([]);
  };

  const isDayOpen = String(dayStatus?.status ?? '').toUpperCase() === 'OPEN';
  const cashInHand =
    dayStatus?.expected_cash ?? dayStatus?.cash_in_hand ?? null;

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      {/* SECTION 1 — Hero */}
      <div
        className="glass-panel"
        style={{
          padding: '1.25rem',
          display: 'grid',
          gridTemplateColumns: 'minmax(0,1fr) auto minmax(0,1fr)',
          gap: '1rem',
          alignItems: 'center',
        }}
      >
        <div>
          <span className="eyebrow">WELCOME BACK</span>
          <h2
            style={{
              margin: '4px 0 0',
              fontSize: '1.25rem',
              letterSpacing: '-0.02em',
            }}
          >
            Welcome, {user.display_name}
          </h2>
        </div>
        <div
          className="date-time-display"
          style={{ flexDirection: 'column', alignItems: 'center', gap: '4px', textAlign: 'center' }}
        >
          <span className="date" style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--text)', letterSpacing: '-0.02em' }}>
            {dateStr}
          </span>
          <span className="time" style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent)', lineHeight: 1 }}>
            {timeStr}
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          <span className={`status-badge ${isDayOpen ? 'status-success' : 'status-warning'}`}>
            {isDayOpen ? 'Day Open' : 'Day Closed'}
          </span>
          <span
            className={`status-badge ${
              lanStatus === 'online'
                ? 'status-success'
                : lanStatus === 'offline'
                ? 'status-danger'
                : 'status-warning'
            }`}
          >
            {lanStatus === 'online' ? 'LAN Online' : lanStatus === 'offline' ? 'LAN Offline' : 'LAN Checking'}
          </span>
        </div>
      </div>

      {/* SECTION 2 — Today's stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
        <div className="metric metric-animated">
          <span>Sales Today</span>
          <b>{salesSummary ? salesSummary.sales_count ?? 0 : '—'}</b>
          <small style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>
            {salesSummary ? `Rs. ${money(salesSummary.sales_total)}` : 'No data'}
          </small>
        </div>
        <div className="metric metric-animated">
          <span>Repairs Active</span>
          <b>—</b>
          <small style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>Not tracked yet</small>
        </div>
        <div className="metric metric-animated">
          <span>Pending</span>
          <b>{isAdmin ? pendingCosts.length : '—'}</b>
          <small style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>
            {isAdmin ? 'Pending cost entries' : 'Admin only'}
          </small>
        </div>
        <div className="metric metric-animated">
          <span>Cash In Hand</span>
          <b>{cashInHand != null ? `Rs. ${money(cashInHand)}` : '—'}</b>
          <small style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>Expected at day-end</small>
        </div>
      </div>

      {/* SECTION 3 — Quick Actions */}
      <div className="glass-panel" style={{ padding: '1.25rem' }}>
        <div className="section-head">
          <div>
            <span className="eyebrow">QUICK ACTIONS</span>
            <h2 style={{ margin: '4px 0 0', fontSize: '1.1rem', letterSpacing: '-0.02em' }}>Common tasks</h2>
          </div>
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.75rem',
            marginTop: '1rem',
          }}
        >
          {QUICK_ACTIONS.map((a) => (
            <button
              key={a.key}
              type="button"
              onClick={() => onNavigate(a.key)}
              style={{
                minHeight: '90px',
                minWidth: '90px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.4rem',
                padding: '0.75rem',
                border: '1px solid var(--line)',
                borderRadius: '12px',
                background: 'var(--surface-2)',
                color: 'var(--text)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.85rem',
              }}
            >
              <span style={{ fontSize: '1.8rem', lineHeight: 1 }}>{a.icon}</span>
              <span>{a.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* SECTION 4 — Widgets */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem' }}>
        {!hidden.includes('recent-activity') && (
          <div className="surface-card" style={{ padding: '1rem' }}>
            <WidgetHead title="Recent Activity" onClose={() => closeWidget('recent-activity')} />
            {salesSummary ? (
              <div style={{ display: 'grid', gap: '0.4rem', fontSize: '0.85rem' }}>
                <Row label="Bills today" value={salesSummary.sales_count ?? 0} />
                <Row label="Sales total" value={`Rs. ${money(salesSummary.sales_total)}`} />
                <Row label="Cash collected" value={`Rs. ${money(salesSummary.cash_total)}`} />
                <Row label="Card" value={`Rs. ${money(salesSummary.card_total)}`} />
                <Row label="Online" value={`Rs. ${money(salesSummary.online_total)}`} />
              </div>
            ) : (
              <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>No recent activity.</p>
            )}
          </div>
        )}

        {isAdmin && !hidden.includes('target-progress') && (
          <div className="surface-card" style={{ padding: '1rem' }}>
            <WidgetHead title="Target Progress" onClose={() => closeWidget('target-progress')} />
            {targets.length === 0 ? (
              <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>No active targets.</p>
            ) : (
              targets.map((t: any) => (
                <div key={t.target_id} className="target-row">
                  <span>{String(t.target_type).replaceAll('_', ' ')}</span>
                  <progress max="100" value={Math.min(100, Number(t.percentage) || 0)} />
                  <b>{t.percentage == null ? 'Active' : `${Number(t.percentage).toFixed(1)}%`}</b>
                </div>
              ))
            )}
          </div>
        )}

        {isAdmin && !hidden.includes('pending-costs') && (
          <div className="surface-card" style={{ padding: '1rem' }}>
            <WidgetHead title="Pending Costs" onClose={() => closeWidget('pending-costs')} />
            {pendingCosts.length === 0 ? (
              <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>No pending costs.</p>
            ) : (
              pendingCosts.slice(0, 5).map((p: any) => (
                <div key={p.purchase_line_id} className="stock-row" style={{ fontSize: '0.85rem' }}>
                  <span>
                    {p.reference_no || 'Purchase'} · Qty {p.quantity}
                  </span>
                  <b>{p.purchase_date}</b>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Restore hidden widgets */}
      {hidden.length > 0 && (
        <div style={{ textAlign: 'center' }}>
          <button type="button" className="btn-secondary" onClick={restoreAll}>
            Restore hidden widgets ({hidden.length})
          </button>
        </div>
      )}
    </div>
  );
}

function WidgetHead({ title, onClose }: { title: string; onClose: () => void }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
      <h3 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, letterSpacing: '-0.02em' }}>{title}</h3>
      <button
        type="button"
        className="icon-button"
        aria-label={`Hide ${title}`}
        onClick={onClose}
        style={{ width: '26px', height: '26px', fontSize: '13px', lineHeight: 1 }}
      >
        ×
      </button>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
      <span style={{ color: 'var(--muted)' }}>{label}</span>
      <b>{value}</b>
    </div>
  );
}

export default HomeDashboard;