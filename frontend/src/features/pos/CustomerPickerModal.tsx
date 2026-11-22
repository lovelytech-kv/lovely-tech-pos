import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';

export type PickerCustomer = {
  customer_id: string;
  name: string | null;
  contact_no: string | null;
};

type Props = {
  onSelect: (customer: PickerCustomer) => void;
  onClose: () => void;
};

function customerLabel(customer: PickerCustomer): string {
  return customer.name?.trim() || customer.contact_no?.trim() || 'Unnamed customer';
}

export function CustomerPickerModal({ onSelect, onClose }: Props) {
  const [view, setView] = useState<'search' | 'new'>('search');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PickerCustomer[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [retryToken, setRetryToken] = useState(0);

  const searchRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      onClose();
    };
    window.addEventListener('keydown', handler, true);
    return () => window.removeEventListener('keydown', handler, true);
  }, [onClose]);

  useEffect(() => {
    if (view === 'search') searchRef.current?.focus();
  }, [view]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  // Debounced search. Empty query shows the 5 most recently created customers.
  useEffect(() => {
    if (view !== 'search') return;
    const term = query.trim();
    const delay = term ? 300 : 0;
    const timer = window.setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setSearching(true);
      setSearchError('');
      try {
        const path = term
          ? `/customers?q=${encodeURIComponent(term)}&limit=10`
          : '/customers?limit=5';
        const rows = await api<PickerCustomer[]>(path, { signal: controller.signal });
        if (!controller.signal.aborted) setResults(rows);
      } catch (e) {
        if (controller.signal.aborted) return;
        setSearchError((e as Error).message || 'Customer search failed. Please retry.');
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, delay);
    return () => window.clearTimeout(timer);
  }, [query, view, retryToken]);

  function choose(customer: PickerCustomer) {
    onSelect(customer);
    onClose();
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="customer-picker-title"
      onClick={onClose}
    >
      <div className="modal-card" style={{ width: 'min(560px, 100%)' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 id="customer-picker-title">{view === 'search' ? 'Add Customer' : 'New Customer'}</h3>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="modal-body">
          {view === 'search' ? (
            <>
              <button type="button" onClick={() => setView('new')} style={{ background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 'var(--radius-sm)', padding: '0.6rem 1rem', fontWeight: 600, cursor: 'pointer' }}>
                + New Customer
              </button>

              <div className="field">
                <label htmlFor="customer-picker-search">Find customer</label>
                <input
                  id="customer-picker-search"
                  ref={searchRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Phone number or name"
                  autoComplete="off"
                  aria-describedby={searchError ? 'customer-picker-search-error' : undefined}
                />
              </div>

              {searching && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--muted)', fontSize: '0.85rem' }}>
                  <span className="spinner" /> Searching customers…
                </div>
              )}

              {searchError && (
                <div id="customer-picker-search-error" role="alert" style={{ display: 'grid', gap: '0.5rem' }}>
                  <span className="field-error">{searchError}</span>
                  <button type="button" className="ghost" onClick={() => setRetryToken((value) => value + 1)}>Retry search</button>
                </div>
              )}

              {!searching && !searchError && (
                <>
                  <div className="muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    {query.trim() ? 'Results' : 'Recent customers'}
                  </div>
                  {results.length > 0 ? (
                    <div className="list-stack">
                      {results.map((customer) => (
                        <button
                          type="button"
                          className="list-row customer-row"
                          key={customer.customer_id}
                          onClick={() => choose(customer)}
                        >
                          <span>
                            <b>{customerLabel(customer)}</b>
                            <small>{customer.contact_no || 'No phone number'}</small>
                          </span>
                          <span>›</span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="empty-state" style={{ padding: '1rem', textAlign: 'center' }}>
                      <b>{query.trim() ? 'No matches' : 'No customers yet'}</b>
                      <span className="muted">
                        {query.trim() ? 'No customer matches this phone or name.' : 'Create the first customer to start attaching sales.'}
                      </span>
                      <button type="button" onClick={() => setView('new')}>
                        {query.trim() ? 'Add new customer' : '+ New Customer'}
                      </button>
                    </div>
                  )}
                </>
              )}

              <div className="modal-actions">
                <button type="button" onClick={onClose}>Cancel</button>
              </div>
            </>
          ) : (
            <>
              <button type="button" className="ghost" onClick={() => setView('search')} style={{ justifySelf: 'start' }}>
                ← Back to search
              </button>
              <p className="muted">New customer form is completed in the next phase.</p>
              <div className="modal-actions">
                <button type="button" onClick={onClose}>Cancel</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
