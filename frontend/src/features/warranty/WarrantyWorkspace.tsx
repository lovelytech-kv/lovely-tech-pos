import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { money } from '../../services/money';

type Props = { isAdmin: boolean; onError: (message: string) => void };

type Claim = {
  claim_id: string;
  claim_no: string;
  version: number;
  item_id: string;
  quantity: string | number;
  admin_decision: string;
  replacement_outcome?: string | null;
  notes?: string | null;
};

type WarrantyLookup = {
  warranty_id: string;
  warranty_no: string;
  start_date: string;
  expiry_date?: string | null;
  warranty_type: string;
  duration_value?: number | null;
  custom_rule?: string | null;
  status: string;
  serial_number?: string;
  item_code?: string;
  description?: string;
};

export function WarrantyWorkspace({ isAdmin, onError }: Props) {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [itemQuery, setItemQuery] = useState('');
  const [items, setItems] = useState<any[]>([]);
  const [itemId, setItemId] = useState('');
  const [claimQuantity, setClaimQuantity] = useState('1');
  const [warrantyId, setWarrantyId] = useState('');
  const [claimNotes, setClaimNotes] = useState('');
  const [serial, setSerial] = useState('');
  const [warrantyNo, setWarrantyNo] = useState('');
  const [lookup, setLookup] = useState<WarrantyLookup | null>(null);
  const [startDate, setStartDate] = useState(today());
  const [warrantyType, setWarrantyType] = useState('DAYS');
  const [duration, setDuration] = useState('30');
  const [customRule, setCustomRule] = useState('');
  const [calculation, setCalculation] = useState<any>(null);
  const [manualReference, setManualReference] = useState('');
  const [manualStart, setManualStart] = useState(today());
  const [manualExpiry, setManualExpiry] = useState('');
  const [manualDescription, setManualDescription] = useState('');
  const [manualCustomer, setManualCustomer] = useState('');
  const [manualNotes, setManualNotes] = useState('');
  const [outcomeQuantity, setOutcomeQuantity] = useState<Record<string, string>>({});

  async function loadClaims() {
    try {
      setClaims(await api<Claim[]>('/warranty/claims'));
    } catch (error) {
      onError((error as Error).message);
    }
  }

  useEffect(() => { void loadClaims(); }, []);

  async function searchItems() {
    try {
      setItems(await api<any[]>(`/inventory/items/search?q=${encodeURIComponent(itemQuery.trim())}`));
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function calculate() {
    try {
      const params = new URLSearchParams({ start_date: startDate, warranty_type: warrantyType });
      if (warrantyType === 'DAYS' || warrantyType === 'MONTHS') params.set('duration_value', duration);
      if (warrantyType === 'CUSTOM') params.set('custom_rule', customRule);
      setCalculation(await api(`/warranty/calculator?${params.toString()}`));
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function lookupSerial() {
    if (!serial.trim()) {
      onError('Enter a serial number or IMEI.');
      return;
    }
    try {
      setLookup(await api<WarrantyLookup>(`/warranty/serial-lookup?serial_number=${encodeURIComponent(serial.trim())}`));
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function lookupWarranty() {
    if (!warrantyNo.trim()) {
      onError('Enter a warranty number.');
      return;
    }
    try {
      setLookup(await api<WarrantyLookup>(`/warranty/lookup?warranty_no=${encodeURIComponent(warrantyNo.trim())}`));
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function createClaim() {
    if (!itemId) {
      onError('Select the item for the warranty claim.');
      return;
    }
    if (!Number(claimQuantity) || Number(claimQuantity) <= 0) {
      onError('Claim quantity must be greater than zero.');
      return;
    }
    try {
      await api('/warranty/claims', {
        method: 'POST',
        body: JSON.stringify({
          item_id: itemId,
          quantity: claimQuantity,
          product_warranty_id: warrantyId.trim() || null,
          notes: claimNotes.trim() || null,
        }),
      });
      setClaimNotes('');
      setWarrantyId('');
      setClaimQuantity('1');
      await loadClaims();
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function decision(claim: Claim, path: string, body: Record<string, unknown>) {
    try {
      await api(`/warranty/claims/${encodeURIComponent(claim.claim_id)}/${path}`, {
        method: 'POST',
        body: JSON.stringify({ version: claim.version, ...body }),
      });
      await loadClaims();
    } catch (error) {
      onError((error as Error).message);
    }
  }

  async function manualRegister() {
    if (!manualReference.trim() || !manualDescription.trim()) {
      onError('Manual warranty reference and item description are required.');
      return;
    }
    try {
      await api('/warranty/manual-registration', {
        method: 'POST',
        body: JSON.stringify({
          reference_no: manualReference.trim(),
          customer_name: manualCustomer.trim() || null,
          item_description: manualDescription.trim(),
          notes: manualNotes.trim() || null,
          start_date: manualStart,
          expiry_date: manualExpiry || null,
          warranty_type: manualExpiry ? 'CUSTOM' : 'CHECKING ONLY',
        }),
      });
      setManualReference('');
      setManualCustomer('');
      setManualDescription('');
      setManualNotes('');
      setManualExpiry('');
      setManualStart(today());
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
              <span className="eyebrow">WARRANTY</span>
              <h2>Warranty lookup</h2>
              <p className="muted">Search a warranty number or serial/IMEI and show the exact stored warranty dates and status.</p>
            </div>
          </div>
          <div className="search-row">
            <input value={serial} onChange={(event) => setSerial(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void lookupSerial(); }} placeholder="Serial / IMEI" />
            <button onClick={() => void lookupSerial()}>Search Serial</button>
          </div>
          <div className="search-row">
            <input value={warrantyNo} onChange={(event) => setWarrantyNo(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void lookupWarranty(); }} placeholder="Warranty number" />
            <button onClick={() => void lookupWarranty()}>Search Warranty</button>
          </div>
          {lookup && (
            <div className="day-card">
              <span>Warranty</span><b>{lookup.warranty_no}</b>
              <span>Item</span><b>{lookup.item_code || '—'} {lookup.description ? `· ${lookup.description}` : ''}</b>
              <span>Serial</span><b>{lookup.serial_number || '—'}</b>
              <span>Type</span><b>{lookup.warranty_type}</b>
              <span>Start</span><b>{lookup.start_date}</b>
              <span>Expiry</span><b>{lookup.expiry_date || '—'}</b>
              <span>Status</span><b>{lookup.status}</b>
            </div>
          )}
        </div>

        <div className="glass panel">
          <div className="section-head">
            <div>
              <span className="eyebrow">WARRANTY RULES</span>
              <h2>Expiry calculator</h2>
              <p className="muted">Use the same calendar warranty calculation as the backend before recording an exception.</p>
            </div>
          </div>
          <div className="form-grid compact">
            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            <select value={warrantyType} onChange={(event) => setWarrantyType(event.target.value)}>
              <option value="NONE">NONE</option>
              <option value="DAYS">DAYS</option>
              <option value="MONTHS">MONTHS</option>
              <option value="CHECKING ONLY">CHECKING ONLY</option>
              <option value="CUSTOM">CUSTOM</option>
            </select>
            {(warrantyType === 'DAYS' || warrantyType === 'MONTHS') && <input type="number" min="1" value={duration} onChange={(event) => setDuration(event.target.value)} placeholder="Duration" />}
            {warrantyType === 'CUSTOM' && <input value={customRule} onChange={(event) => setCustomRule(event.target.value)} placeholder="Custom rule, e.g. 45 DAYS" />}
            <button onClick={() => void calculate()}>Calculate</button>
          </div>
          {calculation && <div className="success-banner">{calculation.status} · {calculation.start_date} → {calculation.expiry_date || 'No expiry'}</div>}
        </div>
      </div>

      <div className="glass panel">
        <div className="section-head">
          <div>
            <span className="eyebrow">WARRANTY CLAIMS</span>
            <h2>Create and manage claims</h2>
            <p className="muted">Claims hold the reported quantity. Admin decisions are version-protected, so a stale screen cannot approve the same claim twice.</p>
          </div>
          <button className="ghost" onClick={() => void loadClaims()}>Refresh</button>
        </div>
        <div className="form-grid compact">
          <input value={itemQuery} onChange={(event) => setItemQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void searchItems(); }} placeholder="Item code / barcode / description" />
          <button onClick={() => void searchItems()}>Find Item</button>
          <select value={itemId} onChange={(event) => setItemId(event.target.value)}>
            <option value="">Select item</option>
            {items.map((item) => <option key={item.item_id} value={item.item_id}>{item.item_code} · {item.description}</option>)}
          </select>
          <input type="number" min="0.001" step="0.001" value={claimQuantity} onChange={(event) => setClaimQuantity(event.target.value)} placeholder="Quantity" />
          <input value={warrantyId} onChange={(event) => setWarrantyId(event.target.value)} placeholder="Product warranty ID (optional)" />
          <input value={claimNotes} onChange={(event) => setClaimNotes(event.target.value)} placeholder="Reported issue / claim notes" />
          <button disabled={!itemId} onClick={() => void createClaim()}>Create Warranty Claim</button>
        </div>

        <div className="list-stack">
          {claims.length === 0 && <div className="empty-state"><span>No warranty claims found.</span></div>}
          {claims.map((claim) => (
            <div className="claim-row" key={claim.claim_id}>
              <div>
                <b>{claim.claim_no}</b>
                <small>Qty {claim.quantity} · Version {claim.version}{claim.notes ? ` · ${claim.notes}` : ''}</small>
              </div>
              <span className="status-pill">{claim.admin_decision}</span>
              {claim.replacement_outcome && <span className="status-pill">{claim.replacement_outcome}</span>}
              {isAdmin && claim.admin_decision === 'PENDING_ADMIN' && (
                <div className="button-row">
                  <button onClick={() => void decision(claim, 'supplier', { supplier_process: 'SUPPLIER_WARRANTY_CLAIM', notes: 'Approved supplier warranty claim' })}>Supplier Claim</button>
                  <button className="danger-button" onClick={() => void decision(claim, 'damage', { notes: 'Approved as damage/loss' })}>Damage / Loss</button>
                </div>
              )}
              {isAdmin && claim.admin_decision === 'SUPPLIER_WARRANTY_CLAIM' && !claim.replacement_outcome && (
                <div className="button-row">
                  <input
                    type="number"
                    min="0.001"
                    step="0.001"
                    value={outcomeQuantity[claim.claim_id] ?? String(claim.quantity)}
                    onChange={(event) => setOutcomeQuantity((current) => ({ ...current, [claim.claim_id]: event.target.value }))}
                    aria-label={`Supplier outcome quantity for ${claim.claim_no}`}
                  />
                  <button onClick={() => void decision(claim, 'supplier-outcome', { outcome: 'REPLACEMENT', quantity: outcomeQuantity[claim.claim_id] ?? String(claim.quantity), notes: 'Replacement received from supplier' })}>Replacement Received</button>
                  <button className="danger-button" onClick={() => void decision(claim, 'supplier-outcome', { outcome: 'SHOP_HELD_DAMAGE', quantity: outcomeQuantity[claim.claim_id] ?? String(claim.quantity), notes: 'Supplier rejected; shop-held item damaged/lost' })}>Shop Damage</button>
                  <button onClick={() => void decision(claim, 'supplier-outcome', { outcome: 'CUSTOMER_KEEPS_ITEM', quantity: outcomeQuantity[claim.claim_id] ?? String(claim.quantity), notes: 'Customer keeps item' })}>Customer Keeps</button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {isAdmin && (
        <div className="glass panel">
          <div className="section-head">
            <div>
              <span className="eyebrow">ADMIN EXCEPTION</span>
              <h2>Manual warranty registration</h2>
              <p className="muted">For controlled manual-document exceptions only. Normal product warranties should originate from the sale transaction.</p>
            </div>
          </div>
          <div className="form-grid compact">
            <input value={manualReference} onChange={(event) => setManualReference(event.target.value)} placeholder="Manual reference number" />
            <input value={manualCustomer} onChange={(event) => setManualCustomer(event.target.value)} placeholder="Customer name (optional)" />
            <input value={manualDescription} onChange={(event) => setManualDescription(event.target.value)} placeholder="Item description" />
            <input type="date" value={manualStart} onChange={(event) => setManualStart(event.target.value)} />
            <input type="date" value={manualExpiry} onChange={(event) => setManualExpiry(event.target.value)} />
            <input value={manualNotes} onChange={(event) => setManualNotes(event.target.value)} placeholder="Exception notes" />
            <button onClick={() => void manualRegister()}>Register Manual Warranty</button>
          </div>
        </div>
      )}
    </section>
  );
}

function today() {
  return new Date().toISOString().slice(0, 10);
}
