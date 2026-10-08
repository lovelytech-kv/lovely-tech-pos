import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { money } from '../../services/money';
const STATUS_FLOW = {
    RECEIVED: ['CHECKING'],
    CHECKING: ['REPAIRING', 'WAITING FOR PART'],
    'WAITING FOR PART': ['REPAIRING'],
    REPAIRING: ['READY'],
    READY: ['DELIVERED'],
};
export function RepairWorkspace({ isAdmin, onError }) {
    const [rows, setRows] = useState([]);
    const [selectedId, setSelectedId] = useState('');
    const [detail, setDetail] = useState(null);
    const [query, setQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('ALL');
    const [loading, setLoading] = useState(false);
    const visibleRows = useMemo(() => {
        const q = query.trim().toLowerCase();
        return rows.filter((row) => {
            const statusMatch = statusFilter === 'ALL' || row.status === statusFilter;
            if (!statusMatch)
                return false;
            if (!q)
                return true;
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
            const result = await api('/operations/repairs');
            setRows(result);
            if (keepSelection && selectedId) {
                const selected = result.find((row) => row.repair_id === selectedId);
                if (selected) {
                    await loadDetail(selected.repair_id, false);
                }
            }
        }
        catch (error) {
            onError(error.message);
        }
        finally {
            setLoading(false);
        }
    }
    async function loadDetail(repairId, updateSelection = true) {
        try {
            const result = await api(`/operations/repairs/${encodeURIComponent(repairId)}`);
            setDetail(result);
            if (updateSelection)
                setSelectedId(repairId);
        }
        catch (error) {
            onError(error.message);
        }
    }
    useEffect(() => {
        void loadRows(false);
    }, []);
    async function action(path, body, queryString = '') {
        try {
            await api(path + queryString, {
                method: 'POST',
                body: JSON.stringify(body ?? {}),
            });
            if (selectedId)
                await loadDetail(selectedId, false);
            await loadRows(true);
        }
        catch (error) {
            onError(error.message);
        }
    }
    async function changeStatus(nextStatus) {
        if (!detail)
            return;
        await action(`/operations/repairs/${detail.repair_id}/status`, {
            status: nextStatus,
            version: detail.version,
        });
    }
    async function deliver() {
        if (!detail)
            return;
        await action(`/operations/repairs/${detail.repair_id}/deliver`, {}, `?version=${encodeURIComponent(detail.version)}`);
    }
    async function cancel() {
        if (!detail)
            return;
        const reason = window.prompt('Cancellation reason')?.trim();
        if (!reason)
            return;
        await action(`/operations/repairs/${detail.repair_id}/cancel`, {
            version: detail.version,
            reason,
        });
    }
    return (_jsx("section", { className: "workspace", children: _jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "SERVICE DESK" }), _jsx("h2", { children: "Repair jobs" }), _jsx("p", { className: "muted", children: "Track intake, diagnosis, parts, payment, final amount, warranty and customer hand-over from one repair record." })] }), _jsx("button", { disabled: loading, onClick: () => void loadRows(), children: loading ? 'Refreshing…' : 'Refresh' })] }), _jsxs("div", { className: "search-row", children: [_jsx("input", { value: query, onChange: (event) => setQuery(event.target.value), placeholder: "Repair no / customer / device / contact" }), _jsxs("select", { value: statusFilter, onChange: (event) => setStatusFilter(event.target.value), children: [_jsx("option", { value: "ALL", children: "All statuses" }), _jsx("option", { value: "RECEIVED", children: "Received" }), _jsx("option", { value: "CHECKING", children: "Checking" }), _jsx("option", { value: "REPAIRING", children: "Repairing" }), _jsx("option", { value: "WAITING FOR PART", children: "Waiting for Part" }), _jsx("option", { value: "READY", children: "Ready" }), _jsx("option", { value: "DELIVERED", children: "Delivered" }), _jsx("option", { value: "CANCELLED", children: "Cancelled" })] })] }), _jsxs("div", { className: "split", children: [_jsxs("div", { className: "list-stack", children: [visibleRows.length === 0 && (_jsxs("div", { className: "empty-state", children: [_jsx("b", { children: "No repair jobs found" }), _jsx("span", { children: "Change the search/filter or create a new repair intake above." })] })), visibleRows.map((row) => (_jsxs("button", { className: `list-row ${selectedId === row.repair_id ? 'selected' : ''}`, onClick: () => void loadDetail(row.repair_id), children: [_jsx("b", { children: row.repair_no }), _jsx("span", { children: [row.device_brand, row.model].filter(Boolean).join(' ') || 'Device not specified' }), _jsxs("small", { children: [row.status, " \u00B7 ", row.customer_name || 'Walk-in', " \u00B7 Outstanding Rs.", ' ', money(row.outstanding)] })] }, row.repair_id)))] }), detail ? (_jsx(RepairDetailPanel, { detail: detail, isAdmin: isAdmin, onError: onError, onReload: () => loadDetail(detail.repair_id, false), onAction: action, onStatus: changeStatus, onDeliver: deliver, onCancel: cancel })) : (_jsxs("div", { className: "empty-state", children: [_jsx("b", { children: "Select a repair" }), _jsx("span", { children: "The complete job timeline, parts, payments and hand-over controls will appear here." })] }))] })] }) }));
}
function RepairDetailPanel({ detail, isAdmin, onError, onReload, onAction, onStatus, onDeliver, onCancel, }) {
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
    const [partItems, setPartItems] = useState([]);
    const [partItemId, setPartItemId] = useState('');
    const [partQuantity, setPartQuantity] = useState('1');
    const [partCharge, setPartCharge] = useState('0');
    const [partNote, setPartNote] = useState('');
    const [warranty, setWarranty] = useState(null);
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
            setPartItems(await api(`/inventory/items/search?q=${encodeURIComponent(partSearch.trim())}`));
        }
        catch (error) {
            onError(error.message);
        }
    }
    async function addPart() {
        if (!partItemId) {
            onError('Select a part first.');
            return;
        }
        await onAction(`/operations/repairs/${detail.repair_id}/part`, {
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
        await onAction(`/operations/repairs/${detail.repair_id}/payment`, {
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
        await onAction(`/operations/repairs/${detail.repair_id}/finalize`, {
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
            setWarranty(await api(`/operations/repairs/${encodeURIComponent(detail.repair_id)}/warranty`));
        }
        catch (error) {
            onError(error.message);
        }
    }
    return (_jsxs("div", { className: "detail-card", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsxs("span", { className: "eyebrow", children: ["REPAIR ", detail.repair_no] }), _jsx("h3", { children: detail.status }), _jsxs("p", { className: "muted", children: ["Version ", detail.version, " \u00B7 ", detail.customer_name || 'Walk-in customer', " \u00B7", ' ', detail.contact_no || 'No contact'] })] }), _jsx("button", { className: "ghost", onClick: () => void onReload(), children: "Reload" })] }), _jsxs("div", { className: "status-strip", children: [_jsxs("div", { children: [_jsx("span", { children: "Estimate" }), _jsxs("b", { children: ["Rs. ", money(detail.estimated_amount)] })] }), _jsxs("div", { children: [_jsx("span", { children: "Final" }), _jsxs("b", { children: ["Rs. ", money(detail.final_amount)] })] }), _jsxs("div", { children: [_jsx("span", { children: "Outstanding" }), _jsxs("b", { children: ["Rs. ", money(detail.outstanding)] })] })] }), _jsxs("div", { className: "info-grid", children: [_jsxs("div", { children: [_jsx("span", { children: "Device" }), _jsx("b", { children: [detail.device_brand, detail.model].filter(Boolean).join(' ') || '—' })] }), _jsxs("div", { children: [_jsx("span", { children: "Date In" }), _jsx("b", { children: formatDateTime(detail.date_in) })] }), _jsxs("div", { children: [_jsx("span", { children: "Reported Fault" }), _jsx("b", { children: detail.reported_fault || '—' })] }), _jsxs("div", { children: [_jsx("span", { children: "Accessories" }), _jsx("b", { children: detail.given_accessories || '—' })] }), _jsxs("div", { children: [_jsx("span", { children: "Warranty Period" }), _jsx("b", { children: detail.warranty_period || '—' })] }), _jsxs("div", { children: [_jsx("span", { children: "Special Note" }), _jsx("b", { children: detail.special_note || '—' })] })] }), _jsx("h4", { children: "Status workflow" }), _jsxs("div", { className: "button-row", children: [(STATUS_FLOW[detail.status] ?? []).map((status) => (_jsx("button", { onClick: () => void onStatus(status), children: status === 'WAITING FOR PART' ? 'Waiting for Part' : `Move to ${status}` }, status))), detail.status === 'READY' && (_jsx("button", { onClick: () => void onDeliver(), children: "Deliver / Hand Over" })), !['DELIVERED', 'CANCELLED'].includes(detail.status) && (_jsx("button", { className: "danger-button", onClick: () => void onCancel(), children: "Cancel Repair" }))] }), _jsx("div", { className: "section-divider" }), _jsx("div", { className: "section-head", children: _jsxs("div", { children: [_jsx("h4", { children: "Parts used" }), _jsx("p", { className: "muted", children: "Adding a part consumes FIFO stock. Removing a good part restores stock; damaged removals go through Admin damage review." })] }) }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { value: partSearch, onChange: (event) => setPartSearch(event.target.value), onKeyDown: (event) => {
                            if (event.key === 'Enter')
                                void searchParts();
                        }, placeholder: "Search part / barcode / item code" }), _jsx("button", { onClick: () => void searchParts(), children: "Find Part" }), _jsxs("select", { value: partItemId, onChange: (event) => setPartItemId(event.target.value), children: [_jsx("option", { value: "", children: "Select part" }), partItems.map((item) => (_jsxs("option", { value: item.item_id, children: [item.item_code, " \u00B7 ", item.description, " \u00B7 Stock ", item.stock ?? '—'] }, item.item_id)))] }), _jsx("input", { type: "number", min: "0.001", step: "0.001", value: partQuantity, onChange: (event) => setPartQuantity(event.target.value), placeholder: "Qty" }), _jsx("input", { type: "number", min: "0", step: "0.01", value: partCharge, onChange: (event) => setPartCharge(event.target.value), placeholder: "Customer charge" }), _jsx("input", { value: partNote, onChange: (event) => setPartNote(event.target.value), placeholder: "Part note" }), _jsx("button", { disabled: !partItemId, onClick: () => void addPart(), children: "Use Part" })] }), _jsxs("div", { className: "list-stack", children: [detail.parts.length === 0 && _jsx("p", { className: "muted", children: "No parts used yet." }), detail.parts.map((part) => (_jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [_jsx("b", { children: part.item_id }), " \u00B7 Qty ", part.quantity, " \u00B7 ", part.status, part.notes ? ` · ${part.notes}` : ''] }), _jsxs("span", { children: [_jsxs("b", { children: ["Rs. ", money(part.charge_amount)] }), ' ', _jsxs("small", { children: ["FIFO Rs. ", money(part.fifo_cost)] })] }), _jsxs("div", { className: "button-row", children: [part.status === 'USED' && (_jsxs(_Fragment, { children: [_jsx("button", { onClick: () => void onAction(`/operations/repairs/${detail.repair_id}/part/${part.id}/remove`, { condition: 'GOOD', reason: 'Part removed and returned in good condition' }), children: "Return Good" }), _jsx("button", { className: "danger-button", onClick: () => void onAction(`/operations/repairs/${detail.repair_id}/part/${part.id}/remove`, { condition: 'DAMAGED', reason: 'Part damaged during repair' }), children: "Mark Damaged" })] })), isAdmin && part.status === 'DAMAGED_REVIEW' && (_jsxs(_Fragment, { children: [_jsx("button", { onClick: () => void onAction(`/operations/repairs/${detail.repair_id}/part/${part.id}/damage-review`, { approve: true, reject_reason: null }), children: "Approve Damage/Loss" }), _jsx("button", { onClick: () => void onAction(`/operations/repairs/${detail.repair_id}/part/${part.id}/damage-review`, { approve: false, reject_reason: 'Damage review rejected; part remains used' }), children: "Reject Damage Review" })] }))] })] }, part.id)))] }), _jsx("div", { className: "section-divider" }), _jsx("h4", { children: "Final amount" }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { type: "number", min: "0", step: "0.01", value: finalAmount, onChange: (event) => setFinalAmount(event.target.value), placeholder: "Final repair amount" }), _jsx("input", { type: "number", min: "0", step: "0.01", value: labourAmount, onChange: (event) => setLabourAmount(event.target.value), placeholder: "Labour amount" }), _jsx("input", { value: invoiceRef, onChange: (event) => setInvoiceRef(event.target.value), placeholder: "Repair invoice reference" }), _jsx("input", { value: descriptionAmount, onChange: (event) => setDescriptionAmount(event.target.value), placeholder: "Description / amount note" }), _jsx("input", { type: "date", value: handoverDate, onChange: (event) => setHandoverDate(event.target.value) }), _jsx("button", { onClick: () => void finalize(), children: "Finalize Amount" })] }), _jsx("div", { className: "section-divider" }), _jsx("h4", { children: "Payments" }), _jsxs("div", { className: "list-stack", children: [detail.payments.length === 0 && _jsx("p", { className: "muted", children: "No repair payments yet." }), detail.payments.map((payment) => (_jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [_jsx("b", { children: payment.method }), " \u00B7 ", payment.payment_type, " \u00B7", ' ', payment.proof_no || 'No proof number', payment.reference ? ` · ${payment.reference}` : ''] }), _jsxs("span", { children: ["Rs. ", money(payment.amount)] }), payment.proof_no && (_jsx("button", { onClick: async () => {
                                    try {
                                        await api(`/documents/REPAIR_PAYMENT/${payment.id}/reprint`, {
                                            method: 'POST',
                                        });
                                    }
                                    catch (error) {
                                        onError(error.message);
                                    }
                                }, children: "Reprint Proof" }))] }, payment.id)))] }), _jsxs("div", { className: "form-grid compact", children: [_jsxs("select", { value: paymentMethod, onChange: (event) => setPaymentMethod(event.target.value), children: [_jsx("option", { value: "CASH", children: "Cash" }), _jsx("option", { value: "CARD", children: "Card" }), _jsx("option", { value: "ONLINE", children: "Online" })] }), _jsx("input", { type: "number", min: "0.01", step: "0.01", value: paymentAmount, onChange: (event) => setPaymentAmount(event.target.value), placeholder: "Payment amount" }), _jsx("input", { value: paymentReference, onChange: (event) => setPaymentReference(event.target.value), placeholder: "Reference" }), _jsx("button", { onClick: () => void addPayment(), children: "Add Payment" })] }), _jsx("div", { className: "section-divider" }), _jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("h4", { children: "Repair warranty" }), _jsx("p", { className: "muted", children: "Warranty starts from the hand-over/finalization date when a valid repair warranty period exists." })] }), _jsx("button", { onClick: () => void loadWarranty(), children: "Check Warranty" })] }), warranty && (_jsxs("div", { className: "success-banner", children: [_jsx("b", { children: warranty.status }), " \u00B7 ", warranty.start_date, " \u2192", ' ', warranty.expiry_date || 'No expiry', " \u00B7 ", warranty.warranty_period] }))] }));
}
function formatDateTime(value) {
    if (!value)
        return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
