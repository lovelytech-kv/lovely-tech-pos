import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { money } from '../../services/money';
import { useModal } from '../../ui/modals';
import { toast } from '../../ui/toast';

type Props = {
  isAdmin: boolean;
  onError: (message: string) => void;
  onNavigate: (key: string) => void;
  user: { display_name: string; role: string; branch_id: string; username?: string };
};

type SaleListItem = {
  sale_id: string;
  invoice_no: string;
  sale_datetime: string;
  customer_name: string | null;
  customer_contact: string | null;
  item_count: number;
  grand_total: string;
  payment_summary: string;
  cashier_name: string;
  cashier_id: string;
  status: string;
  is_voided: boolean;
};

type SaleLine = {
  sale_line_id: string;
  item_id: string;
  item_code: string;
  description: string;
  quantity: string | number;
  unit_price: string | number;
  discount: string | number;
  final_total: string | number;
  serialized_unit_id?: string | null;
};

type SaleDetail = {
  sale_id: string;
  invoice_no: string;
  sale_datetime: string;
  grand_total: string | number;
  version: number;
  lines: SaleLine[];
};

type Filters = {
  date_from: string;
  date_to: string;
  q: string;
  payment_method: string;
  status: string;
  cashier_id: string;
};

const today = () => new Date().toISOString().slice(0, 10);
const LIMIT = 50;

export function SalesHistory({ isAdmin, onError, onNavigate, user }: Props) {
  const [filters, setFilters] = useState<Filters>({
    date_from: today(),
    date_to: today(),
    q: '',
    payment_method: '',
    status: '',
    cashier_id: '',
  });
  const [sales, setSales] = useState<SaleListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [selectedItem, setSelectedItem] = useState<SaleListItem | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<SaleDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [cashiers, setCashiers] = useState<Array<{ user_id: string; display_name: string; role: string }>>([]);

  const modal = useModal();
  const debounceRef = useRef<number | null>(null);

  // Load cashiers dropdown (admin only)
  useEffect(() => {
    if (!isAdmin) return;
    (async () => {
      try {
        const users = await api<Array<{ user_id: string; display_name: string; role: string }>>('/admin/users');
        setCashiers(users.filter((u) => u.role.toUpperCase() === 'CASHIER'));
      } catch {
        // non-critical
      }
    })();
  }, [isAdmin]);

  const fetchSales = useCallback(
    async (append = false) => {
      try {
        if (append) setLoadingMore(true);
        else setLoading(true);
        const params = new URLSearchParams();
        if (filters.date_from) params.set('date_from', filters.date_from);
        if (filters.date_to) params.set('date_to', filters.date_to);
        if (filters.q.trim()) params.set('q', filters.q.trim());
        if (filters.payment_method) params.set('payment_method', filters.payment_method);
        if (filters.status) params.set('status', filters.status);
        if (isAdmin && filters.cashier_id) params.set('cashier_id', filters.cashier_id);
        params.set('limit', String(LIMIT));
        params.set('offset', String(append ? sales.length : 0));
        const result = await api<{ items: SaleListItem[]; total: number; has_more: boolean }>(
          `/sales?${params.toString()}`,
        );
        if (append) setSales((prev) => [...prev, ...result.items]);
        else setSales(result.items);
        setTotal(result.total);
        setHasMore(result.has_more);
      } catch (e) {
        onError((e as Error).message);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filters, isAdmin, onError, sales.length],
  );

  // Fetch on filter change (debounced for text search)
  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    const delay = filters.q !== '' ? 300 : 0;
    debounceRef.current = window.setTimeout(() => {
      void fetchSales(false);
    }, delay);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.date_from, filters.date_to, filters.q, filters.payment_method, filters.status, filters.cashier_id]);

  async function openSale(item: SaleListItem) {
    setSelectedItem(item);
    setSelectedDetail(null);
    try {
      setDetailLoading(true);
      const detail = await api<SaleDetail>(`/sales/${encodeURIComponent(item.invoice_no)}`);
      setSelectedDetail(detail);
    } catch (e) {
      onError((e as Error).message);
      // If sale is VOIDED, backend get_sale_detail returns 404 (only COMPLETED).
      // We still show the list-item info; user can't view lines for voided sales.
      setSelectedDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }

  function closeDetail() {
    setSelectedItem(null);
    setSelectedDetail(null);
  }

  function quickRange(kind: 'today' | 'yesterday' | 'week' | 'month') {
    const now = new Date();
    if (kind === 'today') {
      setFilters((f) => ({ ...f, date_from: today(), date_to: today() }));
    } else if (kind === 'yesterday') {
      const y = new Date(now);
      y.setDate(y.getDate() - 1);
      const yStr = y.toISOString().slice(0, 10);
      setFilters((f) => ({ ...f, date_from: yStr, date_to: yStr }));
    } else if (kind === 'week') {
      const w = new Date(now);
      w.setDate(w.getDate() - 6);
      setFilters((f) => ({ ...f, date_from: w.toISOString().slice(0, 10), date_to: today() }));
    } else {
      const m = new Date(now);
      m.setDate(m.getDate() - 29);
      setFilters((f) => ({ ...f, date_from: m.toISOString().slice(0, 10), date_to: today() }));
    }
  }

  function printReceipt(detail: SaleDetail) {
    const w = window.open('', '_blank', 'width=420,height=640');
    if (!w) {
      toast.error('Print popup blocked. Allow popups for this site.');
      return;
    }
    const lines = Array.isArray(detail.lines) ? detail.lines : [];
    w.document.write(`<!DOCTYPE html><html><head><title>Receipt ${detail.invoice_no}</title>
      <style>
        body{font-family:'Consolas','Menlo',monospace;padding:16px;font-size:13px;color:#000;}
        h1{font-size:16px;text-align:center;margin:0 0 4px;}
        .meta{text-align:center;font-size:11px;color:#333;margin-bottom:8px;}
        .divider{border-top:1px dashed #000;margin:8px 0;}
        .row{display:flex;justify-content:space-between;gap:8px;}
        .line{padding:2px 0;}
        .total{font-size:15px;font-weight:700;}
        .foot{text-align:center;font-size:11px;margin-top:8px;}
      </style></head><body>
      <h1>Lovely Tech POS</h1>
      <div class="meta">Invoice: ${detail.invoice_no}<br/>${new Date(detail.sale_datetime).toLocaleString()}</div>
      <div class="divider"></div>
      ${lines.map((l) => `
        <div class="line">
          <div>${l.description || l.item_code || ''}</div>
          <div class="row"><span>${l.quantity} × Rs. ${l.unit_price}</span><span>Rs. ${l.final_total}</span></div>
        </div>
      `).join('')}
      <div class="divider"></div>
      <div class="row total"><span>TOTAL</span><span>Rs. ${detail.grand_total}</span></div>
      <div class="divider"></div>
      <div class="foot">Thank you for shopping at Lovely Tech!</div>
      <script>window.onload = function(){ window.print(); };</script>
      </body></html>`);
    w.document.close();
  }

  async function voidSale() {
    if (!selectedItem || !selectedDetail) return;
    if (selectedItem.is_voided) {
      onError('This sale is already voided.');
      return;
    }
    const ok = await modal.confirm({
      title: 'Void Sale',
      message: `Void ${selectedItem.invoice_no}? Stock, IMEI, warranty, drawer and reports will be reversed. The invoice number is never reused.`,
      confirmText: 'Void Sale',
      cancelText: 'Cancel',
    });
    if (!ok) return;
    const reason = await modal.prompt({
      title: 'Void reason',
      message: 'Enter the reason for voiding this sale',
      placeholder: 'Reason',
      confirmText: 'Continue',
    });
    if (!reason?.trim()) return;
        const pw = await modal.prompt({
      title: 'Admin re-authentication',
      message: 'Enter admin password to void this sale',
      placeholder: 'Password',
      confirmText: 'Void Sale',
      type: 'password',
    });
    if (!pw) return;
    try {
      await api(
        `/sales/${encodeURIComponent(selectedDetail.sale_id)}/void?reason=${encodeURIComponent(reason.trim())}&version=${encodeURIComponent(String(selectedDetail.version))}&admin_password=${encodeURIComponent(pw)}`,
        { method: 'POST' },
      );
      toast.success(`${selectedItem.invoice_no} voided.`);
      closeDetail();
      await fetchSales(false);
    } catch (e) {
      onError((e as Error).message);
    }
  }

  function goToReturn() {
    if (!selectedItem) return;
    try {
      localStorage.setItem('ltpos_return_prefill', selectedItem.invoice_no);
    } catch {
      // ignore storage errors
    }
    onNavigate('Returns');
  }

    return (
    <section style={{ display: 'grid', gap: '1rem', minWidth: 0 }}>
      {/* FILTERS */}
      <div className="glass panel">
        <div className="section-head">
          <div>
            <span className="eyebrow">SALES HISTORY</span>
            <h2>All sales</h2>
            <p className="muted">
              {isAdmin
                ? 'Full sales list. Search, filter, view details, void or start a return.'
                : 'Your sales history. Search, filter, view details or start a return.'}
            </p>
          </div>
          <button className="ghost" onClick={() => void fetchSales(false)} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>

        <div className="form-grid compact" style={{ marginBottom: '0.5rem' }}>
          <label>
            From
            <input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} />
          </label>
          <label>
            To
            <input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} />
          </label>
          <div className="button-row">
            <button type="button" onClick={() => quickRange('today')}>Today</button>
            <button type="button" onClick={() => quickRange('yesterday')}>Yest</button>
            <button type="button" onClick={() => quickRange('week')}>Week</button>
            <button type="button" onClick={() => quickRange('month')}>Month</button>
          </div>
        </div>

        <div className="search-row" style={{ marginBottom: '0.5rem' }}>
          <input
            value={filters.q}
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
            placeholder="Search invoice / customer / phone / item code / description"
          />
        </div>

        <div className="form-grid compact">
          <label>
            Payment
            <select value={filters.payment_method} onChange={(e) => setFilters({ ...filters, payment_method: e.target.value })}>
              <option value="">All</option>
              <option value="CASH">Cash</option>
              <option value="CARD">Card</option>
              <option value="ONLINE">Online</option>
            </select>
          </label>
          <label>
            Status
            <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
              <option value="">All</option>
              <option value="COMPLETED">Completed</option>
              <option value="VOIDED">Voided</option>
            </select>
          </label>
          {isAdmin && (
            <label>
              Cashier
              <select value={filters.cashier_id} onChange={(e) => setFilters({ ...filters, cashier_id: e.target.value })}>
                <option value="">All cashiers</option>
                {cashiers.map((c) => (
                  <option key={c.user_id} value={c.user_id}>{c.display_name}</option>
                ))}
              </select>
            </label>
          )}
        </div>
      </div>

      {/* TABLE + DETAIL */}
      <div className="sales-history-layout">
        <div className="glass panel sales-history-table-wrap">
          {loading && sales.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center' }}>
              <span className="spinner spinner-lg" />
              <p className="muted" style={{ marginTop: '0.5rem' }}>Loading sales…</p>
            </div>
          ) : sales.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem', textAlign: 'center' }}>
              <b>No sales found for this period</b>
              <span className="muted">Adjust the date range, filters or search term.</span>
            </div>
          ) : (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ width: '100%' }}>
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Time</th>
                      <th>Customer</th>
                      <th style={{ textAlign: 'right' }}>Items</th>
                      <th style={{ textAlign: 'right' }}>Total</th>
                      <th>Payment</th>
                      {isAdmin && <th>Cashier</th>}
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sales.map((s) => (
                      <tr
                        key={s.sale_id}
                        onClick={() => void openSale(s)}
                        style={{
                          cursor: 'pointer',
                          background:
                            selectedItem?.sale_id === s.sale_id
                              ? 'rgba(var(--accent-rgb), 0.08)'
                              : undefined,
                        }}
                      >
                        <td><b>{s.invoice_no}</b></td>
                        <td>{new Date(s.sale_datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                        <td>{s.customer_name || s.customer_contact || '—'}</td>
                        <td style={{ textAlign: 'right' }}>{s.item_count}</td>
                        <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                          Rs. {money(s.grand_total)}
                        </td>
                        <td>{s.payment_summary}</td>
                        {isAdmin && <td>{s.cashier_name}</td>}
                        <td>
                          <span className={`sh-status ${s.is_voided ? 'sh-status-void' : 'sh-status-ok'}`}>
                            {s.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0.75rem',
                  borderTop: '1px solid var(--line)',
                }}
              >
                <span className="muted" style={{ fontSize: '0.75rem' }}>
                  Showing {sales.length} of {total}
                </span>
                {hasMore && (
                  <button className="ghost" onClick={() => void fetchSales(true)} disabled={loadingMore}>
                    {loadingMore ? 'Loading…' : 'Load more'}
                  </button>
                )}
              </div>
            </>
          )}
        </div>

        {/* DETAIL PANEL */}
        <div className="glass panel sales-history-detail">
          {!selectedItem ? (
            <div className="empty-state">
              <b>Select a sale</b>
              <span className="muted">Click any row to see items, totals and actions.</span>
            </div>
          ) : (
            <>
              <div className="section-head">
                <div>
                  <span className="eyebrow">SALE DETAIL</span>
                  <h3>{selectedItem.invoice_no}</h3>
                  <p className="muted" style={{ fontSize: '0.8rem', margin: '2px 0 0' }}>
                    {new Date(selectedItem.sale_datetime).toLocaleString()}
                  </p>
                </div>
                <button className="icon-button" onClick={closeDetail} aria-label="Close detail">×</button>
              </div>

              <div className="day-card" style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
                <span>Customer</span>
                <b>{selectedItem.customer_name || selectedItem.customer_contact || 'Walk-in'}</b>
                <span>Cashier</span>
                <b>{selectedItem.cashier_name}</b>
                <span>Payment</span>
                <b>{selectedItem.payment_summary}</b>
                <span>Status</span>
                <b>{selectedItem.status}</b>
              </div>

              <h4 style={{ marginTop: '0.75rem' }}>Items</h4>
              {detailLoading ? (
                <div style={{ padding: '1rem', textAlign: 'center' }}>
                  <span className="spinner" />
                </div>
              ) : selectedDetail ? (
                <div className="list-stack">
                  {selectedDetail.lines.length === 0 && <p className="muted">No lines.</p>}
                  {selectedDetail.lines.map((line) => (
                    <div className="stock-row" key={line.sale_line_id}>
                      <span>
                        <b>{line.description}</b>
                        <small> · {line.item_code}{line.serialized_unit_id ? ' · IMEI' : ''}</small>
                      </span>
                      <span style={{ whiteSpace: 'nowrap' }}>
                        {line.quantity} × Rs. {money(line.unit_price)} = <b>Rs. {money(line.final_total)}</b>
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">
                  {selectedItem.is_voided
                    ? 'Voided sales do not expose line items for viewing.'
                    : 'Could not load lines for this sale.'}
                </p>
              )}

              <div className="sales-totals" style={{ marginTop: '0.75rem' }}>
                <div className="total-row">
                  <span>TOTAL</span>
                  <span className="amount">Rs. {money(selectedItem.grand_total)}</span>
                </div>
              </div>

              <div className="button-row" style={{ marginTop: '1rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => selectedDetail && printReceipt(selectedDetail)}
                  disabled={!selectedDetail}
                >
                  🖨 Print
                </button>
                <button type="button" onClick={goToReturn}>
                  ↩ Return
                </button>
                {isAdmin && !selectedItem.is_voided && (
                  <button
                    type="button"
                    className="danger-button"
                    onClick={() => void voidSale()}
                    disabled={!selectedDetail}
                  >
                    🚫 Void
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}