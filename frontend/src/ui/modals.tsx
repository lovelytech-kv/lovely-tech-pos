import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';

type ConfirmOpts = { title?: string; message: string; confirmText?: string; cancelText?: string };
type PromptOpts = { title?: string; message: string; defaultValue?: string; placeholder?: string; confirmText?: string; cancelText?: string };

type ModalContextValue = {
  confirm: (opts: ConfirmOpts) => Promise<boolean>;
  prompt: (opts: PromptOpts) => Promise<string | null>;
};

const ModalContext = createContext<ModalContextValue | null>(null);

type PendingConfirm = { kind: 'confirm'; opts: ConfirmOpts; resolve: (v: boolean) => void };
type PendingPrompt = { kind: 'prompt'; opts: PromptOpts; resolve: (v: string | null) => void };
type Pending = PendingConfirm | PendingPrompt;

export function ModalProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const confirm = useCallback((opts: ConfirmOpts) => {
    return new Promise<boolean>((resolve) => {
      setPending({ kind: 'confirm', opts, resolve });
    });
  }, []);

  const prompt = useCallback((opts: PromptOpts) => {
    return new Promise<string | null>((resolve) => {
      setInput(opts.defaultValue ?? '');
      setPending({ kind: 'prompt', opts, resolve });
      window.setTimeout(() => inputRef.current?.focus(), 50);
    });
  }, []);

  const close = (result: boolean | string | null) => {
    if (!pending) return;
    if (pending.kind === 'confirm') pending.resolve(result as boolean);
    else pending.resolve(typeof result === 'string' ? result : null);
    setPending(null);
  };

  return (
    <ModalContext.Provider value={{ confirm, prompt }}>
      {children}
      {pending && (
        <div
          role='dialog'
          aria-modal='true'
          style={{
            position: 'fixed', inset: 0, zIndex: 10000,
            background: 'rgba(0,0,0,0.55)',
            display: 'grid', placeItems: 'center', padding: 16,
          }}
          onClick={() => close(pending.kind === 'confirm' ? false : null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'var(--surface)', border: '1px solid var(--line)',
              borderRadius: 14, padding: '1.25rem', width: 'min(420px, 100%)',
              color: 'var(--text)', boxShadow: '0 20px 48px rgba(0,0,0,0.3)',
            }}
          >
            {pending.opts.title && (
              <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem', fontWeight: 700 }}>
                {pending.opts.title}
              </h3>
            )}
            <p style={{ margin: '0 0 1rem', fontSize: '0.9rem', lineHeight: 1.5 }}>
              {pending.opts.message}
            </p>
            {pending.kind === 'prompt' && (
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={pending.opts.placeholder}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') close(input);
                  if (e.key === 'Escape') close(null);
                }}
                style={{
                  width: '100%', padding: '0.5rem 0.75rem', marginBottom: '1rem',
                  border: '1px solid var(--line)', borderRadius: 8,
                  background: 'var(--surface-2)', color: 'var(--text)',
                }}
              />
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type='button'
                onClick={() => close(pending.kind === 'confirm' ? false : null)}
                style={{ padding: '0.5rem 1rem', background: 'transparent', border: '1px solid var(--line)', borderRadius: 8, cursor: 'pointer' }}
              >
                {pending.opts.cancelText ?? 'Cancel'}
              </button>
              <button
                type='button'
                onClick={() => close(pending.kind === 'confirm' ? true : input)}
                style={{ padding: '0.5rem 1rem', background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}
              >
                {pending.opts.confirmText ?? 'OK'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ModalContext.Provider>
  );
}

export function useModal(): ModalContextValue {
  const ctx = useContext(ModalContext);
  if (!ctx) throw new Error('useModal must be used within ModalProvider');
  return ctx;
}