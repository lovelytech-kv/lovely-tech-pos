import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { money } from '../../services/money';

export type RepairRow = {
  repair_id: string;
  repair_no: string;
  status: string;
  device_brand?: string | null;
  model?: string | null;
  customer_name?: string | null;
  contact_no?: string | null;
  date_in?: string | null;
  total_amount?: string | number | null;
  final_amount?: string | number | null;
  outstanding?: string | number | null;
};

type RepairDetail = RepairRow & {
  version: number;
  given_accessories?: string | null;
  special_note?: string | null;
  reported_fault?: string | null;
  estimated_amount?: string | number | null;
  labour_amount?: string | number | null;
  warranty_period?: string | null;
  repair_invoice_ref?: string | null;
  description_amount?: string | null;
  hand_over_date?: string | null;
  parts: RepairPart[];
  payments: RepairPayment[];
};

type RepairPart = {
  id: string;
  item_id: string;
  quantity: string | number;
  charge_amount: string | number;
  fifo_cost: string | number;
  status: string;
  notes?: string | null;
};

type RepairPayment = {
  id: string;
  method: string;
  amount: string | number;
  payment_datetime?: string | null;
  reference?: string | null;
  proof_no?: string | null;
  payment_type: string;
};

type Props = {
  isAdmin: boolean;
  onError: (message: string) => void;
};

const STATUS_FLOW: Record<string, string[]> = {
  RECEIVED: ['CHECKING'],
  CHECKING: ['REPAIRING', 'WAITING FOR PART'],
  'WAITING FOR PART': ['REPAIRING'],
  REPAIRING: ['READY'],
  READY: ['DELIVERED'],
};

export function RepairWorkspace({ isAdmin, onError }: Props) {
  const [rows, setRows] = useState<RepairRow[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState<RepairDetail | null>(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [loading, setLoading] = useState(false);

  const visibleRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((row) => {
      const statusMatch = statusFilter === 'ALL' || row.status === statusFilter;
      if (!statusMatch) return false;
      if (!q) return true;
      return [
        row.repair_no,
        row.device_brand,
        row.model,
        row.customer_name,
        row.contact_no,
        row.status,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .includes(q);
    });
  }, [rows, query, statusFilter]);

  async function loadRows(keepSelection = true) {
    try {
      setLoading(true);
      const result = await api<RepairRow[]>('/repairs');
      setRows(result);
      if (keepSelection && selectedId) {
        const selected = result.find((row) => row.repair_id === selectedId);
        if (selected) {
          await loadDetail(selected.repair_id, false);
        }
      }
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(repairId: string, updateSelection = true) {
    try {
      const result = await api<RepairDetail>(
        `/repairs/${encodeURIComponent(repairId)}`,
      );
      setDetail(result);
      if (updateSelection) setSelectedId(repairId);
    } catch (error) {
      onError((error as Error).message);
    }
  }

  useEffect(() => {
    void loadRows(false);
  }, []);

  async function action(
    path: string,
    body?: Record<string, unknown>,
    queryString = '',
  ) {
    try {
      await api(path + queryString, {
        method: 'POST',
        body: JSON.stringify(body ?? {}),
      });
      if (selectedId) await loadDetail(selectedId, false);
      await loadRows(true);
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function changeStatus(nextStatus: string) {
    if (!detail) return;
    await action(`/repairs/${detail.repair_id}/status`, {
      status: nextStatus,
      version: detail.version,
    });
  }

  async function deliver() {
    if (!detail) return;
    await action(
      `/repairs/${detail.repair_id}/deliver`,
      {},
      `?version=${encodeURIComponent(detail.version)}`,
    );
  }

  async function cancel() {
    if (!detail) return;
    const reason = window.prompt('Cancellation reason')?.trim();
    if (!reason) return;
    await action(`/repairs/${detail.repair_id}/cancel`, {
      version: detail.version,
      reason,
    });
  }

  return (
    <section className="workspace">
      <div className="glass panel">
        <div className="section-head">
          <div>
            <span className="eyebrow">SERVICE DESK</span>
            <h2>Repair jobs</h2>
            <p className="muted">
              Track intake, diagnosis, parts, payment, final amount, warranty
              and customer hand-over from one repair record.
            </p>
          </div>

          <button disabled={loading} onClick={() => void loadRows()}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>

        <div className="search-row">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Repair no / customer / device / contact"
          />

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="ALL">All statuses</option>
            <option value="RECEIVED">Received</option>
            <option value="CHECKING">Checking</option>
            <option value="REPAIRING">Repairing</option>
            <option value="WAITING FOR PART">Waiting for Part</option>
            <option value="READY">Ready</option>
            <option value="DELIVERED">Delivered</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>

        <div className="split">
          <div className="list-stack">
            {visibleRows.length === 0 && (
              <div className="empty-state">
                <b>No repair jobs found</b>
                <span>Change the search/filter or create a new repair intake above.</span>
              </div>
            )}

            {visibleRows.map((row) => (
              <button
                className={`list-row ${selectedId === row.repair_id ? 'selected' : ''}`}
                key={row.repair_id}
                onClick={() => void loadDetail(row.repair_id)}
              >
                <b>{row.repair_no}</b>
                <span>
                  {[row.device_brand, row.model].filter(Boolean).join(' ') || 'Device not specified'}
                </span>
                <small>
                  {row.status} · {row.customer_name || 'Walk-in'} · Outstanding Rs.{' '}
                  {money(row.outstanding)}
                </small>
              </button>
            ))}
          </div>

          {detail ? (
            <RepairDetailPanel
              detail={detail}
              isAdmin={isAdmin}
              onError={onError}
              onReload={() => loadDetail(detail.repair_id, false)}
              onAction={action}
              onStatus={changeStatus}
              onDeliver={deliver}
              onCancel={cancel}
            />
          ) : (
            <div className="empty-state">
              <b>Select a repair</b>
              <span>
                The complete job timeline, parts, payments and hand-over controls will appear here.
              </span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function RepairDetailPanel({
  detail,
  isAdmin,
  onError,
  onReload,
  onAction,
  onStatus,
  onDeliver,
  onCancel,
}: {
  detail: RepairDetail;
  isAdmin: boolean;
  onError: (message: string) => void;
  onReload: () => Promise<void>;
  onAction: (
    path: string,
    body?: Record<string, unknown>,
    queryString?: string,
  ) => Promise<void>;
  onStatus: (status: string) => Promise<void>;
  onDeliver: () => Promise<void>;
  onCancel: () => Promise<void>;
}) {
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('CASH');
  const [paymentReference, setPaymentReference] = useState('');
  const [paymentKey, setPaymentKey] = useState(() => crypto.randomUUID());
  const [finalAmount, setFinalAmount] = useState(String(detail.final_amount ?? ''));
  const [labourAmount, setLabourAmount] = useState(String(detail.labour_amount ?? ''));
  const [invoiceRef, setInvoiceRef] = useState(detail.repair_invoice_ref ?? '');
  const [descriptionAmount, setDescriptionAmount] = useState(detail.description_amount ?? '');
  const [handoverDate, setHandoverDate] = useState(detail.hand_over_date ?? '');
  const [partSearch, setPartSearch] = useState('');
  const [partItems, setPartItems] = useState<any[]>([]);
  const [partItemId, setPartItemId] = useState('');
  const [partQuantity, setPartQuantity] = useState('1');
  const [partCharge, setPartCharge] = useState('0');
  const [partNote, setPartNote] = useState('');
  const [warranty, setWarranty] = useState<any>(null);

  useEffect(() => {
    setFinalAmount(String(detail.final_amount ?? ''));
    setLabourAmount(String(detail.labour_amount ?? ''));
    setInvoiceRef(detail.repair_invoice_ref ?? '');
    setDescriptionAmount(detail.description_amount ?? '');
    setHandoverDate(detail.hand_over_date ?? '');
  }, [detail]);

  async function searchParts() {
    if (!partSearch.trim()) {
      onError('Enter a part or item search term.');
      return;
    }

    try {
      setPartItems(
        await api<any[]>(
          `/inventory/items/search?q=${encodeURIComponent(partSearch.trim())}`,
        ),
      );
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function addPart() {
    if (!partItemId) {
      onError('Select a part first.');
      return;
    }

    await onAction(`/repairs/${detail.repair_id}/part`, {
      item_id: partItemId,
      quantity: partQuantity,
      charge_amount: partCharge,
      notes: partNote.trim() || null,
    });

    setPartQuantity('1');
    setPartCharge('0');
    setPartNote('');
  }

  async function addPayment() {
    if (!paymentAmount || Number(paymentAmount) <= 0) {
      onError('Enter a valid repair payment amount.');
      return;
    }

    await onAction(`/repairs/${detail.repair_id}/payment`, {
      method: paymentMethod,
      amount: paymentAmount,
      reference: paymentReference.trim() || null,
      payment_type: 'RECEIPT',
      idempotency_key: paymentKey,
    });

    setPaymentAmount('');
    setPaymentReference('');
    setPaymentKey(crypto.randomUUID());
  }

  async function finalize() {
    if (!finalAmount || Number(finalAmount) < 0) {
      onError('Enter the final repair amount.');
      return;
    }

    await onAction(`/repairs/${detail.repair_id}/finalize`, {
      version: detail.version,
      final_amount: finalAmount,
      labour_amount: labourAmount || '0',
      repair_invoice_ref: invoiceRef.trim() || null,
      description_amount: descriptionAmount.trim() || null,
      hand_over_date: handoverDate || null,
    });
  }

  async function loadWarranty() {
    try {
      setWarranty(
        await api<any>(
          `/repairs/${encodeURIComponent(detail.repair_id)}/warranty`,
        ),
      );
    } catch (error) {
      onError((error as Error).message);
    }
  }

  return (
    <div className="detail-card">
      <div className="section-head">
        <div>
          <span className="eyebrow">REPAIR {detail.repair_no}</span>
          <h3>{detail.status}</h3>
          <p className="muted">
            Version {detail.version} · {detail.customer_name || 'Walk-in customer'} ·{' '}
            {detail.contact_no || 'No contact'}
          </p>
        </div>

        <button className="ghost" onClick={() => void onReload()}>
          Reload
        </button>
      </div>

      <div className="status-strip">
        <div>
          <span>Estimate</span>
          <b>Rs. {money(detail.estimated_amount)}</b>
        </div>
        <div>
          <span>Final</span>
          <b>Rs. {money(detail.final_amount)}</b>
        </div>
        <div>
          <span>Outstanding</span>
          <b>Rs. {money(detail.outstanding)}</b>
        </div>
      </div>

      <div className="info-grid">
        <div><span>Device</span><b>{[detail.device_brand, detail.model].filter(Boolean).join(' ') || '—'}</b></div>
        <div><span>Date In</span><b>{formatDateTime(detail.date_in)}</b></div>
        <div><span>Reported Fault</span><b>{detail.reported_fault || '—'}</b></div>
        <div><span>Accessories</span><b>{detail.given_accessories || '—'}</b></div>
        <div><span>Warranty Period</span><b>{detail.warranty_period || '—'}</b></div>
        <div><span>Special Note</span><b>{detail.special_note || '—'}</b></div>
      </div>

      <h4>Status workflow</h4>
      <div className="button-row">
        {(STATUS_FLOW[detail.status] ?? []).map((status) => (
          <button key={status} onClick={() => void onStatus(status)}>
            {status === 'WAITING FOR PART' ? 'Waiting for Part' : `Move to ${status}`}
          </button>
        ))}

        {detail.status === 'READY' && (
          <button onClick={() => void onDeliver()}>Deliver / Hand Over</button>
        )}

        {!['DELIVERED', 'CANCELLED'].includes(detail.status) && (
          <button className="danger-button" onClick={() => void onCancel()}>
            Cancel Repair
          </button>
        )}
      </div>

      <div className="section-divider" />

      <div className="section-head">
        <div>
          <h4>Parts used</h4>
          <p className="muted">
            Adding a part consumes FIFO stock. Removing a good part restores stock;
            damaged removals go through Admin damage review.
          </p>
        </div>
      </div>

      <div className="form-grid compact">
        <input
          value={partSearch}
          onChange={(event) => setPartSearch(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') void searchParts();
          }}
          placeholder="Search part / barcode / item code"
        />
        <button onClick={() => void searchParts()}>Find Part</button>
        <select value={partItemId} onChange={(event) => setPartItemId(event.target.value)}>
          <option value="">Select part</option>
          {partItems.map((item) => (
            <option key={item.item_id} value={item.item_id}>
              {item.item_code} · {item.description} · Stock {item.stock ?? '—'}
            </option>
          ))}
        </select>
        <input
          type="number"
          min="0.001"
          step="0.001"
          value={partQuantity}
          onChange={(event) => setPartQuantity(event.target.value)}
          placeholder="Qty"
        />
        <input
          type="number"
          min="0"
          step="0.01"
          value={partCharge}
          onChange={(event) => setPartCharge(event.target.value)}
          placeholder="Customer charge"
        />
        <input
          value={partNote}
          onChange={(event) => setPartNote(event.target.value)}
          placeholder="Part note"
        />
        <button disabled={!partItemId} onClick={() => void addPart()}>
          Use Part
        </button>
      </div>

      <div className="list-stack">
        {detail.parts.length === 0 && <p className="muted">No parts used yet.</p>}
        {detail.parts.map((part) => (
          <div className="stock-row" key={part.id}>
            <span>
              <b>{part.item_id}</b> · Qty {part.quantity} · {part.status}
              {part.notes ? ` · ${part.notes}` : ''}
            </span>
            <span>
              <b>Rs. {money(part.charge_amount)}</b>{' '}
              <small>FIFO Rs. {money(part.fifo_cost)}</small>
            </span>
            <div className="button-row">
              {part.status === 'USED' && (
                <>
                  <button
                    onClick={() =>
                      void onAction(
                        `/repairs/${detail.repair_id}/part/${part.id}/remove`,
                        { condition: 'GOOD', reason: 'Part removed and returned in good condition' },
                      )
                    }
                  >
                    Return Good
                  </button>
                  <button
                    className="danger-button"
                    onClick={() =>
                      void onAction(
                        `/repairs/${detail.repair_id}/part/${part.id}/remove`,
                        { condition: 'DAMAGED', reason: 'Part damaged during repair' },
                      )
                    }
                  >
                    Mark Damaged
                  </button>
                </>
              )}

              {isAdmin && part.status === 'DAMAGED_REVIEW' && (
                <>
                  <button
                    onClick={() =>
                      void onAction(
                        `/repairs/${detail.repair_id}/part/${part.id}/damage-review`,
                        { approve: true, reject_reason: null },
                      )
                    }
                  >
                    Approve Damage/Loss
                  </button>
                  <button
                    onClick={() =>
                      void onAction(
                        `/repairs/${detail.repair_id}/part/${part.id}/damage-review`,
                        { approve: false, reject_reason: 'Damage review rejected; part remains used' },
                      )
                    }
                  >
                    Reject Damage Review
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="section-divider" />

      <h4>Final amount</h4>
      <div className="form-grid compact">
        <input
          type="number"
          min="0"
          step="0.01"
          value={finalAmount}
          onChange={(event) => setFinalAmount(event.target.value)}
          placeholder="Final repair amount"
        />
        <input
          type="number"
          min="0"
          step="0.01"
          value={labourAmount}
          onChange={(event) => setLabourAmount(event.target.value)}
          placeholder="Labour amount"
        />
        <input
          value={invoiceRef}
          onChange={(event) => setInvoiceRef(event.target.value)}
          placeholder="Repair invoice reference"
        />
        <input
          value={descriptionAmount}
          onChange={(event) => setDescriptionAmount(event.target.value)}
          placeholder="Description / amount note"
        />
        <input
          type="date"
          value={handoverDate}
          onChange={(event) => setHandoverDate(event.target.value)}
        />
        <button onClick={() => void finalize()}>Finalize Amount</button>
      </div>

      <div className="section-divider" />

      <h4>Payments</h4>
      <div className="list-stack">
        {detail.payments.length === 0 && <p className="muted">No repair payments yet.</p>}
        {detail.payments.map((payment) => (
          <div className="stock-row" key={payment.id}>
            <span>
              <b>{payment.method}</b> · {payment.payment_type} ·{' '}
              {payment.proof_no || 'No proof number'}
              {payment.reference ? ` · ${payment.reference}` : ''}
            </span>
            <span>Rs. {money(payment.amount)}</span>
            {payment.proof_no && (
              <button
                onClick={async () => {
                  try {
                    await api(`/documents/REPAIR_PAYMENT/${payment.id}/reprint`, {
                      method: 'POST',
                    });
                  } catch (error) {
                    onError((error as Error).message);
                  }
                }}
              >
                Reprint Proof
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="form-grid compact">
        <select value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)}>
          <option value="CASH">Cash</option>
          <option value="CARD">Card</option>
          <option value="ONLINE">Online</option>
        </select>
        <input
          type="number"
          min="0.01"
          step="0.01"
          value={paymentAmount}
          onChange={(event) => setPaymentAmount(event.target.value)}
          placeholder="Payment amount"
        />
        <input
          value={paymentReference}
          onChange={(event) => setPaymentReference(event.target.value)}
          placeholder="Reference"
        />
        <button onClick={() => void addPayment()}>Add Payment</button>
      </div>

      <div className="section-divider" />

      <div className="section-head">
        <div>
          <h4>Repair warranty</h4>
          <p className="muted">
            Warranty starts from the hand-over/finalization date when a valid repair warranty period exists.
          </p>
        </div>
        <button onClick={() => void loadWarranty()}>Check Warranty</button>
      </div>

      {warranty && (
        <div className="success-banner">
          <b>{warranty.status}</b> · {warranty.start_date} →{' '}
          {warranty.expiry_date || 'No expiry'} · {warranty.warranty_period}
        </div>
      )}
    </div>
  );
}

function formatDateTime(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
