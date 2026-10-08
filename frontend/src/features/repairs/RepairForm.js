import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { api } from '../../api/client';
const initial = {
    device_brand: '', model: '', imei: '', customer_name: '', contact_no: '',
    given_accessories: '', reported_fault: '', special_note: '', estimated_amount: '',
    warranty_period: '', advance_payment: '', advance_method: 'CASH',
};
export function RepairForm({ onCreated, onError }) {
    const [form, setForm] = useState(initial);
    const [busy, setBusy] = useState(false);
    const [result, setResult] = useState(null);
    const [advanceKey, setAdvanceKey] = useState(() => crypto.randomUUID());
    const [pendingAdvance, setPendingAdvance] = useState(null);
    const set = (key, value) => setForm(prev => ({ ...prev, [key]: value }));
    async function submit() {
        if (busy)
            return;
        if (!form.device_brand.trim() && !form.model.trim())
            return onError?.('Enter the device brand or model.');
        if (!form.reported_fault.trim())
            return onError?.('Reported Fault is required.');
        const advance = pendingAdvance ? Number(pendingAdvance.amount) : Number(form.advance_payment || 0);
        if (!Number.isFinite(advance) || advance < 0)
            return onError?.('Advance payment must be zero or a valid amount.');
        if (advance > 0 && advanceKey.length < 8)
            setAdvanceKey(crypto.randomUUID());
        setBusy(true);
        try {
            let created = pendingAdvance;
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
                if (advance > 0)
                    setPendingAdvance({ ...created, amount: form.advance_payment, method: form.advance_method });
            }
            let advanceResult = null;
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
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    return (_jsxs("section", { className: "glass panel repair-form-card", children: [_jsx("div", { className: "section-head", children: _jsxs("div", { children: [_jsx("h2", { children: pendingAdvance ? 'Complete Repair Advance Payment' : 'New Repair Job' }), _jsx("p", { className: "muted", children: pendingAdvance ? `Repair ${pendingAdvance.repair_no} was created. Retry the advance payment safely without creating another repair.` : 'Record the complete intake information before accepting the device.' })] }) }), _jsxs("div", { className: "form-grid repair-form-grid", "aria-disabled": Boolean(pendingAdvance), children: [_jsxs("label", { children: ["Device Brand", _jsx("input", { disabled: Boolean(pendingAdvance), value: form.device_brand, onChange: e => set('device_brand', e.target.value), placeholder: "Samsung" })] }), _jsxs("label", { children: ["Model", _jsx("input", { disabled: Boolean(pendingAdvance), value: form.model, onChange: e => set('model', e.target.value), placeholder: "A12" })] }), _jsxs("label", { children: ["IMEI / Serial", _jsx("input", { disabled: Boolean(pendingAdvance), value: form.imei, onChange: e => set('imei', e.target.value), placeholder: "IMEI / serial" })] }), _jsxs("label", { children: ["Customer Name", _jsx("input", { disabled: Boolean(pendingAdvance), value: form.customer_name, onChange: e => set('customer_name', e.target.value), placeholder: "Optional" })] }), _jsxs("label", { children: ["Contact No.", _jsx("input", { disabled: Boolean(pendingAdvance), value: form.contact_no, onChange: e => set('contact_no', e.target.value), placeholder: "Optional" })] }), _jsxs("label", { className: "span-2", children: ["Given Accessories", _jsx("input", { disabled: Boolean(pendingAdvance), value: form.given_accessories, onChange: e => set('given_accessories', e.target.value), placeholder: "Charger, SIM tray..." })] }), _jsxs("label", { children: ["Estimate (Rs)", _jsx("input", { disabled: Boolean(pendingAdvance), type: "number", min: "0", step: "0.01", value: form.estimated_amount, onChange: e => set('estimated_amount', e.target.value) })] }), _jsxs("label", { children: ["Warranty Period", _jsx("input", { disabled: Boolean(pendingAdvance), value: form.warranty_period, onChange: e => set('warranty_period', e.target.value), placeholder: "e.g. 30 DAYS" })] }), _jsxs("label", { className: "span-2", children: ["Reported Fault", _jsx("textarea", { disabled: Boolean(pendingAdvance), value: form.reported_fault, onChange: e => set('reported_fault', e.target.value), placeholder: "Customer reported fault" })] }), _jsxs("label", { children: ["Advance Payment (Rs)", _jsx("input", { disabled: Boolean(pendingAdvance), type: "number", min: "0", step: "0.01", value: pendingAdvance?.amount ?? form.advance_payment, onChange: e => set('advance_payment', e.target.value) })] }), _jsxs("label", { children: ["Advance Method", _jsxs("select", { disabled: Boolean(pendingAdvance), value: pendingAdvance?.method ?? form.advance_method, onChange: e => set('advance_method', e.target.value), children: [_jsx("option", { value: "CASH", children: "Cash" }), _jsx("option", { value: "CARD", children: "Card" }), _jsx("option", { value: "ONLINE", children: "Online" })] })] }), _jsxs("label", { className: "span-3", children: ["Special Note", _jsx("textarea", { disabled: Boolean(pendingAdvance), value: form.special_note, onChange: e => set('special_note', e.target.value), placeholder: "Special instructions / notes" })] })] }), _jsxs("div", { className: "form-actions", children: [_jsx("button", { disabled: busy, onClick: submit, children: busy ? 'Processing…' : pendingAdvance ? 'Retry Advance Payment' : 'Create Repair Job' }), _jsx("button", { className: "ghost", disabled: busy, onClick: () => { if (!pendingAdvance) {
                            setForm(initial);
                            setResult(null);
                        } }, children: "Clear" })] }), result && _jsxs("div", { className: "success-banner", children: ["Repair created: ", _jsx("b", { children: result.repair_no }), result.advance_payment ? ` · Advance Rs. ${result.advance_payment} · ${result.advance_proof_no || 'Payment recorded'}` : ''] })] }));
}
