import { ReactNode, useEffect, useState } from 'react';
import { todayLocal } from '../utils/date';

type HeaderUser = { display_name: string; role: string };

type AppHeaderProps = {
  title: string;
  user: HeaderUser;
  onLogout: () => void;
  children?: ReactNode;
};

const DATE_FORMAT = new Intl.DateTimeFormat('en-GB', {
  weekday: 'long',
  day: '2-digit',
  month: 'short',
  year: 'numeric',
});

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

export function AppHeader({ title, user, onLogout, children }: AppHeaderProps) {
  const [now, setNow] = useState<Date>(() => new Date());

  // Header clock — updates every minute, cleaned up on unmount.
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 60000);
    return () => window.clearInterval(id);
  }, []);

  // Derive the date from the shop-local calendar date, never UTC.
  const localDate = todayLocal(now);
  const [year, month, day] = localDate.split('-').map(Number);
  const dateLabel = DATE_FORMAT.format(new Date(year, month - 1, day));
  const timeLabel = `${pad2(now.getHours())}:${pad2(now.getMinutes())}`;
  const initials = user.display_name.slice(0, 2).toUpperCase();

  return (
    <header className="v0-header app-header glass-card">
      <div className="app-header-title">
        <h1 title={title}>{title}</h1>
        <span className="app-header-datetime">
          <span>{dateLabel}</span>
          <span className="app-header-datetime-sep" aria-hidden="true">·</span>
          <time dateTime={`${localDate}T${timeLabel}`}>{timeLabel}</time>
        </span>
      </div>
      <div className="app-header-actions">
        {children}
        <span className="app-header-user">
          <span className="avatar">{initials}</span>
          <span className="app-header-user-text">
            <b>{user.display_name}</b>
            <small>{user.role}</small>
          </span>
        </span>
        <button type="button" className="app-header-logout" onClick={onLogout}>Logout</button>
      </div>
    </header>
  );
}
