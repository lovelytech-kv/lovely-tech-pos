import { useState } from 'react';
import { api } from '../../api/client';

export type RepairFormValues = {
  device_brand: string;
  model: string;
  imei: string;
  customer_name: string;
  contact_no: string;
  given_accessories: string;
  reported_fault: string;
  special_note: string;
  estimated_amount: string;
  warranty_period: string;
  advance_payment: string;
  advance_method: 'CASH' | 'CARD' | 'ONLINE';
};

type Props = { onCreated?: (result: any) => void; onError?: (message: string) => void };

const initial: RepairFormValues = {
  device_brand: '', model: '', imei: '', customer_name: '', contact_no: '',
  given_accessories: '', reported_fault: '', special_note: '', estimated_amount: '',
  warranty_period: '', advance_payment: '', advance_method: 'CASH',
};

export function RepairForm({ onCreated, onError }: Props) {
  const [form, setForm] = useState<RepairFormValues>(initial);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [advanceKey, setAdvanceKey] = useState(() => crypto.randomUUID());
  const [pendingAdvance, setPendingAdvance] = useState<{ repair_id: string; repair_no: string; amount: string; method: RepairFormValues['advance_method'] } | null>(null);
  const set = (key: keyof RepairFormValues, value: string) => setForm(prev => ({ ...prev, [key]: value }));

  async function submit() {
    if (busy) return;
    if (!form.device_brand.trim() && !form.model.trim()) return onError?.('Enter the device brand or model.');
    if (!form.reported_fault.trim()) return onError?.('Reported Fault is required.');
    const advance = pendingAdvance ? Number(pendingAdvance.amount) : Number(form.advance_payment || 0);
    if (!Number.isFinite(advance) || advance < 0) return onError?.('Advance payment must be zero or a valid amount.');
    if (advance > 0 && advanceKey.length < 8) setAdvanceKey(crypto.randomUUID());
    setBusy(true);
    try {
      let created: { repair_id: string; repair_no: string } | null = pendingAdvance;
      if (!created) {
        // The locked backend has no structured repair IMEI field. Preserve it in the
        // repair's audited Special Note rather than silently losing it.
        const noteParts = [
          form.imei.trim() ? `IMEI/Serial: ${form.imei.trim()}` : '',
          form.special_note.trim(),
        ].filter(Boolean);
        const createdRepair = await api('/operations/repairs', {
          method: 'POST',
          body: JSON.stringify({
            device_brand: form.device_brand.trim() || null,
            model: form.model.trim() || null,
            customer_name: form.customer_name.trim() || null,
            contact_no: form.contact_no.trim() || null,
            given_accessories: form.given_accessories.trim() || null,
            reported_fault: form.reported_fault.trim(),
            special_note: noteParts.join('\n') || null,
            estimated_amount: form.estimated_amount || null,
            warranty_period: form.warranty_period.trim() || null,
          }),
        });
        created = { repair_id: createdRepair.repair_id, repair_no: createdRepair.repair_no };
        if (advance > 0) setPendingAdvance({ ...created, amount: form.advance_payment, method: form.advance_method });
      }

      let advanceResult: any = null;
      if (advance > 0 && created) {
        const paymentAmount = pendingAdvance?.amount ?? form.advance_payment;
        const paymentMethod = pendingAdvance?.method ?? form.advance_method;
        advanceResult = await api(`/operations/repairs/${created.repair_id}/payment`, {
          method: 'POST',
          body: JSON.stringify({
            method: paymentMethod,
            amount: paymentAmount,
            payment_type: 'RECEIPT',
            idempotency_key: advanceKey,
          }),
        });
      }
      setResult({ ...created, imei: form.imei.trim(), advance_payment: pendingAdvance?.amount ?? form.advance_payment, advance_proof_no: advanceResult?.proof_no });
      setPendingAdvance(null);
      setForm(initial);
      setAdvanceKey(crypto.randomUUID());
      onCreated?.(created);
    } catch (e) {
      onError?.((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="glass panel repair-form-card">
      <div className="section-head">
        <div><h2>{pendingAdvance ? 'Complete Repair Advance Payment' : 'New Repair Job'}</h2><p className="muted">{pendingAdvance ? `Repair ${pendingAdvance.repair_no} was created. Retry the advance payment safely without creating another repair.` : 'Record the complete intake information before accepting the device.'}</p></div>
      </div>
      <div className="form-grid repair-form-grid" aria-disabled={Boolean(pendingAdvance)}>
        <label>Device Brand<input disabled={Boolean(pendingAdvance)} value={form.device_brand} onChange={e => set('device_brand', e.target.value)} placeholder="Samsung" /></label>
        <label>Model<input disabled={Boolean(pendingAdvance)} value={form.model} onChange={e => set('model', e.target.value)} placeholder="A12" /></label>
        <label>IMEI / Serial<input disabled={Boolean(pendingAdvance)} value={form.imei} onChange={e => set('imei', e.target.value)} placeholder="IMEI / serial" /></label>
        <label>Customer Name<input disabled={Boolean(pendingAdvance)} value={form.customer_name} onChange={e => set('customer_name', e.target.value)} placeholder="Optional" /></label>
        <label>Contact No.<input disabled={Boolean(pendingAdvance)} value={form.contact_no} onChange={e => set('contact_no', e.target.value)} placeholder="Optional" /></label>
        <label className="span-2">Given Accessories<input disabled={Boolean(pendingAdvance)} value={form.given_accessories} onChange={e => set('given_accessories', e.target.value)} placeholder="Charger, SIM tray..." /></label>
        <label>Estimate (Rs)<input disabled={Boolean(pendingAdvance)} type="number" min="0" step="0.01" value={form.estimated_amount} onChange={e => set('estimated_amount', e.target.value)} /></label>
        <label>Warranty Period<input disabled={Boolean(pendingAdvance)} value={form.warranty_period} onChange={e => set('warranty_period', e.target.value)} placeholder="e.g. 30 DAYS" /></label>
        <label className="span-2">Reported Fault<textarea disabled={Boolean(pendingAdvance)} value={form.reported_fault} onChange={e => set('reported_fault', e.target.value)} placeholder="Customer reported fault" /></label>
        <label>Advance Payment (Rs)<input disabled={Boolean(pendingAdvance)} type="number" min="0" step="0.01" value={pendingAdvance?.amount ?? form.advance_payment} onChange={e => set('advance_payment', e.target.value)} /></label>
        <label>Advance Method<select disabled={Boolean(pendingAdvance)} value={pendingAdvance?.method ?? form.advance_method} onChange={e => set('advance_method', e.target.value as RepairFormValues['advance_method'])}><option value="CASH">Cash</option><option value="CARD">Card</option><option value="ONLINE">Online</option></select></label>
        <label className="span-3">Special Note<textarea disabled={Boolean(pendingAdvance)} value={form.special_note} onChange={e => set('special_note', e.target.value)} placeholder="Special instructions / notes" /></label>
      </div>
      <div className="form-actions"><button disabled={busy} onClick={submit}>{busy ? 'Processing…' : pendingAdvance ? 'Retry Advance Payment' : 'Create Repair Job'}</button><button className="ghost" disabled={busy} onClick={() => { if (!pendingAdvance) { setForm(initial); setResult(null); } }}>Clear</button></div>
      {result && <div className="success-banner">Repair created: <b>{result.repair_no}</b>{result.advance_payment ? ` · Advance Rs. ${result.advance_payment} · ${result.advance_proof_no || 'Payment recorded'}` : ''}</div>}
    </section>
  );
}
