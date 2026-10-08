import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useMemo, useState } from 'react';
import { api } from '../../api/client';
import { money, moneyPositive } from '../../services/money';
export function ReturnsWorkspace({ isAdmin, onError }) {
    const [saleQuery, setSaleQuery] = useState('');
    const [sale, setSale] = useState(null);
    const [lines, setLines] = useState([]);
    const [returnCharge, setReturnCharge] = useState('0.00');
    const [reason, setReason] = useState('');
    const [returnId, setReturnId] = useState('');
    const [returnInfo, setReturnInfo] = useState(null);
    const [refunds, setRefunds] = useState([]);
    const [refundMethod, setRefundMethod] = useState('CASH');
    const [refundAmount, setRefundAmount] = useState('');
    const [refundReference, setRefundReference] = useState('');
    const [replacementSaleId, setReplacementSaleId] = useState('');
    const [lastResult, setLastResult] = useState(null);
    const [busy, setBusy] = useState(false);
    const [refundKey, setRefundKey] = useState(() => crypto.randomUUID());
    const selectedTotal = useMemo(() => lines.reduce((sum, line) => {
        if (!moneyPositive(line.return_qty))
            return sum;
        const ratio = Number(line.return_qty) / Math.max(Number(line.quantity), 1);
        const lineTotal = Number(line.final_total) * ratio;
        return sum + lineTotal;
    }, 0), [lines]);
    async function findSale() {
        const query = saleQuery.trim();
        if (!query) {
            onError('Enter the completed sale ID or invoice number.');
            return;
        }
        try {
            const result = await api(`/sales/${encodeURIComponent(query)}`);
            setSale(result);
            setLines((result.lines || []).map((line) => ({ ...line, return_qty: '0', condition: 'GOOD' })));
            setLastResult(null);
        }
        catch (error) {
            onError(error.message);
        }
    }
    function updateLine(lineId, patch) {
        setLines((current) => current.map((line) => line.sale_line_id === lineId ? { ...line, ...patch } : line));
    }
    async function completeReturn() {
        if (busy || !sale)
            return;
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
            const result = await api('/returns', {
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
        }
        catch (error) {
            onError(error.message);
        }
        finally {
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
                api(`/returns/${encodeURIComponent(normalized)}`),
                api(`/returns/${encodeURIComponent(normalized)}/refund-payments`),
            ]);
            setReturnId(info.return_id);
            setReturnInfo(info);
            setRefunds(payments);
        }
        catch (error) {
            onError(error.message);
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
            const result = await api(`/returns/${encodeURIComponent(returnInfo.return_id)}/refund-payment`, {
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
        }
        catch (error) {
            onError(error.message);
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
            const result = await api('/returns/exchange', {
                method: 'POST',
                body: JSON.stringify({
                    return_id: returnInfo.return_id,
                    replacement_sale_id: replacementSaleId.trim(),
                }),
            });
            setLastResult(result);
            setReplacementSaleId('');
            await loadReturn(returnInfo.return_id);
        }
        catch (error) {
            onError(error.message);
        }
    }
    return (_jsxs("section", { className: "workspace", children: [_jsxs("div", { className: "split", children: [_jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "AFTER-SALES" }), _jsx("h2", { children: "Return / Exchange" }), _jsx("p", { className: "muted", children: "Find the original sale, select returned quantities, complete the return, then process refund or exchange." })] }), _jsx("button", { className: "ghost", onClick: () => { setSale(null); setLines([]); setLastResult(null); }, children: "Reset" })] }), _jsxs("div", { className: "search-row", children: [_jsx("input", { value: saleQuery, onChange: (event) => setSaleQuery(event.target.value), onKeyDown: (event) => { if (event.key === 'Enter')
                                            void findSale(); }, placeholder: "Completed sale ID / invoice number" }), _jsx("button", { onClick: () => void findSale(), children: "Find Sale" })] }), sale && (_jsxs(_Fragment, { children: [_jsxs("div", { className: "success-banner", children: [_jsx("b", { children: sale.invoice_no }), " \u00B7 Sale ID ", sale.sale_id, " \u00B7 Rs. ", money(sale.grand_total)] }), _jsx("div", { className: "list-stack", children: lines.map((line) => (_jsxs("div", { className: "claim-row", children: [_jsxs("div", { children: [_jsxs("b", { children: [line.item_code, " \u00B7 ", line.description] }), _jsxs("small", { children: ["Sold ", line.quantity, " \u00B7 Line total Rs. ", money(line.final_total)] })] }), _jsx("input", { className: "qty-input", type: "number", min: "0", max: line.quantity, step: "0.001", value: line.return_qty, onChange: (event) => updateLine(line.sale_line_id, { return_qty: event.target.value }), "aria-label": `Return quantity for ${line.item_code}` }), _jsxs("select", { value: line.condition, onChange: (event) => updateLine(line.sale_line_id, { condition: event.target.value }), children: [_jsx("option", { value: "GOOD", children: "Good" }), _jsx("option", { value: "DAMAGED", children: "Damaged" })] })] }, line.sale_line_id))) }), _jsxs("div", { className: "status-strip", children: [_jsxs("div", { children: [_jsx("span", { children: "Selected refund estimate" }), _jsxs("b", { children: ["Rs. ", selectedTotal.toFixed(2)] })] }), _jsxs("div", { children: [_jsx("span", { children: "Admin override" }), _jsx("b", { children: isAdmin ? 'Available' : 'Not available' })] })] }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { type: "number", min: "0", step: "0.01", value: returnCharge, onChange: (event) => setReturnCharge(event.target.value), placeholder: "Return charge" }), _jsx("input", { value: reason, onChange: (event) => setReason(event.target.value), placeholder: "Required return reason" })] }), _jsx("button", { disabled: busy, onClick: () => void completeReturn(), children: busy ? 'Processing return…' : 'Complete Return' })] })), !sale && _jsxs("div", { className: "empty-state", children: [_jsx("b", { children: "Start with the original sale" }), _jsx("span", { children: "Use the sale ID or invoice number printed on the customer document." })] })] }), _jsxs("div", { className: "glass panel", children: [_jsx("div", { className: "section-head", children: _jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "REFUND" }), _jsx("h2", { children: "Refund payment" }), _jsx("p", { className: "muted", children: "Refund payments are idempotent so a retry cannot create a duplicate payment." })] }) }), _jsxs("div", { className: "search-row", children: [_jsx("input", { value: returnId, onChange: (event) => setReturnId(event.target.value), placeholder: "Return ID" }), _jsx("button", { onClick: () => void loadReturn(), children: "Load Return" })] }), returnInfo ? (_jsxs(_Fragment, { children: [_jsxs("div", { className: "day-card", children: [_jsx("span", { children: "Return" }), _jsx("b", { children: returnInfo.return_no }), _jsx("span", { children: "Status" }), _jsx("b", { children: returnInfo.status }), _jsx("span", { children: "Refund total" }), _jsxs("b", { children: ["Rs. ", money(returnInfo.refund_total)] }), _jsx("span", { children: "Paid" }), _jsxs("b", { children: ["Rs. ", money(returnInfo.paid_total)] }), _jsx("span", { children: "Remaining" }), _jsxs("b", { children: ["Rs. ", money(returnInfo.remaining_refund)] })] }), _jsxs("div", { className: "payment-grid", children: [_jsxs("select", { value: refundMethod, onChange: (event) => setRefundMethod(event.target.value), children: [_jsx("option", { value: "CASH", children: "Cash" }), _jsx("option", { value: "CARD", children: "Card" }), _jsx("option", { value: "ONLINE", children: "Online" })] }), _jsx("input", { type: "number", min: "0.01", step: "0.01", value: refundAmount, onChange: (event) => setRefundAmount(event.target.value), placeholder: "Refund amount" }), _jsx("input", { value: refundReference, onChange: (event) => setRefundReference(event.target.value), placeholder: "Reference (optional)" })] }), _jsx("button", { disabled: !moneyPositive(refundAmount) || Number(refundAmount) > Number(returnInfo.remaining_refund), onClick: () => void recordRefund(), children: "Record Refund Payment" }), _jsx("div", { className: "list-stack", children: refunds.map((payment) => (_jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [payment.payment_method, " \u00B7 ", new Date(payment.payment_datetime).toLocaleString(), payment.reference ? ` · ${payment.reference}` : ''] }), _jsxs("b", { children: ["Rs. ", money(payment.amount)] })] }, payment.payment_id))) })] })) : _jsx("div", { className: "empty-state", children: _jsx("span", { children: "Load a completed return to see refund status and payment history." }) })] })] }), _jsxs("div", { className: "glass panel", children: [_jsx("div", { className: "section-head", children: _jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "EXCHANGE" }), _jsx("h2", { children: "Link replacement sale" }), _jsx("p", { className: "muted", children: "Create the replacement sale in Sales first. Then link it to this completed return so the exchange difference is recorded by the backend." })] }) }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { value: returnId, onChange: (event) => setReturnId(event.target.value), placeholder: "Completed return ID" }), _jsx("input", { value: replacementSaleId, onChange: (event) => setReplacementSaleId(event.target.value), placeholder: "Replacement sale ID" }), _jsx("button", { disabled: !returnId || !replacementSaleId.trim(), onClick: () => void completeExchange(), children: "Complete Exchange" })] }), lastResult?.exchange_no && _jsxs("div", { className: "success-banner", children: ["Exchange ", lastResult.exchange_no, " completed \u00B7 Difference Rs. ", money(lastResult.difference_amount)] }), lastResult?.return_no && _jsxs("div", { className: "success-banner", children: ["Return ", lastResult.return_no, " completed \u00B7 Refund Rs. ", money(lastResult.refund_total)] })] })] }));
}
