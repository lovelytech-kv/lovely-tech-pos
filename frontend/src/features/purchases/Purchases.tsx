import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../../api/client';
import { money, moneyAdd, moneyTimesQty } from '../../services/money';
import { moneyInputProps, intInputProps } from '../../utils/numberInput';
import { toast } from '../../ui/toast';
import { useModal } from '../../ui/modals';

type Item = { item_id: string; item_code: string; description: string; stock: string | number; is_serialized?: boolean };
type Supplier = { supplier_id: string; name: string; contact_no?: string | null; address?: string | null };

type DraftLine = {
  key: string;
  item: Item | null;
  search: string;
  results: Item[];
  searching: boolean;
  quantity: string;
  unitCost: string;
  serials: string;
};

type PurchaseSummary = {
  purchase_id: string;
  purchase_date: string;
  reference_no: string | null;
  supplier_id: string | null;
  supplier_name: string | null;
  status: string;
  line_count: number;
  total_quantity: string | number;
  total_cost: string | number | null;
  pending_cost_lines: number;
  created_by: string | null;
};

type DetailLine = {
  purchase_line_id: string;
  item_id: string;
  item_code: string;
  item_description: string;
  quantity: string | number;
  unit_cost: string | number | null;
  line_date: string;
  line_total: string | number | null;
  version: number;
};

type PurchaseDetail = {
  purchase_id: string;
  purchase_date: string;
  reference_no: string | null;
  supplier_id: string | null;
  supplier_name: string | null;
  notes: string | null;
  status: string;
  version: number;
  line_count: number;
  total_quantity: string | number;
  total_cost: string | number | null;
  pending_cost_lines: number;
  created_by: string | null;
  lines: DetailLine[];
};

type CorrectionField = 'cost' | 'date' | 'quantity' | 'reference' | 'supplier';

type CorrectionState = {
  field: CorrectionField;
  purchaseId: string;
  purchaseVersion: number;
  lineId: string | null;
  lineVersion: number;
  title: string;
  initial: string;
};

type LineErrors = { item?: string; quantity?: string; cost?: string };

const today = () => new Date().toISOString().slice(0, 10);
const MAX_QTY = 1000000;
const MAX_COST = 999999999.99;

// One IMEI/serial per line (commas/spaces also accepted); duplicates are caught client-side.
export const parseSerials = (text?: string): string[] => (text || '').split(/[\s,;]+/).map(x => x.trim().toUpperCase()).filter(Boolean);

function emptyLine(): DraftLine {
  return { key: crypto.randomUUID(), item: null, search: '', results: [], searching: false, quantity: '1', unitCost: '', serials: '' };
}

function lineQuantity(line: DraftLine): number {
  return line.item?.is_serialized ? parseSerials(line.serials).length : Number(line.quantity || 0);
}

// Money math stays string/bigint based so float artefacts can never reach the UI.
function costValue(text: string): string | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  const normalized = trimmed.endsWith('.') ? trimmed.slice(0, -1) : trimmed;
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) return null;
  return normalized;
}

function lineTotal(line: DraftLine): string {
  const cost = costValue(line.unitCost);
  if (cost === null) return '0.00';
  return moneyTimesQty(cost, String(lineQuantity(line)));
}

function validateLine(line: DraftLine, isAdmin: boolean): LineErrors {
  const errors: LineErrors = {};
  if (!line.item) errors.item = 'Choose an item';
  const qty = lineQuantity(line);
  if (line.item?.is_serialized) {
    if (qty < 1) errors.quantity = 'Enter at least one IMEI/serial';
  } else if (!Number.isInteger(qty) || qty < 1) {
    errors.quantity = 'Qty must be 1 or more';
  }
  if (qty > MAX_QTY) errors.quantity = 'Qty is too large';
  if (isAdmin && line.unitCost.trim() !== '') {
    const cost = Number(line.unitCost);
    if (!Number.isFinite(cost) || cost < 0) errors.cost = 'Cost must be 0 or more';
    else if (cost > MAX_COST) errors.cost = 'Cost is too large';
  }
  return errors;
}

export function Purchases({ isAdmin, onError, initialStatusFilter = 'ALL' }: { isAdmin: boolean; onError?: (message: string) => void; initialStatusFilter?: 'ALL' | 'PENDING' }) {
  const modal = useModal();
  const [view, setView] = useState<'entry' | 'history'>(initialStatusFilter === 'PENDING' ? 'history' : 'entry');

  // Entry state
  const [date, setDate] = useState(today());
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [supplierId, setSupplierId] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [busy, setBusy] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [purchaseKey, setPurchaseKey] = useState(() => crypto.randomUUID());
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);

  // History state
  const [history, setHistory] = useState<PurchaseSummary[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [filterSearch, setFilterSearch] = useState('');
  const [filterFrom, setFilterFrom] = useState('');
  const [filterTo, setFilterTo] = useState('');
  const [filterSupplier, setFilterSupplier] = useState('');
  const [filterStatus, setFilterStatus] = useState<'ALL' | 'PENDING' | 'COMPLETED'>(initialStatusFilter);

  // Detail state
  const [detail, setDetail] = useState<PurchaseDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [costDrafts, setCostDrafts] = useState<Record<string, string>>({});
  const [costBusy, setCostBusy] = useState('');

  // Audited corrections (Admin)
  const [correction, setCorrection] = useState<CorrectionState | null>(null);
  const [correctionValue, setCorrectionValue] = useState('');
  const [correctionReason, setCorrectionReason] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [savingCorrection, setSavingCorrection] = useState(false);

  const dirty = lines.length > 0 || reference.trim() !== '' || notes.trim() !== '' || supplierId !== '' || date !== today();
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;

  useEffect(() => {
    if (!isAdmin) return;
    (async () => {
      try { setSuppliers(await api<Supplier[]>('/admin/suppliers')); }
      catch (err) { onError?.((err as Error).message); }
    })();
  }, [isAdmin]);

  // Deep links from the dashboard open Purchase history directly (e.g. cost-pending queue).
  useEffect(() => {
    if (view === 'history' && !historyLoaded) void loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // G3 — warn before the whole app window is closed with an unsaved purchase.
  useEffect(() => {
    function onBeforeUnload(event: BeforeUnloadEvent) {
      if (!dirtyRef.current || busy) return;
      event.preventDefault();
      event.returnValue = '';
    }
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [busy]);

  const lineErrors = useMemo(() => {
    const map: Record<string, LineErrors> = {};
    lines.forEach(line => { map[line.key] = validateLine(line, isAdmin); });
    return map;
  }, [lines, isAdmin]);

  const totals = useMemo(() => {
    const quantity = lines.reduce((sum, line) => sum + lineQuantity(line), 0);
    const subtotal = moneyAdd(...lines.map(line => lineTotal(line)));
    return { quantity, subtotal };
  }, [lines]);

  function patchLine(key: string, patch: Partial<DraftLine>) {
    setLines(prev => prev.map(line => (line.key === key ? { ...line, ...patch } : line)));
  }

  function addLine() {
    setLines(prev => [...prev, emptyLine()]);
  }

  function removeLine(key: string) {
    setLines(prev => prev.filter(line => line.key !== key));
  }

  async function searchLineItems(line: DraftLine) {
    const term = line.search.trim();
    if (!term) { patchLine(line.key, { results: [] }); return; }
    patchLine(line.key, { searching: true });
    try {
      const found = await api<Item[]>(`/inventory/items/search?q=${encodeURIComponent(term)}`);
      patchLine(line.key, { results: found });
    } catch (err) {
      onError?.((err as Error).message);
    } finally {
      patchLine(line.key, { searching: false });
    }
  }

  async function requestView(next: 'entry' | 'history') {
    if (next === view) return;
    if (view === 'entry' && dirty) {
      const discard = await modal.confirm({
        title: 'Discard this purchase?',
        message: 'You have lines that are not saved yet. Leave the entry screen and lose them?',
        confirmText: 'Discard',
        cancelText: 'Keep editing',
      });
      if (!discard) return;
      resetEntry();
    }
    setView(next);
    if (next === 'history' && !historyLoaded) void loadHistory();
  }

  function resetEntry() {
    setLines([]);
    setReference('');
    setNotes('');
    setSupplierId('');
    setDate(today());
    setSubmitAttempted(false);
    setSaveError('');
    setPurchaseKey(crypto.randomUUID());
  }

  async function cancelEntry() {
    if (!dirty) { resetEntry(); return; }
    const discard = await modal.confirm({
      title: 'Discard this purchase?',
      message: 'All unsaved lines will be lost.',
      confirmText: 'Discard',
      cancelText: 'Keep editing',
    });
    if (discard) resetEntry();
  }

  async function save() {
    if (busy) return;
    setSubmitAttempted(true);
    setSaveError('');
    if (!lines.length) { onError?.('Add at least one line before saving.'); return; }
    const invalid = lines.find(line => Object.keys(validateLine(line, isAdmin)).length > 0);
    if (invalid) {
      const errors = validateLine(invalid, isAdmin);
      const message = errors.item || errors.quantity || errors.cost || 'Check the highlighted line.';
      toast.error(message);
      return;
    }
    const allSerials = lines.flatMap(line => (line.item?.is_serialized ? parseSerials(line.serials) : []));
    if (new Set(allSerials).size !== allSerials.length) {
      toast.error('The same IMEI/serial is entered more than once.');
      return;
    }
    setBusy(true);
    try {
      await api('/purchases', {
        method: 'POST',
        body: JSON.stringify({
          purchase_date: date,
          reference_no: reference.trim() || null,
          notes: notes.trim() || null,
          supplier_id: isAdmin ? (supplierId || null) : null,
          lines: lines.map(line => {
            const serials = line.item?.is_serialized ? parseSerials(line.serials) : [];
            const payload: Record<string, unknown> = {
              item_id: line.item?.item_id,
              quantity: line.item?.is_serialized ? String(serials.length) : line.quantity,
              line_date: date,
            };
            if (serials.length) payload.serial_numbers = serials;
            if (isAdmin && line.unitCost.trim() !== '') payload.unit_cost = line.unitCost;
            return payload;
          }),
          idempotency_key: purchaseKey,
        }),
      });
      toast.success(`Purchase saved with ${lines.length} line(s).`);
      resetEntry();
      if (historyLoaded) void loadHistory();
    } catch (err) {
      setSaveError((err as Error).message);
      onError?.((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      setHistory(await api<PurchaseSummary[]>('/purchases'));
      setHistoryLoaded(true);
    } catch (err) {
      onError?.((err as Error).message);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function openDetail(purchaseId: string) {
    setDetailLoading(true);
    setCostDrafts({});
    try {
      setDetail(await api<PurchaseDetail>(`/purchases/${purchaseId}`));
    } catch (err) {
      onError?.((err as Error).message);
    } finally {
      setDetailLoading(false);
    }
  }

  async function reloadDetail(purchaseId: string) {
    try { setDetail(await api<PurchaseDetail>(`/purchases/${purchaseId}`)); }
    catch (err) { onError?.((err as Error).message); }
    if (historyLoaded) void loadHistory();
  }

  async function enterCost(line: DetailLine) {
    if (!detail || costBusy) return;
    const value = (costDrafts[line.purchase_line_id] || '').trim();
    if (value === '' || Number(value) < 0 || !Number.isFinite(Number(value))) {
      onError?.('Enter a valid buy cost first.');
      return;
    }
    setCostBusy(line.purchase_line_id);
    try {
      await api('/purchases/complete-cost', {
        method: 'POST',
        body: JSON.stringify({
          version: line.version,
          purchase_version: detail.version,
          purchase_id: detail.purchase_id,
          purchase_line_id: line.purchase_line_id,
          unit_cost: value,
        }),
      });
      setCostDrafts(prev => { const next = { ...prev }; delete next[line.purchase_line_id]; return next; });
      toast.success('Buy cost saved.');
      await reloadDetail(detail.purchase_id);
    } catch (err) {
      onError?.((err as Error).message);
    } finally {
      setCostBusy('');
    }
  }

  function openCorrection(field: CorrectionField, options: { purchaseId: string; purchaseVersion: number; lineId?: string; lineVersion?: number; initial: string; title: string }) {
    setCorrection({
      field, purchaseId: options.purchaseId, purchaseVersion: options.purchaseVersion,
      lineId: options.lineId ?? null, lineVersion: options.lineVersion ?? 0,
      title: options.title, initial: options.initial,
    });
    setCorrectionValue(options.initial);
    setCorrectionReason('');
    setAdminPassword('');
  }

  async function applyCorrection() {
    if (!correction || savingCorrection) return;
    if (!correctionReason.trim()) { onError?.('Correction reason is required.'); return; }
    if (!adminPassword) { onError?.('Admin re-authentication password is required.'); return; }
    setSavingCorrection(true);
    try {
      let path = '';
      let body: Record<string, unknown> = {};
      if (correction.field === 'cost') {
        path = '/purchases/correct-cost';
        body = { purchase_line_id: correction.lineId, version: correction.lineVersion, unit_cost: correctionValue, reason: correctionReason.trim() };
      } else if (correction.field === 'date') {
        path = '/purchases/correct-date';
        body = { purchase_line_id: correction.lineId, version: correction.lineVersion, line_date: correctionValue, reason: correctionReason.trim() };
      } else if (correction.field === 'quantity') {
        path = '/purchases/correct-quantity';
        body = { purchase_line_id: correction.lineId, version: correction.lineVersion, quantity: correctionValue, reason: correctionReason.trim() };
      } else if (correction.field === 'reference') {
        path = '/purchases/correct-reference';
        body = { purchase_id: correction.purchaseId, version: correction.purchaseVersion, reference_no: correctionValue.trim() || null, reason: correctionReason.trim() };
      }
      if (correction.field === 'supplier') {
        const params = new URLSearchParams({ version: String(correction.purchaseVersion), admin_password: adminPassword });
        if (correctionValue) params.set('supplier_id', correctionValue);
        await api(`/purchases/${correction.purchaseId}/supplier?${params.toString()}`, { method: 'PUT' });
      } else {
        await api(`${path}?admin_password=${encodeURIComponent(adminPassword)}`, { method: 'POST', body: JSON.stringify(body) });
      }
      toast.success('Correction saved (audited).');
      setCorrection(null);
      setAdminPassword('');
      if (detail) await reloadDetail(detail.purchase_id);
      else if (historyLoaded) void loadHistory();
    } catch (err) {
      onError?.((err as Error).message);
    } finally {
      setSavingCorrection(false);
    }
  }

  const supplierOptions = useMemo(() => {
    const map = new Map<string, string>();
    history.forEach(row => { if (row.supplier_id && row.supplier_name) map.set(row.supplier_id, row.supplier_name); });
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [history]);

  const filteredHistory = useMemo(() => history.filter(row => {
    if (filterFrom && row.purchase_date < filterFrom) return false;
    if (filterTo && row.purchase_date > filterTo) return false;
    if (filterSupplier && row.supplier_id !== filterSupplier) return false;
    if (filterStatus === 'PENDING' && row.pending_cost_lines === 0) return false;
    if (filterStatus === 'COMPLETED' && row.pending_cost_lines > 0) return false;
    const term = filterSearch.trim().toLowerCase();
    if (!term) return true;
    return [row.reference_no ?? '', row.supplier_name ?? '', row.created_by ?? '', row.purchase_date]
      .join(' ').toLowerCase().includes(term);
  }), [history, filterFrom, filterTo, filterSupplier, filterStatus, filterSearch]);

  function statusBadge(row: { pending_cost_lines: number }) {
    if (row.pending_cost_lines > 0) {
      return <span className="status-badge status-warning">{isAdmin ? 'Cost Pending' : 'Awaiting admin review'}</span>;
    }
    return <span className="status-badge status-success">Completed</span>;
  }

  return (
    <section className="purchases-v2">
      <div className="glass panel">
        <div className="section-head">
          <div>
            <span className="eyebrow">INVENTORY IN</span>
            <h2>Purchases</h2>
            <p className="muted">
              {isAdmin
                ? 'Record supplier invoices with line quantities and buy cost. Costs are Admin-only.'
                : 'Record supplier deliveries. Buy cost is entered by an Admin after review.'}
            </p>
          </div>
          <div className="button-row">
            <button type="button" className={view === 'entry' ? 'primary' : ''} onClick={() => void requestView('entry')}>New Purchase</button>
            <button type="button" className={view === 'history' ? 'primary' : ''} onClick={() => void requestView('history')}>History</button>
          </div>
        </div>
      </div>

      {view === 'entry' && (
        <>
          <div className="glass panel">
            <div className="purchase-meta-grid">
              <label>Purchase date
                <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
              </label>
              <label>Invoice / reference
                <input value={reference} maxLength={100} onChange={(event) => setReference(event.target.value)} placeholder="Supplier invoice / GRN" />
              </label>
              {isAdmin && (
                <label>Supplier
                  <select value={supplierId} onChange={(event) => setSupplierId(event.target.value)}>
                    <option value="">No supplier</option>
                    {suppliers.map(supplier => <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.name}</option>)}
                  </select>
                </label>
              )}
            </div>
            <label className="wide-field">Notes
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Optional purchase note" />
            </label>
          </div>

          {saveError && (
            <div className="modal-error-banner" role="alert">
              <div className="modal-error-banner-title"><span>⚠</span> Could not save purchase</div>
              <div>{saveError}</div>
              <button type="button" className="ghost" onClick={() => void save()} disabled={busy}>Retry save</button>
            </div>
          )}

          <div className="purchases-entry-grid">
            <div className="glass panel">
              <div className="section-head">
                <div><h3>Lines</h3><p className="muted">Search an item, set quantity and leave the rest to the summary.</p></div>
                <span className="feature-badge">{lines.length} line{lines.length === 1 ? '' : 's'}</span>
              </div>

              {!lines.length && (
                <div className="empty-state purchase-empty">
                  <b>No lines yet</b>
                  <span>Click “+ Add Line” to begin.</span>
                </div>
              )}

              {lines.length > 0 && (
                <div className="purchase-table-wrap">
                  <table className="purchase-line-table">
                    <thead>
                      <tr>
                        <th>Item</th>
                        <th>Qty</th>
                        {isAdmin && <th>Unit cost</th>}
                        {isAdmin && <th>Line total</th>}
                        <th aria-label="Actions" />
                      </tr>
                    </thead>
                    <tbody>
                      {lines.map(line => {
                        const errors = lineErrors[line.key];
                        const showError = submitAttempted;
                        return (
                          <tr key={line.key}>
                            <td>
                              {line.item ? (
                                <div className="purchase-line-item">
                                  <span><b>{line.item.item_code}</b> · {line.item.description}</span>
                                  <button type="button" className="ghost" onClick={() => patchLine(line.key, { item: null, results: [], search: '' })}>Change</button>
                                </div>
                              ) : (
                                <div className="purchase-line-search">
                                  <div className="search-row">
                                    <input
                                      value={line.search}
                                      onChange={(event) => patchLine(line.key, { search: event.target.value })}
                                      onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); void searchLineItems(line); } }}
                                      placeholder="Search item code / description"
                                      aria-label="Search item for this line"
                                    />
                                    <button type="button" onClick={() => void searchLineItems(line)} disabled={line.searching}>
                                      {line.searching ? '…' : 'Search'}
                                    </button>
                                  </div>
                                  {line.results.length > 0 && (
                                    <div className="purchase-line-results">
                                      {line.results.slice(0, 8).map(item => (
                                        <button
                                          key={item.item_id}
                                          type="button"
                                          onClick={() => patchLine(line.key, { item, results: [], search: '' })}
                                        >
                                          <b>{item.item_code}</b> · {item.description} <small>stock {item.stock}</small>
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                              {showError && errors.item && <span className="item-field-error">{errors.item}</span>}
                            </td>
                            <td>
                              {line.item?.is_serialized ? (
                                <div className="purchase-serial-cell">
                                  <span className="feature-badge">{lineQuantity(line)} IMEI</span>
                                  <textarea
                                    value={line.serials}
                                    onChange={(event) => patchLine(line.key, { serials: event.target.value })}
                                    placeholder="One IMEI/serial per line"
                                    aria-label="IMEI list for this line"
                                  />
                                </div>
                              ) : (
                                <input
                                  {...intInputProps(line.quantity, (value) => patchLine(line.key, { quantity: value }), 1)}
                                  style={{ width: 84 }}
                                  aria-label="Line quantity"
                                />
                              )}
                              {showError && errors.quantity && <span className="item-field-error">{errors.quantity}</span>}
                            </td>
                            {isAdmin && (
                              <td>
                                <input {...moneyInputProps(line.unitCost, (value) => patchLine(line.key, { unitCost: value }))} style={{ width: 110 }} placeholder="Pending" aria-label="Unit cost" />
                                {showError && errors.cost && <span className="item-field-error">{errors.cost}</span>}
                              </td>
                            )}
                            {isAdmin && <td className="purchase-line-total">{costValue(line.unitCost) === null ? '—' : `Rs. ${lineTotal(line)}`}</td>}
                            <td>
                              <button type="button" className="danger-button" onClick={() => removeLine(line.key)} aria-label="Remove line">Remove</button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="form-actions purchase-line-actions">
                <button type="button" onClick={addLine}>+ Add Line</button>
                <span className="muted">Item, quantity and cost are validated per line.</span>
              </div>
            </div>

            <aside className="glass panel purchase-summary">
              <h3>Summary</h3>
              <div className="purchase-summary-row"><span>Lines</span><b>{lines.length}</b></div>
              <div className="purchase-summary-row"><span>Total quantity</span><b>{totals.quantity}</b></div>
              {isAdmin ? (
                <>
                  <div className="purchase-summary-row"><span>Subtotal</span><b>Rs. {totals.subtotal}</b></div>
                  <div className="purchase-summary-total"><span>Grand total</span><b>Rs. {totals.subtotal}</b></div>
                  <p className="muted">Lines saved without a cost stay in the Admin pending-cost queue.</p>
                </>
              ) : (
                <p className="muted">Buy cost is entered by an Admin. Your purchase will be marked “Awaiting admin review”.</p>
              )}
              <div className="form-actions purchase-summary-actions">
                <button type="button" className="ghost" onClick={() => void cancelEntry()} disabled={busy}>Cancel</button>
                <button type="button" className="primary" disabled={busy} onClick={() => void save()}>
                  {busy ? <><span className="spinner" /> Saving…</> : 'Save Purchase'}
                </button>
              </div>
            </aside>
          </div>
        </>
      )}

      {view === 'history' && (
        <div className="glass panel">
          <div className="section-head">
            <div><h3>Purchase history</h3><p className="muted">Each saved purchase is one document. Click a row to open its lines.</p></div>
            <button type="button" onClick={() => void loadHistory()} disabled={historyLoading}>{historyLoading ? 'Loading…' : 'Refresh'}</button>
          </div>
          <div className="purchase-history-filters">
            <input value={filterSearch} onChange={(event) => setFilterSearch(event.target.value)} placeholder="Search invoice, supplier, cashier" aria-label="Search purchases" />
            <label>From<input type="date" value={filterFrom} onChange={(event) => setFilterFrom(event.target.value)} /></label>
            <label>To<input type="date" value={filterTo} onChange={(event) => setFilterTo(event.target.value)} /></label>
            <label>Supplier
              <select value={filterSupplier} onChange={(event) => setFilterSupplier(event.target.value)}>
                <option value="">All suppliers</option>
                {supplierOptions.map(option => <option key={option.id} value={option.id}>{option.name}</option>)}
              </select>
            </label>
            <label>Status
              <select value={filterStatus} onChange={(event) => setFilterStatus(event.target.value as 'ALL' | 'PENDING' | 'COMPLETED')}>
                <option value="ALL">All</option>
                <option value="PENDING">Pending cost</option>
                <option value="COMPLETED">Completed</option>
              </select>
            </label>
          </div>

          {!historyLoaded && !historyLoading && <p className="muted">Loading purchase history…</p>}
          {historyLoaded && filteredHistory.length === 0 && <p className="muted">No purchases match these filters.</p>}
          {filteredHistory.length > 0 && (
            <div className="purchase-table-wrap">
              <table className="purchase-history-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Supplier</th>
                    <th>Invoice ref</th>
                    <th>Lines</th>
                    {isAdmin && <th>Total</th>}
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHistory.map(row => (
                    <tr
                      key={row.purchase_id}
                      tabIndex={0}
                      onClick={() => void openDetail(row.purchase_id)}
                      onKeyDown={(event) => { if (event.key === 'Enter') void openDetail(row.purchase_id); }}
                    >
                      <td>{row.purchase_date}</td>
                      <td>{row.supplier_name || 'No supplier'}</td>
                      <td>{row.reference_no || '—'}</td>
                      <td>{row.line_count} · {money(row.total_quantity)} qty</td>
                      {isAdmin && <td>{row.total_cost == null ? '—' : `Rs. ${money(row.total_cost)}`}</td>}
                      <td>{statusBadge(row)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {detail && (
        <div className="modal-overlay" onClick={(event) => { if (event.target === event.currentTarget) setDetail(null); }}>
          <div className="modal-card purchase-detail-modal" role="dialog" aria-modal="true" aria-labelledby="purchase-detail-title">
            <div className="modal-header">
              <h3 id="purchase-detail-title">Purchase · {detail.purchase_date}</h3>
              <button type="button" className="modal-close" onClick={() => setDetail(null)} aria-label="Close">×</button>
            </div>
            <div className="modal-body">
              <div className="purchase-detail-meta">
                <span><small>Supplier</small><b>{detail.supplier_name || 'No supplier'}</b></span>
                <span><small>Invoice ref</small><b>{detail.reference_no || '—'}</b></span>
                <span><small>Recorded by</small><b>{detail.created_by || '—'}</b></span>
                <span><small>Status</small>{statusBadge(detail)}</span>
                {isAdmin && <span><small>Total</small><b>{detail.total_cost == null ? '—' : `Rs. ${money(detail.total_cost)}`}</b></span>}
              </div>
              {detail.notes && <p className="muted">{detail.notes}</p>}

              <div className="purchase-table-wrap">
                <table className="purchase-line-table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Qty</th>
                      {isAdmin && <th>Unit cost</th>}
                      {isAdmin && <th>Line total</th>}
                      {isAdmin && <th>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {detail.lines.map(line => (
                      <tr key={line.purchase_line_id}>
                        <td><b>{line.item_code}</b> · {line.item_description}</td>
                        <td>{money(line.quantity)}</td>
                        {isAdmin && (
                          <td>
                            {line.unit_cost == null ? (
                              <div className="purchase-cost-entry">
                                <input
                                  {...moneyInputProps(costDrafts[line.purchase_line_id] || '', (value) => setCostDrafts(prev => ({ ...prev, [line.purchase_line_id]: value })))}
                                  placeholder="Buy cost"
                                  aria-label={`Buy cost for ${line.item_code}`}
                                />
                                <button type="button" disabled={costBusy === line.purchase_line_id} onClick={() => void enterCost(line)}>
                                  {costBusy === line.purchase_line_id ? 'Saving…' : 'Enter Cost'}
                                </button>
                              </div>
                            ) : `Rs. ${money(line.unit_cost)}`}
                          </td>
                        )}
                        {isAdmin && <td>{line.line_total == null ? '—' : `Rs. ${money(line.line_total)}`}</td>}
                        {isAdmin && (
                          <td>
                            <div className="button-row purchase-row-actions">
                              <button type="button" disabled={line.unit_cost == null} onClick={() => openCorrection('cost', { purchaseId: detail.purchase_id, purchaseVersion: detail.version, lineId: line.purchase_line_id, lineVersion: line.version, initial: String(line.unit_cost ?? ''), title: `Correct cost · ${line.item_code}` })}>Cost</button>
                              <button type="button" onClick={() => openCorrection('quantity', { purchaseId: detail.purchase_id, purchaseVersion: detail.version, lineId: line.purchase_line_id, lineVersion: line.version, initial: String(line.quantity), title: `Correct quantity · ${line.item_code}` })}>Qty</button>
                              <button type="button" onClick={() => openCorrection('date', { purchaseId: detail.purchase_id, purchaseVersion: detail.version, lineId: line.purchase_line_id, lineVersion: line.version, initial: line.line_date, title: `Correct date · ${line.item_code}` })}>Date</button>
                            </div>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {isAdmin && (
                <div className="button-row purchase-detail-admin">
                  <button type="button" onClick={() => openCorrection('reference', { purchaseId: detail.purchase_id, purchaseVersion: detail.version, initial: detail.reference_no ?? '', title: 'Correct invoice reference' })}>Correct reference</button>
                  <button type="button" onClick={() => openCorrection('supplier', { purchaseId: detail.purchase_id, purchaseVersion: detail.version, initial: detail.supplier_id ?? '', title: 'Assign supplier' })}>Assign supplier</button>
                </div>
              )}
              <div className="modal-actions">
                <button type="button" className="ghost" onClick={() => setDetail(null)}>Close</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {detailLoading && (
        <div className="loading-overlay" aria-live="polite">
          <div style={{ display: 'grid', placeItems: 'center', gap: 8 }}>
            <span className="spinner spinner-lg" />
            <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>Loading purchase…</span>
          </div>
        </div>
      )}

      {correction && (
        <div className="modal-overlay" onClick={(event) => { if (event.target === event.currentTarget && !savingCorrection) setCorrection(null); }}>
          <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="purchase-correction-title">
            <div className="modal-header">
              <h3 id="purchase-correction-title">{correction.title}</h3>
              <button type="button" className="modal-close" onClick={() => setCorrection(null)} aria-label="Close" disabled={savingCorrection}>×</button>
            </div>
            <div className="modal-body">
              {correction.field === 'supplier' ? (
                <label className="wide-field">Supplier
                  <select value={correctionValue} onChange={(event) => setCorrectionValue(event.target.value)}>
                    <option value="">Clear supplier</option>
                    {suppliers.map(supplier => <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.name}</option>)}
                  </select>
                </label>
              ) : correction.field === 'date' ? (
                <label className="wide-field">Date<input type="date" value={correctionValue} onChange={(event) => setCorrectionValue(event.target.value)} /></label>
              ) : correction.field === 'quantity' ? (
                <label className="wide-field">Quantity<input {...intInputProps(correctionValue, setCorrectionValue, 1)} /></label>
              ) : correction.field === 'cost' ? (
                <label className="wide-field">Unit cost<input {...moneyInputProps(correctionValue, setCorrectionValue)} /></label>
              ) : (
                <label className="wide-field">Reference<input value={correctionValue} maxLength={100} onChange={(event) => setCorrectionValue(event.target.value)} /></label>
              )}
              <label className="wide-field">Reason<textarea value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} placeholder="Why is this correction required?" /></label>
              <label className="wide-field">Admin password<input type="password" value={adminPassword} onChange={(event) => setAdminPassword(event.target.value)} placeholder="Re-authentication" /></label>
              <div className="modal-actions">
                <button type="button" className="ghost" onClick={() => setCorrection(null)} disabled={savingCorrection}>Cancel</button>
                <button type="button" disabled={savingCorrection} onClick={() => void applyCorrection()}>{savingCorrection ? 'Applying…' : 'Apply audited correction'}</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
