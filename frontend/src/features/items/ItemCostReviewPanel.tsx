import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { money } from '../../services/money';
import { moneyInputProps } from '../../utils/numberInput';
import { toast } from '../../ui/toast';

type PendingReviewItem = {
  item_id: string;
  item_code: string;
  description: string;
  category_name: string | null;
  created_by: string | null;
  created_at: string;
  buy_cost: string | number | null;
  low_stock_threshold: number;
};

function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString();
}

export function ItemCostReviewPanel({ onError }: { onError: (message: string) => void }) {
  const [rows, setRows] = useState<PendingReviewItem[]>([]);
  const [costs, setCosts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');

  async function load() {
    setLoading(true);
    try {
      setRows(await api<PendingReviewItem[]>('/items/pending-review'));
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function saveCost(row: PendingReviewItem) {
    if (busy) return;
    const value = (costs[row.item_id] || '').trim();
    if (value === '' || !Number.isFinite(Number(value)) || Number(value) < 0) {
      onError('Enter a valid buy cost (0 or more).');
      return;
    }
    setBusy(row.item_id);
    try {
      await api(`/items/${row.item_id}/review`, {
        method: 'PATCH',
        body: JSON.stringify({ buy_cost: value }),
      });
      setRows(prev => prev.filter(item => item.item_id !== row.item_id));
      setCosts(prev => { const next = { ...prev }; delete next[row.item_id]; return next; });
      toast.success(`Buy cost saved for ${row.item_code}.`);
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  return (
    <div className="glass panel" id="item-cost-review-queue">
      <div className="section-head">
        <div>
          <span className="eyebrow">ADMIN REVIEW</span>
          <h3>Item Cost Review Queue</h3>
          <p className="muted">Items with no known buy cost. Enter the buy cost to clear the review flag and enable profit reporting.</p>
          <p className="muted" style={{ fontSize: '0.78rem' }}>Purchase-line costs → Purchases History (Status: Pending cost).</p>
        </div>
        <button type="button" onClick={() => void load()} disabled={loading}>{loading ? 'Loading…' : 'Refresh'}</button>
      </div>

      {!loading && rows.length === 0 && (
        <div className="empty-state purchase-empty">
          <b>Nothing to review</b>
          <span>No active item is missing a buy cost.</span>
        </div>
      )}

      {rows.length > 0 && (
        <div className="purchase-table-wrap">
          <table className="purchase-line-table">
            <thead>
              <tr>
                <th>Item</th>
                <th>Category</th>
                <th>Created by</th>
                <th>Created</th>
                <th>Buy cost</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.item_id}>
                  <td><b>{row.item_code}</b> · {row.description}</td>
                  <td>{row.category_name || '—'}</td>
                  <td>{row.created_by || '—'}</td>
                  <td>{formatDate(row.created_at)}</td>
                  <td>
                    <input
                      {...moneyInputProps(costs[row.item_id] || '', (value) => setCosts(prev => ({ ...prev, [row.item_id]: value })))}
                      placeholder={row.buy_cost == null ? 'No cost yet' : `Rs. ${money(row.buy_cost)}`}
                      aria-label={`Buy cost for ${row.item_code}`}
                      style={{ width: 120 }}
                    />
                  </td>
                  <td>
                    <button type="button" disabled={busy === row.item_id} onClick={() => void saveCost(row)}>
                      {busy === row.item_id ? 'Saving…' : 'Set Cost'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
