import type { ToastType } from './toast';

/**
 * Popup-window toast rendering.
 *
 * Toasts normally render in the main app document. Receipt/reprint windows are
 * separate documents, so a toast fired from the app is hidden behind them.
 * Every window opened by the app can be registered here; toasts are then
 * injected directly into that window's DOM (no app runtime needed there).
 *
 * Toasts are also kept briefly per popup so a `document.write()` that replaces
 * the popup content can restore the ones that have not expired yet.
 */

type PopupToastItem = {
  id: number;
  msg: string;
  type: ToastType;
  expiresAt: number;
};

type PopupRecord = {
  win: Window;
  history: PopupToastItem[];
};

const STYLE_ID = 'ltpos-popup-toast-style';
const STACK_ID = 'ltpos-popup-toast-stack';
const TOAST_TTL_MS = 4000;
const MAX_HISTORY = 6;

const POPUP_CSS = `
#${STACK_ID}{position:fixed;top:12px;right:12px;z-index:2147483647;display:flex;flex-direction:column;gap:8px;max-width:320px;pointer-events:none;}
.ltpos-popup-toast{position:relative;display:flex;align-items:flex-start;gap:8px;padding:10px 12px;background:#fff;color:#111;border:1px solid #d1d5db;border-left:4px solid #2563eb;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.18);font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:13px;line-height:1.35;pointer-events:auto;animation:ltpos-popup-toast-in .18s ease-out;}
.ltpos-popup-toast-icon{flex:0 0 auto;width:18px;height:18px;margin-top:1px;border-radius:50%;display:grid;place-items:center;color:#fff;font-size:11px;font-weight:800;line-height:1;background:#2563eb;}
.ltpos-popup-toast-success{border-left-color:#16a34a;}
.ltpos-popup-toast-success .ltpos-popup-toast-icon{background:#16a34a;}
.ltpos-popup-toast-error{border-left-color:#dc2626;}
.ltpos-popup-toast-error .ltpos-popup-toast-icon{background:#dc2626;}
.ltpos-popup-toast-info{border-left-color:#2563eb;}
.ltpos-popup-toast-message{flex:1;word-break:break-word;color:#111;}
@keyframes ltpos-popup-toast-in{from{opacity:0;transform:translateX(16px);}to{opacity:1;transform:translateX(0);}}
@media print{#${STACK_ID}{display:none!important;}}
`;

const ICONS: Record<ToastType, string> = {
  success: '✓',
  error: '✕',
  info: 'i',
};

const popups = new Map<Window, PopupRecord>();
let nextId = 0;

function pruneClosedPopups(): void {
  for (const [win] of popups) {
    if (win.closed) popups.delete(win);
  }
}

function ensureStack(win: Window): HTMLElement | null {
  const doc = win.document;
  if (!doc || !doc.body) return null;

  let stack = doc.getElementById(STACK_ID);
  if (stack) return stack;

  if (!doc.getElementById(STYLE_ID)) {
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = POPUP_CSS;
    (doc.head || doc.documentElement).appendChild(style);
  }

  stack = doc.createElement('div');
  stack.id = STACK_ID;
  stack.setAttribute('role', 'status');
  stack.setAttribute('aria-live', 'polite');
  doc.body.appendChild(stack);
  return stack;
}

function renderItem(win: Window, item: PopupToastItem): boolean {
  const doc = win.document;
  const stack = ensureStack(win);
  if (!stack) return false;

  const elementId = `ltpos-popup-toast-${item.id}`;
  if (doc.getElementById(elementId)) return true;

  const el = doc.createElement('div');
  el.id = elementId;
  el.className = `ltpos-popup-toast ltpos-popup-toast-${item.type}`;

  const icon = doc.createElement('span');
  icon.className = 'ltpos-popup-toast-icon';
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = ICONS[item.type];

  const message = doc.createElement('span');
  message.className = 'ltpos-popup-toast-message';
  message.textContent = item.msg;

  el.appendChild(icon);
  el.appendChild(message);
  stack.appendChild(el);

  window.setTimeout(() => {
    try {
      el.remove();
    } catch {
      // Popup may have been replaced or closed; nothing to clean up.
    }
  }, TOAST_TTL_MS);

  return true;
}

function renderToPopup(record: PopupRecord, item: PopupToastItem): void {
  const { win } = record;
  if (win.closed) {
    popups.delete(win);
    return;
  }
  try {
    if (renderItem(win, item)) return;
  } catch {
    // Cross-window access failed (window closing). Treat as closed.
    popups.delete(win);
    return;
  }

  // Document not ready yet: retry once after the popup finishes loading.
  try {
    win.addEventListener('load', () => {
      try {
        renderItem(win, item);
      } catch {
        popups.delete(win);
      }
    }, { once: true });
  } catch {
    popups.delete(win);
  }
}

/** Registers an opened popup window so toasts can be shown inside it. */
export function trackPopup(win: Window | null): Window | null {
  if (!win) return win;
  if (!popups.has(win)) {
    popups.set(win, { win, history: [] });
    try {
      win.addEventListener('beforeunload', () => popups.delete(win));
    } catch {
      // Ignore: the window may already be unusable.
    }
  }
  return win;
}

/** Dispatches a toast to every open tracked popup window. */
export function showPopupToast(msg: string, type: ToastType): void {
  pruneClosedPopups();
  if (popups.size === 0) return;

  const now = Date.now();
  const item: PopupToastItem = { id: ++nextId, msg, type, expiresAt: now + TOAST_TTL_MS };

  for (const record of popups.values()) {
    record.history = record.history.filter((entry) => entry.expiresAt > now);
    record.history.push(item);
    if (record.history.length > MAX_HISTORY) record.history.shift();
    renderToPopup(record, item);
  }
}

/**
 * Re-renders unexpired toasts inside a popup after its document was rewritten
 * (for example `document.write()` of the receipt HTML).
 */
export function restorePopupToasts(win: Window | null): void {
  if (!win) return;
  const record = popups.get(win);
  if (!record || win.closed) return;
  const now = Date.now();
  record.history = record.history.filter((item) => item.expiresAt > now);
  for (const item of record.history) renderToPopup(record, item);
}
