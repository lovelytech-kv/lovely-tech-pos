export type ToastType = 'success' | 'error' | 'info';
export type ToastListener = (msg: string, type: ToastType) => void;

const listeners: ToastListener[] = [];

export const toast = {
  success: (msg: string) => listeners.forEach((l) => l(msg, 'success')),
  error: (msg: string) => listeners.forEach((l) => l(msg, 'error')),
  info: (msg: string) => listeners.forEach((l) => l(msg, 'info')),
  subscribe: (fn: ToastListener) => {
    listeners.push(fn);
    return () => {
      const i = listeners.indexOf(fn);
      if (i >= 0) listeners.splice(i, 1);
    };
  },
};