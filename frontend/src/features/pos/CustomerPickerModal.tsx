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

const digitsOnly = (value: string | null | undefined): string => (value || '').replace(/\D/g, '');

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
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);
  const [duplicateCount, setDuplicateCount] = useState(0);
  const [checkingPhone, setCheckingPhone] = useState(false);

  const searchRef = useRef<HTMLInputElement>(null);
  const phoneRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const savingRef = useRef(saving);
  const dirtyRef = useRef(false);
  const requestCloseRef = useRef<() => void>(() => undefined);

  const dirty = view === 'new' && (phone.trim().length > 0 || name.trim().length > 0);

  function requestClose() {
    if (savingRef.current) return;
    if (dirtyRef.current && !window.confirm('Discard the new customer details?')) return;
    onClose();
  }

  useEffect(() => {
    savingRef.current = saving;
  }, [saving]);

  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);

  useEffect(() => {
    requestCloseRef.current = requestClose;
  }, [onClose, dirty, saving]);

  // ESC closes the picker, but a dirty quick-add form must be confirmed first (G3).
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      requestCloseRef.current();
    };
    window.addEventListener('keydown', handler, true);
    return () => window.removeEventListener('keydown', handler, true);
  }, []);

  useEffect(() => {
    if (view === 'search') searchRef.current?.focus();
    else phoneRef.current?.focus();
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

  // Duplicate phone warning (allowed, but the cashier must see it).
  useEffect(() => {
    if (view !== 'new') return;
    const raw = phone.trim();
    const target = digitsOnly(raw);
    if (target.length < 3) {
      setDuplicateCount(0);
      setCheckingPhone(false);
      return;
    }
    let cancelled = false;
    setCheckingPhone(true);
    const timer = window.setTimeout(async () => {
      try {
        const rows = await api<PickerCustomer[]>(`/customers?q=${encodeURIComponent(raw)}&limit=50`);
        if (!cancelled) {
          setDuplicateCount(rows.filter((row) => digitsOnly(row.contact_no) === target).length);
        }
      } catch {
        if (!cancelled) setDuplicateCount(0);
      } finally {
        if (!cancelled) setCheckingPhone(false);
      }
    }, 400);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [phone, view]);

  function openNewCustomer() {
    setFormError('');
    setView('new');
  }

  function backToSearch() {
    if (phone.trim() || name.trim()) {
      if (!window.confirm('Discard the new customer details?')) return;
    }
    setPhone('');
    setName('');
    setFormError('');
    setDuplicateCount(0);
    setView('search');
  }

  function choose(customer: PickerCustomer) {
    onSelect(customer);
    onClose();
  }

  async function save() {
    if (saving) return;
    const trimmedPhone = phone.trim();
    const trimmedName = name.trim();
    if (!trimmedPhone && !trimmedName) {
      setFormError('Enter a phone number or a name.');
      phoneRef.current?.focus();
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      const created = await api<PickerCustomer>('/customers', {
        method: 'POST',
        body: JSON.stringify({
          name: trimmedName || null,
          contact_no: trimmedPhone || null,
          notes: null,
        }),
      });
      onSelect(created);
      onClose();
    } catch (e) {
      setFormError((e as Error).message || 'Could not create the customer. Please retry.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="customer-picker-title"
      onClick={requestClose}
    >
      <div className="modal-card" style={{ width: 'min(560px, 100%)' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 id="customer-picker-title">{view === 'search' ? 'Add Customer' : 'New Customer'}</h3>
          <button type="button" className="modal-close" onClick={requestClose} aria-label="Close" disabled={saving}>×</button>
        </div>

        <div className="modal-body">
          {view === 'search' ? (
            <>
              <button type="button" onClick={openNewCustomer} style={{ background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 'var(--radius-sm)', padding: '0.6rem 1rem', fontWeight: 600, cursor: 'pointer' }}>
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
                      <button type="button" onClick={openNewCustomer}>
                        {query.trim() ? 'Add new customer' : '+ New Customer'}
                      </button>
                    </div>
                  )}
                </>
              )}

              <div className="modal-actions">
                <button type="button" onClick={requestClose}>Cancel</button>
              </div>
            </>
          ) : (
            <>
              <button type="button" className="ghost" onClick={backToSearch} disabled={saving} style={{ justifySelf: 'start' }}>
                ← Back to search
              </button>

              <div className="field">
                <label htmlFor="customer-picker-phone">Phone number</label>
                <input
                  id="customer-picker-phone"
                  ref={phoneRef}
                  type="tel"
                  value={phone}
                  onChange={(e) => { setPhone(e.target.value); setFormError(''); }}
                  placeholder="07X XXX XXXX"
                  autoComplete="off"
                  aria-describedby="customer-picker-phone-hint"
                />
                <small id="customer-picker-phone-hint" className="muted">Any format accepted (Sri Lankan 07X numbers or other digits).</small>
                {checkingPhone && (
                  <small className="muted" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <span className="spinner" /> Checking for duplicate phone…
                  </small>
                )}
                {!checkingPhone && duplicateCount > 0 && (
                  <small style={{ color: 'var(--color-warning)', fontWeight: 600 }}>
                    {duplicateCount} {duplicateCount === 1 ? 'customer has' : 'customers have'} this phone number. Saving is allowed, but check it is not a duplicate.
                  </small>
                )}
              </div>

              <div className="field">
                <label htmlFor="customer-picker-name">Name (optional)</label>
                <input
                  id="customer-picker-name"
                  value={name}
                  onChange={(e) => { setName(e.target.value); setFormError(''); }}
                  placeholder="Customer name"
                  autoComplete="off"
                />
              </div>

              {formError && <p className="field-error" role="alert">{formError}</p>}

              <div className="modal-actions">
                <button type="button" onClick={requestClose} disabled={saving}>Cancel</button>
                <button type="button" onClick={() => void save()} disabled={saving} style={{ background: 'var(--accent)', color: '#fff', border: 0, borderRadius: 'var(--radius-sm)', padding: '0.5rem 1rem', fontWeight: 600, cursor: saving ? 'wait' : 'pointer' }}>
                  {saving ? 'Saving…' : 'Save Customer'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
