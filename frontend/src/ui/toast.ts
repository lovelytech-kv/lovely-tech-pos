import { showPopupToast } from './popupToast';

export type ToastType = 'success' | 'error' | 'info';
export type ToastListener = (msg: string, type: ToastType) => void;

const listeners: ToastListener[] = [];

function emit(msg: string, type: ToastType): void {
  listeners.forEach((listener) => listener(msg, type));
  // Popups are separate documents; render there too so the feedback is not
  // hidden behind an open receipt / reprint window.
  showPopupToast(msg, type);
}

export const toast = {
  success: (msg: string) => emit(msg, 'success'),
  error: (msg: string) => emit(msg, 'error'),
  info: (msg: string) => emit(msg, 'info'),
  subscribe: (fn: ToastListener) => {
    listeners.push(fn);
    return () => {
      const i = listeners.indexOf(fn);
      if (i >= 0) listeners.splice(i, 1);
    };
  },
};
