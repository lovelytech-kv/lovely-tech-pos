import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { money } from '../../services/money';

type Item = { item_id: string; item_code: string; description: string; stock: string | number; sale_price?: string | number | null };
type Supplier = { supplier_id: string; name: string; contact_no?: string | null; address?: string | null };
type Pending = {
  version: number | null;
  purchase_version: number | null;
  purchase_id: string;
  purchase_line_id: string;
  purchase_date: string;
  reference_no?: string | null;
  item_id: string;
  quantity: string | number;
  unit_cost?: string | number | null;
};
type History = Pending & {
  line_date: string;
  supplier_id?: string | null;
  supplier_name?: string | null;
  item_code: string;
  item_description: string;
  status: string;
  payment_method?: string;
};

const today = () => new Date().toISOString().slice(0, 10);

export function Purchases({ isAdmin, onError }: { isAdmin: boolean; onError?: (message: string) => void }) {
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<Item[]>([]);
  const [selected, setSelected] = useState<Array<Item & { quantity: string }>>([]);
  const [quantity, setQuantity] = useState('1');
  const [date, setDate] = useState(today());
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [supplierId, setSupplierId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('CASH');
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [pending, setPending] = useState<Pending[]>([]);
  const [history, setHistory] = useState<History[]>([]);
  const [costs, setCosts] = useState<Record<string, string>>({});
  const [historyStart, setHistoryStart] = useState(today());
  const [historyEnd, setHistoryEnd] = useState(today());
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [purchaseKey, setPurchaseKey] = useState(() => crypto.randomUUID());
  const [correction, setCorrection] = useState<{ row: History; field: 'cost' | 'date' | 'quantity' | 'reference' | 'supplier' } | null>(null);
  const [correctionValue, setCorrectionValue] = useState('');
  const [correctionReason, setCorrectionReason] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [savingCorrection, setSavingCorrection] = useState(false);

  const selectedQty = useMemo(() => selected.reduce((sum, row) => sum + Number(row.quantity || 0), 0), [selected]);

  async function search() {
    try { setItems(await api<Item[]>(`/inventory/items/search?q=${encodeURIComponent(query)}`)); }
    catch (e) { onError?.((e as Error).message); }
  }

  async function loadAdminData() {
    if (!isAdmin) return;
    try {
      const [p, s] = await Promise.all([api<Pending[]>('/purchases/pending-costs'), api<Supplier[]>('/admin/suppliers')]);
      setPending(p); setSuppliers(s);
    } catch (e) { onError?.((e as Error).message); }
  }

  async function loadHistory() {
    if (!isAdmin) return;
    try {
      const rows = await api<History[]>('/purchases/history');
      const filtered = rows.filter(row => row.purchase_date >= historyStart && row.purchase_date <= historyEnd);
      setHistory(filtered); setHistoryLoaded(true);
    } catch (e) { onError?.((e as Error).message); }
  }

  useEffect(() => { loadAdminData(); }, [isAdmin]);

  function add(item: Item) {
    setSelected(prev => prev.some(x => x.item_id === item.item_id)
      ? prev.map(x => x.item_id === item.item_id ? { ...x, quantity } : x)
      : [...prev, { ...item, quantity }]);
  }

  function remove(itemId: string) { setSelected(prev => prev.filter(x => x.item_id !== itemId)); }

  async function save() {
    if (!selected.length) { onError?.('Add at least one item.'); return; }
    if (selected.some(x => !Number.isFinite(Number(x.quantity)) || Number(x.quantity) <= 0)) { onError?.('Every purchase quantity must be greater than zero.'); return; }
    setBusy(true);
    try {
      await api('/purchases', {
        method: 'POST',
        body: JSON.stringify({
          purchase_date: date,
          reference_no: reference.trim() || null,
          notes: notes.trim() || null,
          supplier_id: isAdmin ? (supplierId || null) : null,
          payment_method: paymentMethod,
          lines: selected.map(x => ({ item_id: x.item_id, quantity: x.quantity, line_date: date })),
          idempotency_key: purchaseKey,
        }),
      });
      setSelected([]); setReference(''); setNotes(''); setSupplierId(''); setPaymentMethod('CASH'); setQuantity('1'); setPurchaseKey(crypto.randomUUID());
      await loadAdminData();
    } catch (e) { onError?.((e as Error).message); }
    finally { setBusy(false); }
  }

  async function completeCost(row: Pending) {
    const value = costs[row.purchase_line_id];
    if (!value || Number(value) < 0) { onError?.('Enter a valid buy cost first.'); return; }
    try {
      await api('/purchases/complete-cost', { method: 'POST', body: JSON.stringify({ version: row.version, purchase_version: row.purchase_version, purchase_id: row.purchase_id, purchase_line_id: row.purchase_line_id, unit_cost: value }) });
      setCosts(prev => ({ ...prev, [row.purchase_line_id]: '' }));
      await loadAdminData();
    } catch (e) { onError?.((e as Error).message); }
  }

  function openCorrection(row: History, field: 'cost' | 'date' | 'quantity' | 'reference' | 'supplier') {
    const initial = field === 'cost' ? String(row.unit_cost ?? '') : field === 'date' ? row.line_date : field === 'quantity' ? String(row.quantity) : field === 'reference' ? String(row.reference_no ?? '') : String(row.supplier_id ?? '');
    setCorrection({ row, field }); setCorrectionValue(initial); setCorrectionReason(''); setAdminPassword('');
  }

  async function applyCorrection() {
    if (!correction) return;
    if (!correctionReason.trim()) { onError?.('Correction reason is required.'); return; }
    if (!adminPassword) { onError?.('Admin re-authentication password is required.'); return; }
    const { row, field } = correction;
    setSavingCorrection(true);
    try {
      let path = '';
      let body: Record<string, string | number | null> = {};
      if (field === 'cost') { path = '/purchases/correct-cost'; body = { purchase_line_id: row.purchase_line_id, version: row.version ?? 0, unit_cost: correctionValue, reason: correctionReason.trim() }; }
      if (field === 'date') { path = '/purchases/correct-date'; body = { purchase_line_id: row.purchase_line_id, version: row.version ?? 0, line_date: correctionValue, reason: correctionReason.trim() }; }
      if (field === 'quantity') { path = '/purchases/correct-quantity'; body = { purchase_line_id: row.purchase_line_id, version: row.version ?? 0, quantity: correctionValue, reason: correctionReason.trim() }; }
      if (field === 'reference') { path = '/purchases/correct-reference'; body = { purchase_id: row.purchase_id, version: row.purchase_version ?? 0, reference_no: correctionValue.trim() || null, reason: correctionReason.trim() }; }
      if (field === 'supplier') {
        const params = new URLSearchParams({ version: String(row.purchase_version ?? 0), admin_password: adminPassword });
        if (correctionValue) params.set('supplier_id', correctionValue);
        await api(`/purchases/${row.purchase_id}/supplier?${params.toString()}`, { method: 'PUT' });
      } else {
        await api(`${path}?admin_password=${encodeURIComponent(adminPassword)}`, { method: 'POST', body: JSON.stringify(body) });
      }
      setCorrection(null); setAdminPassword(''); await loadAdminData(); await loadHistory();
    } catch (e) { onError?.((e as Error).message); }
    finally { setSavingCorrection(false); }
  }

  return <section className="purchases-page">
    <div className="glass panel">
      <div className="section-head"><div><span className="eyebrow">INVENTORY IN</span><h2>Purchase Entry</h2><p className="muted">Record supplier, date, reference and quantities. Buy cost stays Admin-only.</p></div><span className="feature-badge">FIFO COST CONTROL</span></div>
      <div className="search-row"><input autoFocus value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && search()} placeholder="Search item code / description"/><button onClick={search}>Search</button></div>
      <div className="item-list">{items.map(item => <button className="item-card" key={item.item_id} onClick={() => add(item)}><b>{item.item_code}</b><span>{item.description}</span><small>Current stock: {item.stock}</small></button>)}</div>
      <div className="form-grid compact">
        <label>Date<input type="date" value={date} onChange={e => setDate(e.target.value)} /></label>
        <label>Reference<input value={reference} onChange={e => setReference(e.target.value)} placeholder="Supplier invoice / GRN" /></label>
        <label>Quantity<input type="number" min="0.001" step="0.001" value={quantity} onChange={e => setQuantity(e.target.value)} /></label>
        <label>Payment Method<select value={paymentMethod} onChange={e => setPaymentMethod(e.target.value)}><option value="CASH">Cash</option><option value="CARD">Card</option><option value="ONLINE">Online</option></select></label>
        {isAdmin && <label>Supplier<select value={supplierId} onChange={e => setSupplierId(e.target.value)}><option value="">No supplier</option>{suppliers.map(s => <option key={s.supplier_id} value={s.supplier_id}>{s.name}</option>)}</select></label>}
      </div>
      <label className="wide-field">Notes<textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Optional purchase note" /></label>
      {selected.length > 0 && <div className="status-strip"><div><span>Lines</span><b>{selected.length}</b></div><div><span>Total quantity</span><b>{selectedQty}</b></div><div><span>Cost visibility</span><b className="status-good">Admin only</b></div></div>}
      {selected.map(item => <div className="stock-row" key={item.item_id}><span><b>{item.item_code}</b> · {item.description} · Qty {item.quantity}</span><button className="danger-button" onClick={() => remove(item.item_id)}>Remove</button></div>)}
      <div className="form-actions"><button disabled={busy || !selected.length} onClick={save}>{busy ? 'Saving…' : 'Save Purchase'}</button><span className="muted">No buy cost is entered in this workspace.</span></div>
    </div>

    {isAdmin && <>
      <div className="glass panel">
        <div className="section-head"><div><h2>Admin · Pending Buy Cost</h2><p className="muted">Complete unresolved unit costs using optimistic-lock versions.</p></div><button onClick={loadAdminData}>Refresh</button></div>
        {!pending.length ? <p className="muted">No pending purchase costs.</p> : pending.map(row => <div className="pending-cost-row" key={row.purchase_line_id}><div><b>{row.reference_no || 'Purchase'}</b><span>{row.purchase_date} · Qty {row.quantity} · Line v{row.version ?? '—'} / Purchase v{row.purchase_version ?? '—'}</span></div><input className="cost-input" type="number" min="0" step="0.01" value={costs[row.purchase_line_id] || ''} onChange={e => setCosts(prev => ({ ...prev, [row.purchase_line_id]: e.target.value }))} placeholder="Buy cost"/><button onClick={() => completeCost(row)}>Complete Cost</button></div>)}
      </div>

      <div className="glass panel">
        <div className="section-head"><div><h2>Admin · Purchase History</h2><p className="muted">Review recorded supplier, quantity and FIFO cost, then make audited corrections.</p></div><button disabled={!historyLoaded} onClick={() => { setHistoryLoaded(false); loadHistory(); }}>Reload</button></div>
        <div className="form-grid compact"><label>From<input type="date" value={historyStart} onChange={e => setHistoryStart(e.target.value)} /></label><label>To<input type="date" value={historyEnd} onChange={e => setHistoryEnd(e.target.value)} /></label><button onClick={loadHistory}>Load History</button></div>
        {!historyLoaded ? <p className="muted">Select a date range and load history.</p> : !history.length ? <p className="muted">No purchase history in this date range.</p> : history.map(row => <div className="purchase-history-row" key={row.purchase_line_id}>
          <div className="purchase-history-main"><b>{row.item_code} · {row.item_description}</b><span>{row.purchase_date} · Line {row.line_date} · Qty {row.quantity} · {row.reference_no || 'No reference'}</span><small>Supplier: {row.supplier_name || 'No supplier'} · Payment: {row.payment_method || 'CASH'} · Unit cost: {row.unit_cost == null ? 'Pending' : `Rs. ${money(row.unit_cost)}`} · Versions: line {row.version ?? '—'}, purchase {row.purchase_version ?? '—'}</small></div>
          <div className="button-row"><button onClick={() => openCorrection(row, 'cost')} disabled={row.unit_cost == null}>Cost</button><button onClick={() => openCorrection(row, 'quantity')}>Qty</button><button onClick={() => openCorrection(row, 'date')}>Date</button><button onClick={() => openCorrection(row, 'reference')}>Reference</button><button onClick={() => openCorrection(row, 'supplier')}>Supplier</button></div>
        </div>)}
      </div>

      {correction && <div className="glass panel correction-panel"><div className="section-head"><div><span className="eyebrow">ADMIN RE-AUTH</span><h3>Correct {correction.field}</h3><p className="muted">{correction.row.item_code} · audited correction with version check.</p></div><button className="icon-button" onClick={() => setCorrection(null)}>×</button></div>
        {correction.field === 'supplier' ? <select value={correctionValue} onChange={e => setCorrectionValue(e.target.value)}><option value="">Clear supplier</option>{suppliers.map(s => <option key={s.supplier_id} value={s.supplier_id}>{s.name}</option>)}</select> : <input type={correction.field === 'date' ? 'date' : correction.field === 'quantity' || correction.field === 'cost' ? 'number' : 'text'} min={correction.field === 'quantity' ? '0.001' : correction.field === 'cost' ? '0' : undefined} step={correction.field === 'quantity' ? '0.001' : correction.field === 'cost' ? '0.01' : undefined} value={correctionValue} onChange={e => setCorrectionValue(e.target.value)} />}
        <label className="wide-field">Reason<textarea value={correctionReason} onChange={e => setCorrectionReason(e.target.value)} placeholder="Why is this correction required?" /></label>
        <label className="wide-field">Admin password<input type="password" value={adminPassword} onChange={e => setAdminPassword(e.target.value)} placeholder="Re-authentication" /></label>
        <div className="form-actions"><button disabled={savingCorrection} onClick={applyCorrection}>{savingCorrection ? 'Applying…' : 'Apply Audited Correction'}</button><button className="icon-button" onClick={() => setCorrection(null)}>Cancel</button></div>
      </div>}
    </>}
  </section>;
}
