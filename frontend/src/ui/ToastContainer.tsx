import { useEffect, useState } from 'react';
import { toast, type ToastType } from './toast';

type Item = { id: number; msg: string; type: ToastType };

let _id = 0;

const TOAST_CONFIG: Record<ToastType, { icon: string }> = {
  success: { icon: '✓' },
  error: { icon: '✕' },
  info: { icon: 'i' },
};

export function ToastContainer() {
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    const unsub = toast.subscribe((msg, type) => {
      const id = ++_id;
      setItems((prev) => [...prev, { id, msg, type }]);
      window.setTimeout(() => {
        setItems((prev) => prev.filter((x) => x.id !== id));
      }, 4000);
    });
    return unsub;
  }, []);

  const dismiss = (id: number) => setItems((prev) => prev.filter((x) => x.id !== id));

  if (items.length === 0) return null;

  return (
    <div className="toast-stack" aria-live="polite" aria-atomic="false">
      {items.map((it) => {
        const cfg = TOAST_CONFIG[it.type];
        return (
          <div key={it.id} className={`toast toast-${it.type}`} role="status">
            <div className="toast-icon" aria-hidden="true">{cfg.icon}</div>
            <div className="toast-message">{it.msg}</div>
            <button
              type="button"
              className="toast-close"
              onClick={() => dismiss(it.id)}
              aria-label="Dismiss notification"
            >
              ×
            </button>
            <div className="toast-progress" />
          </div>
        );
      })}
    </div>
  );
}