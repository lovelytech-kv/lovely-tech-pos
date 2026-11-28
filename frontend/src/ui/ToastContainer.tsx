import { useEffect, useState } from 'react';
import { Icon, type IconName } from '../components/Icon';
import { toast, type ToastType } from './toast';

type Item = { id: number; msg: string; type: ToastType };

let _id = 0;

const TOAST_CONFIG: Record<ToastType, { icon: IconName }> = {
  success: { icon: 'check' },
  error: { icon: 'close-x' },
  info: { icon: 'info-circle' },
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
            <div className="toast-icon" aria-hidden="true"><Icon name={cfg.icon} size={12} /></div>
            <div className="toast-message">{it.msg}</div>
            <button
              type="button"
              className="toast-close"
              onClick={() => dismiss(it.id)}
              aria-label="Dismiss notification"
            >
              <Icon name="close-x" size={15} />
            </button>
            <div className="toast-progress" />
          </div>
        );
      })}
    </div>
  );
}