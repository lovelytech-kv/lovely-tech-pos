import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { money } from '../../services/money';
const today = () => new Date().toISOString().slice(0, 10);
export function Purchases({ isAdmin, onError }) {
    const [query, setQuery] = useState('');
    const [items, setItems] = useState([]);
    const [selected, setSelected] = useState([]);
    const [quantity, setQuantity] = useState('1');
    const [date, setDate] = useState(today());
    const [reference, setReference] = useState('');
    const [notes, setNotes] = useState('');
    const [supplierId, setSupplierId] = useState('');
    const [paymentMethod, setPaymentMethod] = useState('CASH');
    const [suppliers, setSuppliers] = useState([]);
    const [pending, setPending] = useState([]);
    const [history, setHistory] = useState([]);
    const [costs, setCosts] = useState({});
    const [historyStart, setHistoryStart] = useState(today());
    const [historyEnd, setHistoryEnd] = useState(today());
    const [historyLoaded, setHistoryLoaded] = useState(false);
    const [busy, setBusy] = useState(false);
    const [purchaseKey, setPurchaseKey] = useState(() => crypto.randomUUID());
    const [correction, setCorrection] = useState(null);
    const [correctionValue, setCorrectionValue] = useState('');
    const [correctionReason, setCorrectionReason] = useState('');
    const [adminPassword, setAdminPassword] = useState('');
    const [savingCorrection, setSavingCorrection] = useState(false);
    const selectedQty = useMemo(() => selected.reduce((sum, row) => sum + Number(row.quantity || 0), 0), [selected]);
    async function search() {
        try {
            setItems(await api(`/inventory/items/search?q=${encodeURIComponent(query)}`));
        }
        catch (e) {
            onError?.(e.message);
        }
    }
    async function loadAdminData() {
        if (!isAdmin)
            return;
        try {
            const [p, s] = await Promise.all([api('/purchases/pending-costs'), api('/admin/suppliers')]);
            setPending(p);
            setSuppliers(s);
        }
        catch (e) {
            onError?.(e.message);
        }
    }
    async function loadHistory() {
        if (!isAdmin)
            return;
        try {
            const rows = await api('/purchases/history');
            const filtered = rows.filter(row => row.purchase_date >= historyStart && row.purchase_date <= historyEnd);
            setHistory(filtered);
            setHistoryLoaded(true);
        }
        catch (e) {
            onError?.(e.message);
        }
    }
    useEffect(() => { loadAdminData(); }, [isAdmin]);
    function add(item) {
        setSelected(prev => prev.some(x => x.item_id === item.item_id)
            ? prev.map(x => x.item_id === item.item_id ? { ...x, quantity } : x)
            : [...prev, { ...item, quantity }]);
    }
    function remove(itemId) { setSelected(prev => prev.filter(x => x.item_id !== itemId)); }
    async function save() {
        if (!selected.length) {
            onError?.('Add at least one item.');
            return;
        }
        if (selected.some(x => !Number.isFinite(Number(x.quantity)) || Number(x.quantity) <= 0)) {
            onError?.('Every purchase quantity must be greater than zero.');
            return;
        }
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
            setSelected([]);
            setReference('');
            setNotes('');
            setSupplierId('');
            setPaymentMethod('CASH');
            setQuantity('1');
            setPurchaseKey(crypto.randomUUID());
            await loadAdminData();
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    async function completeCost(row) {
        const value = costs[row.purchase_line_id];
        if (!value || Number(value) < 0) {
            onError?.('Enter a valid buy cost first.');
            return;
        }
        try {
            await api('/purchases/complete-cost', { method: 'POST', body: JSON.stringify({ version: row.version, purchase_version: row.purchase_version, purchase_id: row.purchase_id, purchase_line_id: row.purchase_line_id, unit_cost: value }) });
            setCosts(prev => ({ ...prev, [row.purchase_line_id]: '' }));
            await loadAdminData();
        }
        catch (e) {
            onError?.(e.message);
        }
    }
    function openCorrection(row, field) {
        const initial = field === 'cost' ? String(row.unit_cost ?? '') : field === 'date' ? row.line_date : field === 'quantity' ? String(row.quantity) : field === 'reference' ? String(row.reference_no ?? '') : String(row.supplier_id ?? '');
        setCorrection({ row, field });
        setCorrectionValue(initial);
        setCorrectionReason('');
        setAdminPassword('');
    }
    async function applyCorrection() {
        if (!correction)
            return;
        if (!correctionReason.trim()) {
            onError?.('Correction reason is required.');
            return;
        }
        if (!adminPassword) {
            onError?.('Admin re-authentication password is required.');
            return;
        }
        const { row, field } = correction;
        setSavingCorrection(true);
        try {
            let path = '';
            let body = {};
            if (field === 'cost') {
                path = '/purchases/correct-cost';
                body = { purchase_line_id: row.purchase_line_id, version: row.version ?? 0, unit_cost: correctionValue, reason: correctionReason.trim() };
            }
            if (field === 'date') {
                path = '/purchases/correct-date';
                body = { purchase_line_id: row.purchase_line_id, version: row.version ?? 0, line_date: correctionValue, reason: correctionReason.trim() };
            }
            if (field === 'quantity') {
                path = '/purchases/correct-quantity';
                body = { purchase_line_id: row.purchase_line_id, version: row.version ?? 0, quantity: correctionValue, reason: correctionReason.trim() };
            }
            if (field === 'reference') {
                path = '/purchases/correct-reference';
                body = { purchase_id: row.purchase_id, version: row.purchase_version ?? 0, reference_no: correctionValue.trim() || null, reason: correctionReason.trim() };
            }
            if (field === 'supplier') {
                const params = new URLSearchParams({ version: String(row.purchase_version ?? 0), admin_password: adminPassword });
                if (correctionValue)
                    params.set('supplier_id', correctionValue);
                await api(`/purchases/${row.purchase_id}/supplier?${params.toString()}`, { method: 'PUT' });
            }
            else {
                await api(`${path}?admin_password=${encodeURIComponent(adminPassword)}`, { method: 'POST', body: JSON.stringify(body) });
            }
            setCorrection(null);
            setAdminPassword('');
            await loadAdminData();
            await loadHistory();
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setSavingCorrection(false);
        }
    }
    return _jsxs("section", { className: "purchases-page", children: [_jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "INVENTORY IN" }), _jsx("h2", { children: "Purchase Entry" }), _jsx("p", { className: "muted", children: "Record supplier, date, reference and quantities. Buy cost stays Admin-only." })] }), _jsx("span", { className: "feature-badge", children: "FIFO COST CONTROL" })] }), _jsxs("div", { className: "search-row", children: [_jsx("input", { autoFocus: true, value: query, onChange: e => setQuery(e.target.value), onKeyDown: e => e.key === 'Enter' && search(), placeholder: "Search item code / description" }), _jsx("button", { onClick: search, children: "Search" })] }), _jsx("div", { className: "item-list", children: items.map(item => _jsxs("button", { className: "item-card", onClick: () => add(item), children: [_jsx("b", { children: item.item_code }), _jsx("span", { children: item.description }), _jsxs("small", { children: ["Current stock: ", item.stock] })] }, item.item_id)) }), _jsxs("div", { className: "form-grid compact", children: [_jsxs("label", { children: ["Date", _jsx("input", { type: "date", value: date, onChange: e => setDate(e.target.value) })] }), _jsxs("label", { children: ["Reference", _jsx("input", { value: reference, onChange: e => setReference(e.target.value), placeholder: "Supplier invoice / GRN" })] }), _jsxs("label", { children: ["Quantity", _jsx("input", { type: "number", min: "0.001", step: "0.001", value: quantity, onChange: e => setQuantity(e.target.value) })] }), _jsxs("label", { children: ["Payment Method", _jsxs("select", { value: paymentMethod, onChange: e => setPaymentMethod(e.target.value), children: [_jsx("option", { value: "CASH", children: "Cash" }), _jsx("option", { value: "CARD", children: "Card" }), _jsx("option", { value: "ONLINE", children: "Online" })] })] }), isAdmin && _jsxs("label", { children: ["Supplier", _jsxs("select", { value: supplierId, onChange: e => setSupplierId(e.target.value), children: [_jsx("option", { value: "", children: "No supplier" }), suppliers.map(s => _jsx("option", { value: s.supplier_id, children: s.name }, s.supplier_id))] })] })] }), _jsxs("label", { className: "wide-field", children: ["Notes", _jsx("textarea", { value: notes, onChange: e => setNotes(e.target.value), placeholder: "Optional purchase note" })] }), selected.length > 0 && _jsxs("div", { className: "status-strip", children: [_jsxs("div", { children: [_jsx("span", { children: "Lines" }), _jsx("b", { children: selected.length })] }), _jsxs("div", { children: [_jsx("span", { children: "Total quantity" }), _jsx("b", { children: selectedQty })] }), _jsxs("div", { children: [_jsx("span", { children: "Cost visibility" }), _jsx("b", { className: "status-good", children: "Admin only" })] })] }), selected.map(item => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [_jsx("b", { children: item.item_code }), " \u00B7 ", item.description, " \u00B7 Qty ", item.quantity] }), _jsx("button", { className: "danger-button", onClick: () => remove(item.item_id), children: "Remove" })] }, item.item_id)), _jsxs("div", { className: "form-actions", children: [_jsx("button", { disabled: busy || !selected.length, onClick: save, children: busy ? 'Saving…' : 'Save Purchase' }), _jsx("span", { className: "muted", children: "No buy cost is entered in this workspace." })] })] }), isAdmin && _jsxs(_Fragment, { children: [_jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("h2", { children: "Admin \u00B7 Pending Buy Cost" }), _jsx("p", { className: "muted", children: "Complete unresolved unit costs using optimistic-lock versions." })] }), _jsx("button", { onClick: loadAdminData, children: "Refresh" })] }), !pending.length ? _jsx("p", { className: "muted", children: "No pending purchase costs." }) : pending.map(row => _jsxs("div", { className: "pending-cost-row", children: [_jsxs("div", { children: [_jsx("b", { children: row.reference_no || 'Purchase' }), _jsxs("span", { children: [row.purchase_date, " \u00B7 Qty ", row.quantity, " \u00B7 Line v", row.version ?? '—', " / Purchase v", row.purchase_version ?? '—'] })] }), _jsx("input", { className: "cost-input", type: "number", min: "0", step: "0.01", value: costs[row.purchase_line_id] || '', onChange: e => setCosts(prev => ({ ...prev, [row.purchase_line_id]: e.target.value })), placeholder: "Buy cost" }), _jsx("button", { onClick: () => completeCost(row), children: "Complete Cost" })] }, row.purchase_line_id))] }), _jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("h2", { children: "Admin \u00B7 Purchase History" }), _jsx("p", { className: "muted", children: "Review recorded supplier, quantity and FIFO cost, then make audited corrections." })] }), _jsx("button", { disabled: !historyLoaded, onClick: () => { setHistoryLoaded(false); loadHistory(); }, children: "Reload" })] }), _jsxs("div", { className: "form-grid compact", children: [_jsxs("label", { children: ["From", _jsx("input", { type: "date", value: historyStart, onChange: e => setHistoryStart(e.target.value) })] }), _jsxs("label", { children: ["To", _jsx("input", { type: "date", value: historyEnd, onChange: e => setHistoryEnd(e.target.value) })] }), _jsx("button", { onClick: loadHistory, children: "Load History" })] }), !historyLoaded ? _jsx("p", { className: "muted", children: "Select a date range and load history." }) : !history.length ? _jsx("p", { className: "muted", children: "No purchase history in this date range." }) : history.map(row => _jsxs("div", { className: "purchase-history-row", children: [_jsxs("div", { className: "purchase-history-main", children: [_jsxs("b", { children: [row.item_code, " \u00B7 ", row.item_description] }), _jsxs("span", { children: [row.purchase_date, " \u00B7 Line ", row.line_date, " \u00B7 Qty ", row.quantity, " \u00B7 ", row.reference_no || 'No reference'] }), _jsxs("small", { children: ["Supplier: ", row.supplier_name || 'No supplier', " \u00B7 Payment: ", row.payment_method || 'CASH', " \u00B7 Unit cost: ", row.unit_cost == null ? 'Pending' : `Rs. ${money(row.unit_cost)}`, " \u00B7 Versions: line ", row.version ?? '—', ", purchase ", row.purchase_version ?? '—'] })] }), _jsxs("div", { className: "button-row", children: [_jsx("button", { onClick: () => openCorrection(row, 'cost'), disabled: row.unit_cost == null, children: "Cost" }), _jsx("button", { onClick: () => openCorrection(row, 'quantity'), children: "Qty" }), _jsx("button", { onClick: () => openCorrection(row, 'date'), children: "Date" }), _jsx("button", { onClick: () => openCorrection(row, 'reference'), children: "Reference" }), _jsx("button", { onClick: () => openCorrection(row, 'supplier'), children: "Supplier" })] })] }, row.purchase_line_id))] }), correction && _jsxs("div", { className: "glass panel correction-panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "ADMIN RE-AUTH" }), _jsxs("h3", { children: ["Correct ", correction.field] }), _jsxs("p", { className: "muted", children: [correction.row.item_code, " \u00B7 audited correction with version check."] })] }), _jsx("button", { className: "icon-button", onClick: () => setCorrection(null), children: "\u00D7" })] }), correction.field === 'supplier' ? _jsxs("select", { value: correctionValue, onChange: e => setCorrectionValue(e.target.value), children: [_jsx("option", { value: "", children: "Clear supplier" }), suppliers.map(s => _jsx("option", { value: s.supplier_id, children: s.name }, s.supplier_id))] }) : _jsx("input", { type: correction.field === 'date' ? 'date' : correction.field === 'quantity' || correction.field === 'cost' ? 'number' : 'text', min: correction.field === 'quantity' ? '0.001' : correction.field === 'cost' ? '0' : undefined, step: correction.field === 'quantity' ? '0.001' : correction.field === 'cost' ? '0.01' : undefined, value: correctionValue, onChange: e => setCorrectionValue(e.target.value) }), _jsxs("label", { className: "wide-field", children: ["Reason", _jsx("textarea", { value: correctionReason, onChange: e => setCorrectionReason(e.target.value), placeholder: "Why is this correction required?" })] }), _jsxs("label", { className: "wide-field", children: ["Admin password", _jsx("input", { type: "password", value: adminPassword, onChange: e => setAdminPassword(e.target.value), placeholder: "Re-authentication" })] }), _jsxs("div", { className: "form-actions", children: [_jsx("button", { disabled: savingCorrection, onClick: applyCorrection, children: savingCorrection ? 'Applying…' : 'Apply Audited Correction' }), _jsx("button", { className: "icon-button", onClick: () => setCorrection(null), children: "Cancel" })] })] })] })] });
}
