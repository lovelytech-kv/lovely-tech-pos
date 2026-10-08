import { useMemo, useState } from 'react';
import { api } from '../../api/client';
import { money, moneyPositive } from '../../services/money';

type Props = { isAdmin: boolean; onError: (message: string) => void };

type SaleLine = {
  sale_line_id: string;
  item_id: string;
  item_code: string;
  description: string;
  quantity: string | number;
  final_total: string | number;
  serialized_unit_id?: string | null;
};

type ReturnLineDraft = SaleLine & { return_qty: string; condition: 'GOOD' | 'DAMAGED' };

type Sale = {
  sale_id: string;
  invoice_no: string;
  grand_total: string | number;
  date?: string;
  lines: SaleLine[];
};

type ReturnInfo = {
  return_id: string;
  return_no: string;
  original_sale_id: string;
  refund_total: string | number;
  return_charge: string | number;
  status: string;
  reason?: string | null;
  paid_total: string | number;
  remaining_refund: string | number;
  lines: Array<{
    return_line_id: string;
    item_id: string;
    item_code: string;
    description: string;
    quantity: string | number;
    refund_amount: string | number;
    condition: string;
  }>;
};

type RefundPayment = {
  payment_id: string;
  payment_method: string;
  amount: string | number;
  payment_datetime: string;
  reference?: string | null;
};

export function ReturnsWorkspace({ isAdmin, onError }: Props) {
  const [saleQuery, setSaleQuery] = useState('');
  const [sale, setSale] = useState<Sale | null>(null);
  const [lines, setLines] = useState<ReturnLineDraft[]>([]);
  const [returnCharge, setReturnCharge] = useState('0.00');
  const [reason, setReason] = useState('');
  const [returnId, setReturnId] = useState('');
  const [returnInfo, setReturnInfo] = useState<ReturnInfo | null>(null);
  const [refunds, setRefunds] = useState<RefundPayment[]>([]);
  const [refundMethod, setRefundMethod] = useState('CASH');
  const [refundAmount, setRefundAmount] = useState('');
  const [refundReference, setRefundReference] = useState('');
  const [replacementSaleId, setReplacementSaleId] = useState('');
  const [lastResult, setLastResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [refundKey, setRefundKey] = useState(() => crypto.randomUUID());

  const selectedTotal = useMemo(
    () => lines.reduce((sum, line) => {
      if (!moneyPositive(line.return_qty)) return sum;
      const ratio = Number(line.return_qty) / Math.max(Number(line.quantity), 1);
      const lineTotal = Number(line.final_total) * ratio;
      return sum + lineTotal;
    }, 0),
    [lines],
  );

  async function findSale() {
    const query = saleQuery.trim();
    if (!query) {
      onError('Enter the completed sale ID or invoice number.');
      return;
    }
    try {
      const result = await api<Sale>(`/sales/${encodeURIComponent(query)}`);
      setSale(result);
      setLines((result.lines || []).map((line) => ({ ...line, return_qty: '0', condition: 'GOOD' })));
      setLastResult(null);
    } catch (error) {
      onError((error as Error).message);
    }
  }

  function updateLine(lineId: string, patch: Partial<ReturnLineDraft>) {
    setLines((current) => current.map((line) => line.sale_line_id === lineId ? { ...line, ...patch } : line));
  }

  async function completeReturn() {
    if (busy || !sale) return;
    const selected = lines.filter((line) => moneyPositive(line.return_qty));
    if (!selected.length) {
      onError('Select at least one item and enter a return quantity.');
      return;
    }
    const invalid = selected.find((line) => Number(line.return_qty) > Number(line.quantity));
    if (invalid) {
      onError(`Return quantity cannot exceed sold quantity for ${invalid.item_code}.`);
      return;
    }
    if (!reason.trim()) {
      onError('A return reason is required.');
      return;
    }

    try {
      setBusy(true);
      const result = await api<any>('/returns', {
        method: 'POST',
        body: JSON.stringify({
          original_sale_id: sale.sale_id,
          lines: selected.map((line) => ({
            sale_line_id: line.sale_line_id,
            quantity: String(line.return_qty),
            condition: line.condition,
            serialized_unit_id: line.serialized_unit_id || null,
            warranty_type: null,
            warranty_duration_value: null,
            warranty_custom_rule: null,
          })),
          return_charge: String(returnCharge || '0'),
          reason: reason.trim(),
          admin_override: isAdmin,
        }),
      });
      setLastResult(result);
      setReturnId(result.return_id);
      setLines((current) => current.map((line) => ({ ...line, return_qty: '0' })));
      await loadReturn(result.return_id);
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function loadReturn(id = returnId) {
    const normalized = id.trim();
    if (!normalized) {
      onError('Enter a return ID.');
      return;
    }
    try {
      const [info, payments] = await Promise.all([
        api<ReturnInfo>(`/returns/${encodeURIComponent(normalized)}`),
        api<RefundPayment[]>(`/returns/${encodeURIComponent(normalized)}/refund-payments`),
      ]);
      setReturnId(info.return_id);
      setReturnInfo(info);
      setRefunds(payments);
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function recordRefund() {
    if (!returnInfo) {
      onError('Load a return before recording a refund.');
      return;
    }
    if (!moneyPositive(refundAmount)) {
      onError('Enter a valid refund amount.');
      return;
    }
    if (Number(refundAmount) > Number(returnInfo.remaining_refund)) {
      onError('Refund amount cannot exceed the remaining refund.');
      return;
    }
    try {
      const result = await api<any>(`/returns/${encodeURIComponent(returnInfo.return_id)}/refund-payment`, {
        method: 'POST',
        body: JSON.stringify({
          idempotency_key: refundKey,
          payment_method: refundMethod,
          amount: refundAmount,
          reference: refundReference.trim() || null,
        }),
      });
      setLastResult(result);
      setRefundAmount('');
      setRefundReference('');
      setRefundKey(crypto.randomUUID());
      await loadReturn(returnInfo.return_id);
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function completeExchange() {
    if (!returnInfo) {
      onError('Load the completed return first.');
      return;
    }
    if (!replacementSaleId.trim()) {
      onError('Create the replacement sale in Sales first, then enter its sale ID here.');
      return;
    }
    try {
      const result = await api<any>('/returns/exchange', {
        method: 'POST',
        body: JSON.stringify({
          return_id: returnInfo.return_id,
          replacement_sale_id: replacementSaleId.trim(),
        }),
      });
      setLastResult(result);
      setReplacementSaleId('');
      await loadReturn(returnInfo.return_id);
    } catch (error) {
      onError((error as Error).message);
    }
  }

  return (
    <section className="workspace">
      <div className="split">
        <div className="glass panel">
          <div className="section-head">
            <div>
              <span className="eyebrow">AFTER-SALES</span>
              <h2>Return / Exchange</h2>
              <p className="muted">Find the original sale, select returned quantities, complete the return, then process refund or exchange.</p>
            </div>
            <button className="ghost" onClick={() => { setSale(null); setLines([]); setLastResult(null); }}>Reset</button>
          </div>

          <div className="search-row">
            <input
              value={saleQuery}
              onChange={(event) => setSaleQuery(event.target.value)}
              onKeyDown={(event) => { if (event.key === 'Enter') void findSale(); }}
              placeholder="Completed sale ID / invoice number"
            />
            <button onClick={() => void findSale()}>Find Sale</button>
          </div>

          {sale && (
            <>
              <div className="success-banner">
                <b>{sale.invoice_no}</b> · Sale ID {sale.sale_id} · Rs. {money(sale.grand_total)}
              </div>

              <div className="list-stack">
                {lines.map((line) => (
                  <div className="claim-row" key={line.sale_line_id}>
                    <div>
                      <b>{line.item_code} · {line.description}</b>
                      <small>Sold {line.quantity} · Line total Rs. {money(line.final_total)}</small>
                    </div>
                    <input
                      className="qty-input"
                      type="number"
                      min="0"
                      max={line.quantity}
                      step="0.001"
                      value={line.return_qty}
                      onChange={(event) => updateLine(line.sale_line_id, { return_qty: event.target.value })}
                      aria-label={`Return quantity for ${line.item_code}`}
                    />
                    <select value={line.condition} onChange={(event) => updateLine(line.sale_line_id, { condition: event.target.value as 'GOOD' | 'DAMAGED' })}>
                      <option value="GOOD">Good</option>
                      <option value="DAMAGED">Damaged</option>
                    </select>
                  </div>
                ))}
              </div>

              <div className="status-strip">
                <div><span>Selected refund estimate</span><b>Rs. {selectedTotal.toFixed(2)}</b></div>
                <div><span>Admin override</span><b>{isAdmin ? 'Available' : 'Not available'}</b></div>
              </div>

              <div className="form-grid compact">
                <input type="number" min="0" step="0.01" value={returnCharge} onChange={(event) => setReturnCharge(event.target.value)} placeholder="Return charge" />
                <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Required return reason" />
              </div>
              <button disabled={busy} onClick={() => void completeReturn()}>{busy ? 'Processing return…' : 'Complete Return'}</button>
            </>
          )}

          {!sale && <div className="empty-state"><b>Start with the original sale</b><span>Use the sale ID or invoice number printed on the customer document.</span></div>}
        </div>

        <div className="glass panel">
          <div className="section-head">
            <div>
              <span className="eyebrow">REFUND</span>
              <h2>Refund payment</h2>
              <p className="muted">Refund payments are idempotent so a retry cannot create a duplicate payment.</p>
            </div>
          </div>
          <div className="search-row">
            <input value={returnId} onChange={(event) => setReturnId(event.target.value)} placeholder="Return ID" />
            <button onClick={() => void loadReturn()}>Load Return</button>
          </div>

          {returnInfo ? (
            <>
              <div className="day-card">
                <span>Return</span><b>{returnInfo.return_no}</b>
                <span>Status</span><b>{returnInfo.status}</b>
                <span>Refund total</span><b>Rs. {money(returnInfo.refund_total)}</b>
                <span>Paid</span><b>Rs. {money(returnInfo.paid_total)}</b>
                <span>Remaining</span><b>Rs. {money(returnInfo.remaining_refund)}</b>
              </div>
              <div className="payment-grid">
                <select value={refundMethod} onChange={(event) => setRefundMethod(event.target.value)}>
                  <option value="CASH">Cash</option>
                  <option value="CARD">Card</option>
                  <option value="ONLINE">Online</option>
                </select>
                <input type="number" min="0.01" step="0.01" value={refundAmount} onChange={(event) => setRefundAmount(event.target.value)} placeholder="Refund amount" />
                <input value={refundReference} onChange={(event) => setRefundReference(event.target.value)} placeholder="Reference (optional)" />
              </div>
              <button disabled={!moneyPositive(refundAmount) || Number(refundAmount) > Number(returnInfo.remaining_refund)} onClick={() => void recordRefund()}>Record Refund Payment</button>
              <div className="list-stack">
                {refunds.map((payment) => (
                  <div className="stock-row" key={payment.payment_id}>
                    <span>{payment.payment_method} · {new Date(payment.payment_datetime).toLocaleString()}{payment.reference ? ` · ${payment.reference}` : ''}</span>
                    <b>Rs. {money(payment.amount)}</b>
                  </div>
                ))}
              </div>
            </>
          ) : <div className="empty-state"><span>Load a completed return to see refund status and payment history.</span></div>}
        </div>
      </div>

      <div className="glass panel">
        <div className="section-head">
          <div>
            <span className="eyebrow">EXCHANGE</span>
            <h2>Link replacement sale</h2>
            <p className="muted">Create the replacement sale in Sales first. Then link it to this completed return so the exchange difference is recorded by the backend.</p>
          </div>
        </div>
        <div className="form-grid compact">
          <input value={returnId} onChange={(event) => setReturnId(event.target.value)} placeholder="Completed return ID" />
          <input value={replacementSaleId} onChange={(event) => setReplacementSaleId(event.target.value)} placeholder="Replacement sale ID" />
          <button disabled={!returnId || !replacementSaleId.trim()} onClick={() => void completeExchange()}>Complete Exchange</button>
        </div>
        {lastResult?.exchange_no && <div className="success-banner">Exchange {lastResult.exchange_no} completed · Difference Rs. {money(lastResult.difference_amount)}</div>}
        {lastResult?.return_no && <div className="success-banner">Return {lastResult.return_no} completed · Refund Rs. {money(lastResult.refund_total)}</div>}
      </div>
    </section>
  );
}
