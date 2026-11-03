import { useEffect, useState } from 'react';
import { toast, type ToastType } from './toast';

type Item = { id: number; msg: string; type: ToastType };

let _id = 0;

const COLORS: Record<ToastType, { bg: string; border: string; color: string }> = {
  success: { bg: 'rgba(22, 163, 74, 0.12)', border: 'rgba(22, 163, 74, 0.4)', color: '#16a34a' },
  error: { bg: 'rgba(220, 38, 38, 0.12)', border: 'rgba(220, 38, 38, 0.4)', color: '#dc2626' },
  info: { bg: 'rgba(37, 99, 235, 0.12)', border: 'rgba(37, 99, 235, 0.4)', color: '#2563eb' },
};

export function ToastContainer() {
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    const unsub = toast.subscribe((msg, type) => {
      const id = ++_id;
      setItems((prev) => [...prev, { id, msg, type }]);
      window.setTimeout(() => {
        setItems((prev) => prev.filter((x) => x.id !== id));
      }, 3000);
    });
    return unsub;
  }, []);

  const dismiss = (id: number) => setItems((prev) => prev.filter((x) => x.id !== id));

  if (items.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 16,
        right: 16,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        maxWidth: 360,
      }}
      aria-live='polite'
    >
      {items.map((it) => {
        const c = COLORS[it.type];
        return (
          <div
            key={it.id}
            role='status'
            onClick={() => dismiss(it.id)}
            style={{
              padding: '0.75rem 1rem',
              borderRadius: 10,
              background: c.bg,
              border: `1px solid ${c.border}`,
              color: c.color,
              fontSize: '0.85rem',
              fontWeight: 600,
              boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            {it.msg}
          </div>
        );
      })}
    </div>
  );
}