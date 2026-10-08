import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { api, serverLogout } from '../../api/client';
import { money, moneyAdd, moneySub, moneyTimesQty, moneyPositive, moneyEqual } from '../../services/money';
import { DashboardLayout } from '../../layouts/DashboardLayout';
import { RepairForm } from '../repairs/RepairForm';
import { RepairWorkspace } from '../repairs/RepairWorkspace';
import { Purchases } from '../purchases/Purchases';
import { DayEnd } from '../finance/DayEnd';
import { ReturnsWorkspace } from '../returns/ReturnsWorkspace';
import { WarrantyWorkspace } from '../warranty/WarrantyWorkspace';
import { SettingsPanel } from '../settings/SettingsPanel';
const baseTabs = ['Dashboard', 'Sales', 'Returns', 'Repairs', 'Warranty', 'Stock', 'Purchases', 'Expenses', 'Cash/Day', 'Reports', 'Documents'];
const today = () => new Date().toISOString().slice(0, 10);
export function POSHome({ user, onLogout }) {
    const [tab, setTab] = useState('Dashboard');
    const [error, setError] = useState('');
    const isAdmin = user.role.toUpperCase() === 'ADMIN';
    return _jsxs(DashboardLayout, { user: user, activeKey: tab, onNavigate: key => { setTab(key); setError(''); }, onLogout: () => { serverLogout().finally(onLogout); }, children: [error && _jsxs("div", { className: "error-banner", role: "alert", children: [_jsx("span", { children: error }), _jsx("button", { className: "error-dismiss", "aria-label": "Dismiss error", onClick: () => setError(''), children: "\u00D7" })] }), tab === 'Dashboard' && _jsx(DashboardTab, { isAdmin: isAdmin, onError: setError, onNavigate: setTab }), " ", tab === 'Customers' && _jsx(CustomersTab, { onError: setError }), " ", tab === 'Items' && _jsx(ItemsTab, { onError: setError }), " ", tab === 'Sales' && _jsx(SalesTab, { isAdmin: isAdmin, onError: setError }), " ", tab === 'Returns' && _jsx(ReturnsWorkspace, { isAdmin: isAdmin, onError: setError }), " ", tab === 'Repairs' && _jsxs(_Fragment, { children: [_jsx(RepairForm, { onError: setError }), _jsx(RepairWorkspace, { isAdmin: isAdmin, onError: setError })] }), " ", tab === 'Warranty' && _jsx(WarrantyWorkspace, { isAdmin: isAdmin, onError: setError }), " ", tab === 'Stock' && _jsx(StockTab, {}), " ", tab === 'Purchases' && _jsx(Purchases, { isAdmin: isAdmin, onError: setError }), " ", tab === 'Expenses' && _jsx(ExpensesTab, { onError: setError }), " ", tab === 'Cash/Day' && _jsx(DayEnd, { isAdmin: isAdmin, onError: setError }), " ", tab === 'Reports' && _jsx(ReportsTab, { isAdmin: isAdmin, onError: setError }), " ", tab === 'Documents' && _jsx(DocumentsTab, { onError: setError }), " ", tab === 'Settings' && _jsx(SettingsPanel, { isAdmin: isAdmin }), " ", tab === 'Admin' && isAdmin && _jsx(AdminTab, { onError: setError }), " ", tab === 'Backup' && isAdmin && _jsx(BackupTab, { onError: setError })] });
}
function CustomersTab({ onError }) {
    const [q, setQ] = useState(''), [rows, setRows] = useState([]), [selected, setSelected] = useState(null), [history, setHistory] = useState(null), [busy, setBusy] = useState(false);
    const [form, setForm] = useState({ name: '', contact_no: '', notes: '', version: 0 });
    async function search() { try {
        setRows(await api(`/customers?q=${encodeURIComponent(q.trim())}`));
    }
    catch (e) {
        onError(e.message);
    } }
    async function open(c) { setSelected(c); setForm({ name: c.name || '', contact_no: c.contact_no || '', notes: c.notes || '', version: Number(c.version || 0) }); setHistory(null); }
    async function save() { if (!selected)
        return; try {
        setBusy(true);
        const r = await api(`/customers/${selected.customer_id}`, { method: 'PUT', body: JSON.stringify(form) });
        setSelected(r);
        setRows(x => x.map(c => c.customer_id === r.customer_id ? r : c));
        setForm({ name: r.name || '', contact_no: r.contact_no || '', notes: r.notes || '', version: r.version });
        alert('Customer updated.');
    }
    catch (e) {
        onError(e.message);
    }
    finally {
        setBusy(false);
    } }
    async function create() { try {
        setBusy(true);
        const r = await api('/customers', { method: 'POST', body: JSON.stringify({ name: form.name || null, contact_no: form.contact_no || null, notes: form.notes || null }) });
        await search();
        open(r);
    }
    catch (e) {
        onError(e.message);
    }
    finally {
        setBusy(false);
    } }
    async function loadHistory() { if (!selected)
        return; try {
        setHistory(await api(`/customers/${selected.customer_id}/history`));
    }
    catch (e) {
        onError(e.message);
    } }
    return _jsxs("section", { className: "split", children: [_jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "CUSTOMERS" }), _jsx("h2", { children: "Customer directory" }), _jsx("p", { className: "muted", children: "Customer details are optional. History covers sales, repairs, warranty claims and settlements." })] }), _jsx("button", { onClick: search, children: "Search" })] }), _jsxs("div", { className: "search-row", children: [_jsx("input", { value: q, onChange: e => setQ(e.target.value), onKeyDown: e => e.key === 'Enter' && search(), placeholder: "Name or contact number" }), _jsx("button", { onClick: search, children: "Find" })] }), _jsxs("div", { className: "list-stack", children: [rows.map(c => _jsxs("button", { className: "list-row customer-row", onClick: () => open(c), children: [_jsxs("span", { children: [_jsx("b", { children: c.name || 'Unnamed customer' }), _jsxs("small", { children: [c.contact_no || 'No contact', " \u00B7 Version ", c.version] })] }), _jsx("span", { children: "\u203A" })] }, c.customer_id)), rows.length === 0 && _jsx("p", { className: "muted", children: "No customers loaded." })] })] }), _jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "CUSTOMER PROFILE" }), _jsx("h2", { children: selected ? selected.name || selected.contact_no || 'Customer' : 'Create customer' })] }), selected && _jsx("button", { onClick: loadHistory, children: "History" })] }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { placeholder: "Name", value: form.name, onChange: e => setForm({ ...form, name: e.target.value }) }), _jsx("input", { placeholder: "Contact no.", value: form.contact_no, onChange: e => setForm({ ...form, contact_no: e.target.value }) }), _jsx("textarea", { className: "wide-field", placeholder: "Notes", value: form.notes, onChange: e => setForm({ ...form, notes: e.target.value }) })] }), selected ? _jsx("button", { disabled: busy, onClick: save, children: "Save Customer" }) : _jsx("button", { disabled: busy || (!form.name.trim() && !form.contact_no.trim()), onClick: create, children: "Create Customer" }), selected && _jsxs("p", { className: "muted", children: ["Optimistic lock version: ", form.version, ". A stale save is rejected by the backend."] }), history && _jsxs("div", { className: "history-card", children: [_jsx("h3", { children: "History" }), _jsxs("div", { className: "status-strip", children: [_jsxs("div", { children: [_jsx("span", { children: "Sales" }), _jsx("b", { children: history.sales?.length || 0 })] }), _jsxs("div", { children: [_jsx("span", { children: "Repairs" }), _jsx("b", { children: history.repairs?.length || 0 })] }), _jsxs("div", { children: [_jsx("span", { children: "Warranty" }), _jsx("b", { children: history.warranty_claims?.length || 0 })] })] }), _jsx("h4", { children: "Sales" }), (history.sales || []).slice(0, 20).map((x) => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [x.invoice_no, " \u00B7 ", new Date(x.date).toLocaleString()] }), _jsxs("b", { children: ["Rs. ", money(x.total)] })] }, x.sale_id)), _jsx("h4", { children: "Settlements" }), (history.settlements || []).slice(0, 20).map((x) => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [new Date(x.date).toLocaleString(), " \u00B7 ", x.method] }), _jsxs("b", { children: ["Rs. ", money(x.amount)] })] }, x.settlement_id)), _jsx("h4", { children: "Repairs" }), (history.repairs || []).slice(0, 20).map((x) => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [x.repair_no, " \u00B7 ", x.status] }), _jsxs("b", { children: ["Rs. ", money(x.total)] })] }, x.repair_id))] })] })] });
}
function DashboardTab({ isAdmin, onError, onNavigate }) {
    const [report, setReport] = useState();
    const [day, setDay] = useState();
    const [targets, setTargets] = useState([]);
    const [backup, setBackup] = useState();
    async function load() { try {
        const d = today();
        const [r, c, b, t] = await Promise.all([api('/reports/sales-summary', { method: 'POST', body: JSON.stringify({ start: d, end: d }) }), api('/operations/day/status'), api('/backup/status'), api('/reports/target-progress', { method: 'POST', body: JSON.stringify({ start: d, end: d }) })]);
        setReport(r);
        setDay(c);
        setBackup(b);
        setTargets(t);
    }
    catch (e) {
        onError(e.message);
    } }
    useEffect(() => { load(); }, []);
    return _jsxs("section", { className: "workspace", children: [_jsxs("div", { className: "glass panel dashboard-hero rise-in", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "LOVELY TECH \u00B7 TODAY" }), _jsx("h2", { children: "Good day. Your shop at a glance." }), _jsx("p", { className: "muted", children: "Sales, cash, day status and targets \u2014 without hiding the important actions." })] }), _jsx("button", { onClick: load, className: "refresh-btn", children: "\u21BB Refresh" })] }), _jsxs("div", { className: "report-grid metric-grid", children: [_jsx(Metric, { t: "Sales", v: `Rs. ${money(report?.sales_total)}`, icon: "\u2197" }), _jsx(Metric, { t: "Bills", v: report?.sales_count ?? 0, icon: "#" }), _jsx(Metric, { t: "Cash", v: `Rs. ${money(report?.cash_total)}`, icon: "Rs" }), _jsx(Metric, { t: "Card", v: `Rs. ${money(report?.card_total)}`, icon: "\u25A3" }), _jsx(Metric, { t: "Online", v: `Rs. ${money(report?.online_total)}`, icon: "\u25CE" }), isAdmin && _jsxs(_Fragment, { children: [_jsx(Metric, { t: "Gross Profit", v: `Rs. ${money(report?.gross_profit)}`, icon: "G" }), _jsx(Metric, { t: "Net Profit", v: `Rs. ${money(report?.net_profit)}`, icon: "N" })] })] }), _jsxs("div", { className: "quick-actions", children: [_jsx("button", { onClick: () => onNavigate('Sales'), children: "\uFF0B New Sale" }), _jsx("button", { onClick: () => onNavigate('Items'), children: "\uFF0B Add Item" }), _jsx("button", { onClick: () => onNavigate('Repairs'), children: "\uFF0B New Repair" }), _jsx("button", { onClick: () => onNavigate('Purchases'), children: "\uFF0B Purchase" })] })] }), _jsxs("div", { className: "glass panel rise-in delay-1", children: [_jsx("div", { className: "section-head", children: _jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "CONTROL CENTER" }), _jsx("h2", { children: "Day / Backup / Targets" })] }) }), _jsxs("div", { className: "status-strip", children: [_jsxs("div", { children: [_jsx("span", { children: "Day Status" }), _jsx("b", { children: day?.status ?? '—' })] }), _jsxs("div", { children: [_jsx("span", { children: "Backup" }), _jsx("b", { className: (backup?.status || '').toUpperCase() === 'VERIFIED' ? 'status-good' : '', children: backup?.status ?? '—' })] }), _jsxs("div", { children: [_jsx("span", { children: "Expected Cash" }), _jsxs("b", { children: ["Rs. ", money(day?.expected_cash)] })] })] }), targets.length === 0 ? _jsx("p", { className: "muted", children: "No active targets." }) : targets.map((t) => _jsxs("div", { className: "target-row animated-target", children: [_jsx("span", { children: String(t.target_type).replaceAll('_', ' ') }), t.percentage == null ? _jsx("b", { children: "Target active" }) : _jsxs(_Fragment, { children: [_jsx("progress", { max: "100", value: Math.min(100, Number(t.percentage)) }), isAdmin ? _jsxs("b", { children: [money(t.percentage), "%"] }) : _jsx("b", { className: "muted", children: "Progress" })] })] }, t.target_id))] })] });
}
function SalesTab({ isAdmin, onError }) {
    const [q, setQ] = useState(''), [items, setItems] = useState([]), [cart, setCart] = useState([]), [cash, setCash] = useState(''), [cashReceived, setCashReceived] = useState(''), [card, setCard] = useState(''), [online, setOnline] = useState(''), [credit, setCredit] = useState(false), [customer, setCustomer] = useState(''), [customerQuery, setCustomerQuery] = useState(''), [customers, setCustomers] = useState([]), [settleAmount, setSettleAmount] = useState(''), [settleMethod, setSettleMethod] = useState('CASH'), [settlementKey, setSettlementKey] = useState(() => crypto.randomUUID()), [saleKey, setSaleKey] = useState(() => crypto.randomUUID()), [approvalId, setApprovalId] = useState(''), [pendingApproval, setPendingApproval] = useState(null), [customerHistory, setCustomerHistory] = useState(null), [serialQ, setSerialQ] = useState(''), [serialRows, setSerialRows] = useState([]), [doc, setDoc] = useState('SYSTEM_PRINTED'), [manualRef, setManualRef] = useState(''), [saleDateTime, setSaleDateTime] = useState(''), [busy, setBusy] = useState(false), [last, setLast] = useState();
    const total = useMemo(() => cart.reduce((sum, x) => moneyAdd(sum, moneySub(moneyTimesQty(x.price, x.quantity), x.discount)), '0.00'), [cart]);
    async function search() { try {
        setItems(await api(`/inventory/items/search?q=${encodeURIComponent(q)}`));
    }
    catch (e) {
        onError(e.message);
    } }
    async function searchCustomers() { try {
        setCustomers(await api(`/customers?q=${encodeURIComponent(customerQuery)}`));
    }
    catch (e) {
        onError(e.message);
    } }
    async function loadCustomerHistory() { try {
        if (!customer) {
            onError('Select a customer first.');
            return;
        }
        setCustomerHistory(await api(`/customers/${customer}/history`));
    }
    catch (e) {
        onError(e.message);
    } }
    function add(i) { setCart(c => c.some(x => x.item_id === i.item_id) ? c.map(x => x.item_id === i.item_id ? { ...x, quantity: moneyAdd(x.quantity, '1') } : x) : [...c, { ...i, quantity: '1', price: i.sale_price == null ? '' : String(i.sale_price), discount: '0', warranty_override: null }]); }
    async function findSerial() { try {
        setSerialRows(await api(`/inventory/serialized/search?q=${encodeURIComponent(serialQ.trim())}`));
    }
    catch (e) {
        onError(e.message);
    } }
    function attachSerial(unit) { const idx = cart.findIndex(x => x.item_id === unit.item_id); if (idx < 0) {
        onError('Add the serialized item to the cart first.');
        return;
    } setCart(c => c.map((x, i) => i === idx ? { ...x, serialized_unit_id: unit.serial_unit_id || unit.id, quantity: '1' } : x)); setSerialQ(''); setSerialRows([]); }
    function edit(id, k, v) { setCart(c => c.map(x => x.item_id === id ? { ...x, [k]: v } : x)); }
    function setWarrantyOverride(id, value) { setCart(c => c.map(x => x.item_id === id ? { ...x, warranty_override: value === 'DEFAULT' ? null : { ...(x.warranty_default || { warranty_type: 'NONE' }), warranty_type: value, duration_value: value === 'DAYS' || value === 'MONTHS' ? (x.warranty_override?.duration_value || x.warranty_default?.duration_value || null) : null, custom_rule: value === 'CUSTOM' ? (x.warranty_override?.custom_rule || x.warranty_default?.custom_rule || '') : null } } : x)); }
    async function checkout() {
        if (busy)
            return;
        try {
            setBusy(true);
            if (!cart.length) {
                onError('Add at least one item.');
                return;
            }
            if (cart.some(x => !x.price || !moneyPositive(x.price))) {
                onError('Enter a sale price for every item.');
                return;
            }
            if (doc === 'MANUAL' && !manualRef.trim()) {
                onError('Manual invoice reference is required.');
                return;
            }
            if (cart.some(x => moneyPositive(moneySub(x.discount, moneyTimesQty(x.price, x.quantity))))) {
                onError('Discount cannot exceed line total.');
                return;
            }
            const required = total;
            const entered = moneyAdd(cash, card, online);
            if (!credit && !moneyEqual(entered, required)) {
                onError(`Payment total must equal Rs. ${required}. Cash change: Rs. ${moneyPositive(moneySub(cash, required)) ? moneySub(cash, required) : '0.00'}`);
                return;
            }
            const payments = credit ? [] : [['CASH', cash], ['CARD', card], ['ONLINE', online]].filter(([, v]) => moneyPositive(String(v))).map(([method, amount]) => ({ method, amount: String(amount) }));
            const salePayload = { lines: cart.map(x => ({ item_id: x.item_id, quantity: x.quantity, unit_price: String(x.price), discount: String(x.discount), serialized_unit_id: x.serialized_unit_id || null, warranty_type: x.warranty_override?.warranty_type || null, warranty_duration_value: x.warranty_override?.duration_value || null, warranty_custom_rule: x.warranty_override?.custom_rule || null })), payments, credit_sale: credit, customer_id: credit ? customer || null : null, document_type: doc, manual_invoice_ref: doc === 'MANUAL' ? manualRef.trim() : null, sale_datetime: isAdmin && saleDateTime ? new Date(saleDateTime).toISOString() : null, cash_received: cashReceived || null, idempotency_key: saleKey, admin_discount_approval_id: approvalId.trim() || null };
            let result;
            try {
                result = await api('/sales', { method: 'POST', body: JSON.stringify(salePayload) });
                setLast(result);
                setCart([]);
                setCash('');
                setCashReceived('');
                setCard('');
                setOnline('');
                setManualRef('');
                setSaleDateTime('');
                setCredit(false);
                setApprovalId('');
                setPendingApproval(null);
                setSaleKey(crypto.randomUUID());
            }
            catch (e) {
                const msg = e.message;
                if (msg.includes('Admin approval required')) {
                    const approval = await api('/sales/discount-approval', { method: 'POST', body: JSON.stringify(salePayload) });
                    setPendingApproval(approval);
                    setApprovalId(approval.approval_id);
                    onError(`Discount approval requested: ${approval.approval_action_id}. After Admin approves it, retry the sale using the approval ID below.`);
                }
                else
                    throw e;
            }
        }
        catch (e) {
            onError(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    return _jsxs("section", { className: "workspace", children: [_jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "POINT OF SALE" }), _jsx("h2", { children: "New Sale" }), _jsx("p", { className: "muted", children: "Search or scan \u2192 cart \u2192 price/discount \u2192 warranty \u2192 payment \u2192 complete." })] }), _jsx("button", { className: "icon-button", disabled: !cart.length || busy, onClick: () => { setCart([]); setApprovalId(''); setPendingApproval(null); }, children: "Clear" })] }), _jsxs("div", { className: "search-row", children: [_jsx("input", { autoFocus: true, value: q, onChange: e => setQ(e.target.value), onKeyDown: e => e.key === 'Enter' && search(), placeholder: "Barcode / item code / description" }), _jsx("button", { onClick: search, children: "Search" })] }), _jsx("div", { className: "item-list", children: items.map(i => _jsxs("button", { className: "item-card", onClick: () => add(i), children: [_jsx("b", { children: i.item_code }), _jsx("span", { children: i.description }), _jsxs("small", { children: ["Stock: ", i.stock, " \u00B7 Rs. ", i.sale_price ?? 'Type price'] })] }, i.item_id)) }), _jsxs("div", { className: "search-row", children: [_jsx("input", { placeholder: "Serialized item IMEI / Serial", value: serialQ, onChange: e => setSerialQ(e.target.value), onKeyDown: e => e.key === 'Enter' && findSerial() }), _jsx("button", { onClick: findSerial, children: "Find Serialized Unit" })] }), serialRows.map(u => _jsxs("button", { className: "item-card", onClick: () => attachSerial(u), children: [_jsx("b", { children: u.serial_number || u.imei }), _jsx("span", { children: u.item_code || u.description }), _jsxs("small", { children: [u.status || 'AVAILABLE', " \u00B7 Click to attach"] })] }, u.serial_unit_id || u.id)), last && _jsxs("div", { className: "success-banner", children: ["Completed: ", last.invoice_no, " \u00B7 Rs. ", money(last.grand_total), last.negative_stock ? ' · Negative stock warning' : ''] })] }), _jsxs("div", { className: "glass panel", children: [_jsx("h2", { children: "Cart" }), cart.length === 0 ? _jsx("p", { className: "muted", children: "No items added." }) : cart.map(x => _jsxs("div", { className: "cart-line", children: [_jsxs("span", { children: [_jsx("b", { children: x.description }), x.serialized_unit_id && _jsxs("small", { children: ["Serialized unit: ", x.serialized_unit_id] }), _jsxs("div", { className: "line-controls", children: [_jsx("input", { type: "number", min: ".001", step: ".001", value: x.quantity, onChange: e => edit(x.item_id, 'quantity', e.target.value), title: "Quantity" }), _jsx("input", { type: "number", min: "0", step: ".01", value: x.price, onChange: e => edit(x.item_id, 'price', e.target.value), placeholder: "Price", title: "Sale price" }), _jsx("input", { type: "number", min: "0", step: ".01", value: x.discount, onChange: e => edit(x.item_id, 'discount', e.target.value), placeholder: "Discount", title: "Discount" }), _jsxs("select", { value: x.warranty_override?.warranty_type || 'DEFAULT', onChange: e => setWarrantyOverride(x.item_id, e.target.value), title: "Warranty override", children: [_jsx("option", { value: "DEFAULT", children: "Warranty: Default" }), _jsx("option", { value: "NONE", children: "No Warranty" }), _jsx("option", { value: "DAYS", children: "Warranty: Days" }), _jsx("option", { value: "MONTHS", children: "Warranty: Months" }), _jsx("option", { value: "CHECKING ONLY", children: "Checking Only" }), _jsx("option", { value: "CUSTOM", children: "Warranty: Custom" })] }), (x.warranty_override?.warranty_type === 'DAYS' || x.warranty_override?.warranty_type === 'MONTHS') && _jsx("input", { type: "number", min: "1", placeholder: "Duration", value: x.warranty_override?.duration_value || '', onChange: e => setCart(c => c.map(y => y.item_id === x.item_id ? { ...y, warranty_override: { ...y.warranty_override, duration_value: Number(e.target.value) || null } } : y)) }), " ", x.warranty_override?.warranty_type === 'CUSTOM' && _jsx("input", { placeholder: "e.g. 45 DAYS", value: x.warranty_override?.custom_rule || '', onChange: e => setCart(c => c.map(y => y.item_id === x.item_id ? { ...y, warranty_override: { ...y.warranty_override, custom_rule: e.target.value } } : y)) })] })] }), _jsxs("span", { className: "line-total-actions", children: [_jsxs("b", { children: ["Rs. ", moneySub(moneyTimesQty(x.price, x.quantity), x.discount)] }), _jsx("button", { className: "icon-button", "aria-label": `Remove ${x.description}`, onClick: () => setCart(c => c.filter(y => y.item_id !== x.item_id)), children: "\u00D7" })] })] }, x.item_id)), _jsxs("div", { className: "cart-total", children: [_jsx("span", { children: "Total" }), _jsxs("b", { children: ["Rs. ", money(total)] })] }), _jsxs("div", { className: "form-grid compact", children: [_jsxs("select", { value: doc, onChange: e => setDoc(e.target.value), children: [_jsx("option", { value: "SYSTEM_PRINTED", children: "Thermal Receipt" }), _jsx("option", { value: "MANUAL", children: "Manual Invoice Ref" }), _jsx("option", { value: "NO_PRINT", children: "No Print" })] }), doc === 'MANUAL' && _jsx("input", { placeholder: "Handwritten invoice reference", value: manualRef, onChange: e => setManualRef(e.target.value) }), isAdmin && _jsx("input", { type: "datetime-local", value: saleDateTime, onChange: e => setSaleDateTime(e.target.value), title: "Admin backdated/missed sale time" })] }), isAdmin && _jsxs("label", { className: "check", children: [_jsx("input", { type: "checkbox", checked: credit, onChange: e => setCredit(e.target.checked) }), " Admin Credit Sale"] }), credit && _jsxs(_Fragment, { children: [_jsxs("div", { className: "search-row", children: [_jsx("input", { placeholder: "Customer name / contact", value: customerQuery, onChange: e => setCustomerQuery(e.target.value), onKeyDown: e => e.key === 'Enter' && searchCustomers() }), _jsx("button", { onClick: searchCustomers, children: "Find Customer" })] }), _jsxs("select", { className: "wide-input", value: customer, onChange: e => setCustomer(e.target.value), children: [_jsx("option", { value: "", children: "Select customer" }), customers.map(c => _jsxs("option", { value: c.customer_id, children: [c.name || 'Unnamed', " \u00B7 ", c.contact_no || 'No contact'] }, c.customer_id))] }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { id: "newCustomerName", placeholder: "New customer name (optional)" }), _jsx("input", { id: "newCustomerContact", placeholder: "Contact no." }), _jsx("button", { onClick: async () => { try {
                                            const n = document.getElementById('newCustomerName')?.value.trim();
                                            const c = document.getElementById('newCustomerContact')?.value.trim();
                                            if (!n && !c) {
                                                onError('Enter customer name or contact.');
                                                return;
                                            }
                                            const r = await api('/customers', { method: 'POST', body: JSON.stringify({ name: n || null, contact_no: c || null, notes: null }) });
                                            setCustomer(r.customer_id);
                                            setCustomerQuery(r.name || r.contact_no || '');
                                            searchCustomers();
                                        }
                                        catch (e) {
                                            onError(e.message);
                                        } }, children: "Create Customer" })] }), _jsx("button", { disabled: !customer, onClick: loadCustomerHistory, children: "History" }), customerHistory && _jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("h3", { children: ["Customer History \u00B7 ", customerHistory.customer?.name || customerHistory.customer?.contact_no || 'Customer'] }), _jsx("button", { onClick: () => setCustomerHistory(null), children: "Close" })] }), _jsxs("div", { className: "day-card", children: [_jsx("span", { children: "Sales" }), _jsx("b", { children: customerHistory.sales?.length || 0 }), _jsx("span", { children: "Settlements" }), _jsx("b", { children: customerHistory.settlements?.length || 0 }), _jsx("span", { children: "Repairs" }), _jsx("b", { children: customerHistory.repairs?.length || 0 }), _jsx("span", { children: "Warranty Claims" }), _jsx("b", { children: customerHistory.warranty_claims?.length || 0 })] }), _jsx("h4", { children: "Sales" }), (customerHistory.sales || []).slice(0, 20).map((x) => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [x.invoice_no, " \u00B7 ", new Date(x.date).toLocaleString()] }), _jsxs("b", { children: ["Rs. ", money(x.total)] })] }, x.sale_id)), _jsx("h4", { children: "Settlements" }), (customerHistory.settlements || []).slice(0, 20).map((x) => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [new Date(x.date).toLocaleString(), " \u00B7 ", x.method] }), _jsxs("b", { children: ["Rs. ", money(x.amount), " \u00B7 Remaining Rs. ", money(x.remaining)] })] }, x.settlement_id)), _jsx("h4", { children: "Repairs" }), (customerHistory.repairs || []).slice(0, 20).map((x) => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [x.repair_no, " \u00B7 ", x.status, " \u00B7 ", new Date(x.date).toLocaleDateString()] }), _jsxs("b", { children: ["Rs. ", money(x.total)] })] }, x.repair_id)), _jsx("h4", { children: "Warranty Claims" }), (customerHistory.warranty_claims || []).slice(0, 20).map((x) => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [x.claim_no, " \u00B7 ", x.invoice_no, " \u00B7 ", x.decision] }), _jsx("b", { children: x.outcome || 'Pending' })] }, x.claim_id))] }), isAdmin && _jsxs(_Fragment, { children: [_jsx("input", { type: "number", min: "0.01", step: "0.01", placeholder: "Settlement amount", value: settleAmount, onChange: e => setSettleAmount(e.target.value) }), _jsxs("select", { value: settleMethod, onChange: e => setSettleMethod(e.target.value), children: [_jsx("option", { children: "CASH" }), _jsx("option", { children: "CARD" }), _jsx("option", { children: "ONLINE" })] }), _jsx("button", { disabled: !customer || !settleAmount, onClick: async () => { try {
                                            const r = await api('/operations/settlements', { method: 'POST', body: JSON.stringify({ idempotency_key: settlementKey, customer_id: customer, amount: settleAmount, payment_method: settleMethod }) });
                                            setSettleAmount('');
                                            setSettlementKey(crypto.randomUUID());
                                            alert(`Settlement ${r.proof_no} recorded · Remaining Rs. ${money(r.remaining_outstanding)}`);
                                            await api(`/documents/SETTLEMENT/${r.settlement_id}/reprint`, { method: 'POST' });
                                        }
                                        catch (e) {
                                            onError(e.message);
                                        } }, children: "Settle Credit" })] })] }), " ", !credit && _jsxs("div", { className: "payment-grid", children: [_jsx("input", { type: "number", min: "0", step: ".01", placeholder: "Cash applied", value: cash, onChange: e => setCash(e.target.value) }), _jsx("input", { type: "number", min: "0", step: ".01", placeholder: "Cash received", value: cashReceived, onChange: e => setCashReceived(e.target.value) }), _jsx("input", { type: "number", min: "0", step: ".01", placeholder: "Card", value: card, onChange: e => setCard(e.target.value) }), _jsx("input", { type: "number", min: "0", step: ".01", placeholder: "Online", value: online, onChange: e => setOnline(e.target.value) })] }), !credit && _jsxs("div", { className: "balance-box", children: ["Balance / Change: ", _jsxs("b", { children: ["Rs. ", (moneyPositive(moneySub(cashReceived, cash)) ? moneySub(cashReceived, cash) : '0.00')] })] }), pendingApproval && _jsxs("div", { className: "approval-box", children: [_jsx("b", { children: "Discount approval" }), _jsxs("span", { children: ["Request: ", pendingApproval.approval_action_id] }), _jsxs("label", { children: ["Approved approval ID", _jsx("input", { value: approvalId, onChange: e => setApprovalId(e.target.value), placeholder: "Paste approved approval_id" })] }), _jsx("small", { children: "Do not reuse an approval for a different sale. The backend validates the approved request." })] }), _jsx("button", { disabled: !cart.length || busy, onClick: checkout, children: busy ? 'Processing…' : credit ? 'Complete Credit Sale' : 'Complete Sale' })] })] });
}
function StockTab() { const [rows, setRows] = useState([]), [age, setAge] = useState([]), [serialRows, setSerialRows] = useState([]), [q, setQ] = useState(''), [serial, setSerial] = useState(''); async function load() { try {
    setRows(await api('/inventory/summary'));
}
catch { } } async function loadAge() { try {
    setAge(await api('/reports/stock-age', { method: 'POST', body: JSON.stringify({ start: today(), end: today() }) }));
}
catch { } } async function findSerial() { try {
    setSerialRows(await api(`/inventory/serialized/search?q=${encodeURIComponent(serial.trim())}`));
}
catch {
    setSerialRows([]);
} } useEffect(() => { load(); }, []); return _jsxs("section", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsx("h2", { children: "Stock Count / Serial & IMEI" }), _jsxs("div", { children: [_jsx("button", { onClick: load, children: "Refresh" }), _jsx("button", { onClick: loadAge, children: "Stock Age by Batch" })] })] }), _jsxs("div", { className: "search-row", children: [_jsx("input", { placeholder: "Search IMEI / Serial / barcode", value: serial, onChange: e => setSerial(e.target.value), onKeyDown: e => e.key === 'Enter' && findSerial() }), _jsx("button", { onClick: findSerial, children: "Find Serial / IMEI" })] }), serialRows.length > 0 && _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Serialized Units" }), serialRows.map(x => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [x.serial_number || x.imei, " \u00B7 ", x.item_code || x.description] }), _jsx("b", { children: x.status || '—' })] }, x.serial_unit_id || x.id))] }), _jsx("input", { className: "wide-input", placeholder: "Filter stock", value: q, onChange: e => setQ(e.target.value) }), rows.filter(x => (x.item_code + ' ' + x.description).toLowerCase().includes(q.toLowerCase())).map(x => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [x.item_code, " \u00B7 ", x.description] }), _jsxs("b", { children: [money(x.stock), Number(x.stock) < 0 ? ' · NEGATIVE' : ''] })] }, x.item_id)), age.length > 0 && _jsxs(_Fragment, { children: [_jsx("h3", { children: "Purchase Batch Age" }), age.map(x => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [x.item_code, " \u00B7 ", x.description, " \u00B7 ", x.lot_date] }), _jsxs("b", { children: [x.remaining_quantity, " units \u00B7 ", x.age_days, " days"] })] }, x.lot_id))] })] }); }
function PurchasesTab({ isAdmin, onError }) {
    const [rows, setRows] = useState([]), [history, setHistory] = useState([]), [items, setItems] = useState([]), [suppliers, setSuppliers] = useState([]), [q, setQ] = useState(''), [selected, setSelected] = useState([]), [qty, setQty] = useState('1'), [ref, setRef] = useState(''), [date, setDate] = useState(today()), [supplierId, setSupplierId] = useState(''), [costs, setCosts] = useState({});
    async function load() {
        try {
            if (isAdmin) {
                const [pending, hist, sup] = await Promise.all([api('/purchases/pending-costs'), api('/purchases/history'), api('/admin/suppliers')]);
                setRows(pending);
                setHistory(hist);
                setSuppliers(sup);
            }
        }
        catch (e) {
            onError(e.message);
        }
    }
    useEffect(() => { load(); }, [isAdmin]);
    async function search() { try {
        setItems(await api(`/inventory/items/search?q=${encodeURIComponent(q)}`));
    }
    catch (e) {
        onError(e.message);
    } }
    function add(i) { setSelected(s => s.some(x => x.item_id === i.item_id) ? s : s.concat(i)); }
    async function savePurchase() {
        try {
            await api('/purchases', { method: 'POST', body: JSON.stringify({
                    purchase_date: date, reference_no: ref || null, supplier_id: isAdmin ? (supplierId || null) : null,
                    lines: selected.map(i => ({ item_id: i.item_id, quantity: qty, line_date: date })),
                    idempotency_key: crypto.randomUUID()
                }) });
            setSelected([]);
            setRef('');
            setSupplierId('');
            await load();
            alert('Purchase saved; cost remains Admin-pending.');
        }
        catch (e) {
            onError(e.message);
        }
    }
    async function saveCost(r) {
        try {
            await api('/purchases/complete-cost', { method: 'POST', body: JSON.stringify({ version: r.version ?? null, purchase_version: r.purchase_version ?? null, purchase_id: r.purchase_id, purchase_line_id: r.purchase_line_id, unit_cost: String(costs[r.purchase_line_id]) }) });
            load();
        }
        catch (e) {
            onError(e.message);
        }
    }
    async function correct(path, body) {
        try {
            const pw = window.prompt('Admin password (re-authentication required)') || '';
            await api(`${path}?admin_password=${encodeURIComponent(pw)}`, { method: 'POST', body: JSON.stringify(body) });
            await load();
        }
        catch (e) {
            onError(e.message);
        }
    }
    return _jsxs("section", { className: "workspace", children: [_jsxs("div", { className: "glass panel", children: [_jsx("h2", { children: "Purchase Entry" }), _jsxs("div", { className: "search-row", children: [_jsx("input", { value: q, onChange: e => setQ(e.target.value), onKeyDown: e => e.key === 'Enter' && search(), placeholder: "Search item" }), _jsx("button", { onClick: search, children: "Search" })] }), _jsx("div", { className: "item-list", children: items.map(i => _jsxs("button", { className: "item-card", onClick: () => add(i), children: [_jsx("b", { children: i.item_code }), _jsx("span", { children: i.description }), _jsxs("small", { children: ["Stock ", i.stock] })] }, i.item_id)) }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { type: "date", value: date, onChange: e => setDate(e.target.value) }), _jsx("input", { placeholder: "Reference (optional)", value: ref, onChange: e => setRef(e.target.value) }), _jsx("input", { type: "number", min: ".001", step: ".001", value: qty, onChange: e => setQty(e.target.value) }), isAdmin && _jsxs("select", { value: supplierId, onChange: e => setSupplierId(e.target.value), children: [_jsx("option", { value: "", children: "Supplier (optional)" }), suppliers.map(x => _jsx("option", { value: x.supplier_id, children: x.name }, x.supplier_id))] })] }), selected.map(i => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [i.item_code, " \u00B7 ", i.description] }), _jsx("button", { onClick: () => setSelected(s => s.filter(x => x.item_id !== i.item_id)), children: "Remove" })] }, i.item_id)), _jsx("button", { disabled: !selected.length, onClick: savePurchase, children: "Save Purchase (No Cost)" })] }), isAdmin && _jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsx("h2", { children: "Private Cost Pending" }), _jsx("button", { onClick: load, children: "Refresh" })] }), rows.length === 0 ? _jsx("p", { className: "muted", children: "No pending costs." }) : rows.map(r => _jsxs("div", { className: "claim-row", children: [_jsxs("span", { children: [r.reference_no || 'Purchase', " \u00B7 Qty ", r.quantity, " \u00B7 ", r.purchase_date] }), _jsx("input", { className: "cost-input", placeholder: "Buy cost", value: costs[r.purchase_line_id] || '', onChange: e => setCosts({ ...costs, [r.purchase_line_id]: e.target.value }) }), _jsx("button", { onClick: () => saveCost(r), children: "Complete Cost" }), _jsx("button", { onClick: () => { const q = window.prompt('Correct quantity', String(r.quantity)); if (!q)
                                    return; const reason = window.prompt('Reason') || ''; correct('/purchases/correct-quantity', { purchase_line_id: r.purchase_line_id, version: r.version ?? 0, quantity: q, reason }); }, children: "Correct Qty" }), _jsx("button", { onClick: () => { const d = window.prompt('Correct purchase date', String(r.purchase_date)) || ''; if (!d)
                                    return; const reason = window.prompt('Reason') || ''; correct('/purchases/correct-date', { purchase_line_id: r.purchase_line_id, version: r.version ?? 0, line_date: d, reason }); }, children: "Correct Date" })] }, r.purchase_line_id))] }), isAdmin && _jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsx("h2", { children: "Completed Purchase History / Corrections" }), _jsx("button", { onClick: load, children: "Refresh" })] }), history.filter(r => r.unit_cost != null).map(r => _jsxs("div", { className: "claim-row", children: [_jsxs("span", { children: [_jsx("b", { children: r.reference_no || 'Purchase' }), " \u00B7 ", r.purchase_date, " \u00B7 ", r.supplier_name || 'No supplier', _jsxs("small", { children: [r.item_code, " \u00B7 ", r.item_description, " \u00B7 Qty ", r.quantity, " \u00B7 Cost Rs. ", money(r.unit_cost)] })] }), _jsxs("div", { className: "button-row", children: [_jsx("button", { onClick: () => { const c = window.prompt('New unit cost', String(r.unit_cost)); if (!c)
                                            return; const reason = window.prompt('Reason') || ''; correct('/purchases/correct-cost', { purchase_line_id: r.purchase_line_id, version: r.version ?? 0, unit_cost: c, reason }); }, children: "Correct Cost" }), _jsx("button", { onClick: () => { const d = window.prompt('New line date', String(r.line_date)) || ''; if (!d)
                                            return; const reason = window.prompt('Reason') || ''; correct('/purchases/correct-date', { purchase_line_id: r.purchase_line_id, version: r.version ?? 0, line_date: d, reason }); }, children: "Correct Date" }), _jsx("button", { onClick: () => { const q = window.prompt('New quantity', String(r.quantity)) || ''; if (!q)
                                            return; const reason = window.prompt('Reason') || ''; correct('/purchases/correct-quantity', { purchase_line_id: r.purchase_line_id, version: r.version ?? 0, quantity: q, reason }); }, children: "Correct Qty" }), _jsx("button", { onClick: () => { const ref = window.prompt('New reference', r.reference_no || ''); const reason = window.prompt('Reason') || ''; if (ref === null)
                                            return; correct('/purchases/correct-reference', { purchase_id: r.purchase_id, version: r.purchase_version ?? r.version ?? 0, reference_no: ref || null, reason }); }, children: "Correct Ref" }), _jsx("button", { onClick: () => { const sid = window.prompt('Supplier ID (blank to clear)', r.supplier_id || ''); if (sid === null)
                                            return; const pw = window.prompt('Admin password (re-authentication required)') || ''; api(`/purchases/${r.purchase_id}/supplier?supplier_id=${encodeURIComponent(sid)}&version=${encodeURIComponent(r.purchase_version ?? r.version ?? 0)}&admin_password=${encodeURIComponent(pw)}`, { method: 'PUT' }).then(load).catch(e => onError(e.message)); }, children: "Set Supplier" })] })] }, r.purchase_line_id)), history.length === 0 && _jsx("p", { className: "muted", children: "No purchase history." })] })] });
}
function ExpensesTab({ onError }) {
    const [mode, setMode] = useState('EXPENSE'), [cats, setCats] = useState([]), [category, setCategory] = useState(''), [date, setDate] = useState(today()), [amount, setAmount] = useState(''), [method, setMethod] = useState('CASH'), [description, setDescription] = useState(''), [busy, setBusy] = useState(false), [last, setLast] = useState();
    async function load() { try {
        const c = await api('/admin/expense-categories');
        setCats(c);
        if (!category && c[0])
            setCategory(c[0].id);
    }
    catch (e) {
        onError(e.message);
    } }
    useEffect(() => { load(); }, []);
    async function save() { if (!amount)
        return; setBusy(true); try {
        const path = mode === 'EXPENSE' ? '/admin/expenses' : '/admin/other-income';
        const body = mode === 'EXPENSE' ? { category_id: category, expense_date: date, amount, payment_method: method, description: description || null } : { income_date: date, amount, payment_method: method, description: description || null };
        const r = await api(path, { method: 'POST', body: JSON.stringify(body) });
        setLast({ ...r, mode });
        setAmount('');
        setDescription('');
    }
    catch (e) {
        onError(e.message);
    }
    finally {
        setBusy(false);
    } }
    return _jsxs("section", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsx("h2", { children: "Expenses / Other Income" }), _jsx("button", { onClick: load, children: "Refresh" })] }), _jsxs("div", { className: "button-row", children: [_jsx("button", { className: mode === 'EXPENSE' ? '' : 'ghost', onClick: () => setMode('EXPENSE'), children: "Expense" }), _jsx("button", { className: mode === 'INCOME' ? '' : 'ghost', onClick: () => setMode('INCOME'), children: "Other Income" })] }), _jsxs("div", { className: "form-grid compact", children: [mode === 'EXPENSE' && _jsxs("select", { value: category, onChange: e => setCategory(e.target.value), children: [_jsx("option", { value: "", children: "Category" }), cats.map(c => _jsx("option", { value: c.id, children: c.name }, c.id))] }), _jsx("input", { type: "date", value: date, onChange: e => setDate(e.target.value) }), _jsx("input", { type: "number", min: "0.01", step: "0.01", placeholder: "Amount", value: amount, onChange: e => setAmount(e.target.value) }), _jsxs("select", { value: method, onChange: e => setMethod(e.target.value), children: [_jsx("option", { children: "CASH" }), _jsx("option", { children: "CARD" }), _jsx("option", { children: "ONLINE" })] }), _jsx("input", { placeholder: "Description / note", value: description, onChange: e => setDescription(e.target.value) }), _jsx("button", { disabled: busy || !amount || (mode === 'EXPENSE' && !category), onClick: save, children: busy ? 'Saving…' : mode === 'EXPENSE' ? 'Add Expense' : 'Add Other Income' })] }), last && _jsxs("div", { className: "success-banner", children: [mode === 'EXPENSE' ? 'Expense' : 'Other income', " saved \u00B7 ", last.status === 'PENDING_APPROVAL' ? 'Pending Admin approval' : 'Approved'] }), _jsx("p", { className: "muted", children: "Cashier entries remain pending until Admin approval. Expenses are monthly outflows and do not automatically reduce the Day-End drawer." })] });
}
function ReportsTab({ isAdmin, onError }) {
    const [d, setD] = useState(), [comparison, setComparison] = useState(), [cashHands, setCashHands] = useState(), [cashiers, setCashiers] = useState([]), [rows, setRows] = useState([]), [start, setStart] = useState(today()), [end, setEnd] = useState(today()), [reportType, setReportType] = useState('sales'), [loading, setLoading] = useState(false);
    async function load() { try {
        setLoading(true);
        const range = { start, end };
        setRows([]);
        setComparison(undefined);
        setCashHands(undefined);
        setCashiers([]);
        if (reportType === 'sales' || reportType === 'profit') {
            setD(await api('/reports/sales-summary', { method: 'POST', body: JSON.stringify(range) }));
            setComparison(await api('/reports/comparison', { method: 'POST', body: JSON.stringify(range) }));
            if (isAdmin)
                setCashiers(await api('/reports/cashiers', { method: 'POST', body: JSON.stringify(range) }));
        }
        else if (reportType === 'cash-in-hands') {
            if (isAdmin)
                setCashHands(await api('/reports/cash-in-hands', { method: 'POST', body: JSON.stringify(range) }));
        }
        else if (reportType === 'stock') {
            setRows(await api('/inventory/summary'));
        }
        else {
            const path = reportType === 'purchases' ? '/reports/purchases' : reportType === 'repairs' ? '/reports/repairs' : reportType === 'warranty' ? '/reports/warranty' : '/reports/cash-drawer';
            setRows(await api(path, { method: 'POST', body: JSON.stringify(range) }));
        }
    }
    catch (e) {
        onError(e.message);
    }
    finally {
        setLoading(false);
    } }
    async function exportReport(fmt) { try {
        const token = localStorage.getItem('ltpos_token') || '';
        const apiBase = (import.meta.env.VITE_API_BASE ?? '/api/v1').replace(/\/$/, '');
        const r = await fetch(`${apiBase}/reports/export/${reportType}/${fmt}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify({ start, end }) });
        if (!r.ok)
            throw new Error(await r.text());
        const b = await r.blob();
        const u = URL.createObjectURL(b);
        const a = document.createElement('a');
        a.href = u;
        a.download = `lovely-tech-${reportType}-${start}-to-${end}.${fmt}`;
        a.click();
        URL.revokeObjectURL(u);
    }
    catch (e) {
        onError(e.message);
    } }
    function preset(kind) { const now = new Date(); if (kind === 'today') {
        const x = today();
        setStart(x);
        setEnd(x);
    }
    else if (kind === 'yesterday') {
        now.setDate(now.getDate() - 1);
        const x = now.toISOString().slice(0, 10);
        setStart(x);
        setEnd(x);
    }
    else if (kind === 'month') {
        const x = today();
        setStart(x.slice(0, 7) + '-01');
        setEnd(x);
    }
    else if (kind === 'year') {
        const x = today();
        setStart(x.slice(0, 4) + '-01-01');
        setEnd(x);
    }
    else {
        now.setMonth(now.getMonth() - 1);
        const x = now.toISOString().slice(0, 10);
        const e = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().slice(0, 10);
        setStart(x.slice(0, 7) + '-01');
        setEnd(e);
    } }
    return _jsxs("section", { className: "report-page", children: [_jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("h2", { children: "Reports" }), _jsx("p", { className: "muted", children: "Daily, monthly, yearly/custom-range operational reports with PDF/Excel export." })] }), _jsxs("div", { className: "button-row", children: [_jsx("button", { disabled: loading, onClick: load, children: loading ? 'Loading…' : 'Load' }), _jsxs("select", { value: reportType, onChange: e => { setReportType(e.target.value); setRows([]); }, children: [_jsx("option", { value: "sales", children: "Sales" }), _jsx("option", { value: "profit", disabled: !isAdmin, children: "Profit (Admin)" }), _jsx("option", { value: "purchases", disabled: !isAdmin, children: "Purchases (Admin)" }), _jsx("option", { value: "repairs", children: "Repairs" }), _jsx("option", { value: "warranty", children: "Warranty" }), _jsx("option", { value: "cash-drawer", disabled: !isAdmin, children: "Cash Drawer (Admin)" }), _jsx("option", { value: "cash-in-hands", disabled: !isAdmin, children: "Cash In Hands (Admin)" }), _jsx("option", { value: "stock", children: "Stock" })] }), _jsx("button", { onClick: () => exportReport('xlsx'), children: "Excel" }), _jsx("button", { onClick: () => exportReport('pdf'), children: "PDF" })] })] }), _jsxs("div", { className: "button-row", children: [_jsx("button", { onClick: () => preset('today'), children: "Today" }), _jsx("button", { onClick: () => preset('yesterday'), children: "Yesterday" }), _jsx("button", { onClick: () => preset('month'), children: "This Month" }), _jsx("button", { onClick: () => preset('year'), children: "This Year" }), _jsx("button", { onClick: () => preset('previous'), children: "Previous Month" })] }), _jsxs("div", { className: "date-row", children: [_jsx("input", { type: "date", value: start, onChange: e => setStart(e.target.value) }), _jsx("input", { type: "date", value: end, onChange: e => setEnd(e.target.value) })] })] }), reportType === 'sales' || reportType === 'profit' ? _jsx(_Fragment, { children: _jsx("div", { className: "glass panel", children: _jsxs("div", { className: "report-grid", children: [_jsx(Metric, { t: "Sales", v: `Rs. ${money(d?.sales_total)}` }), _jsx(Metric, { t: "Bills", v: d?.sales_count ?? 0 }), _jsx(Metric, { t: "Cash", v: `Rs. ${money(d?.cash_total)}` }), _jsx(Metric, { t: "Card", v: `Rs. ${money(d?.card_total)}` }), _jsx(Metric, { t: "Online", v: `Rs. ${money(d?.online_total)}` }), isAdmin && _jsxs(_Fragment, { children: [_jsx(Metric, { t: "Cost", v: `Rs. ${money(d?.cost_total)}` }), _jsx(Metric, { t: "Gross Profit", v: `Rs. ${money(d?.gross_profit)}` }), _jsx(Metric, { t: "Refunds", v: `Rs. ${money(d?.refunds_total)}` }), _jsx(Metric, { t: "Return Charges", v: `Rs. ${money(d?.return_charge_total)}` }), _jsx(Metric, { t: "Expenses", v: `Rs. ${money(d?.expenses_total)}` }), _jsx(Metric, { t: "Other Income", v: `Rs. ${money(d?.other_income_total)}` }), _jsx(Metric, { t: "Repair Income", v: `Rs. ${money(d?.repair_income)}` }), _jsx(Metric, { t: "Repair Profit", v: `Rs. ${money(d?.repair_profit)}` }), _jsx(Metric, { t: "Damage/Loss", v: `Rs. ${money(d?.damage_loss_total)}` }), _jsx(Metric, { t: "Net Profit", v: `Rs. ${money(d?.net_profit)}` })] })] }) }) }) : null, reportType === 'cash-in-hands' && isAdmin && _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Cash In Hands" }), _jsxs("div", { className: "cash-total-box", children: [_jsx("span", { children: "Approved inflows \u2212 approved outflows" }), _jsxs("strong", { children: ["Rs. ", money(cashHands?.cash_in_hands)] })] })] }), reportType === 'stock' && _jsx(ReportRows, { title: "Current Stock", rows: rows, fields: ['item_code', 'description', 'stock'] }), reportType === 'purchases' && isAdmin && _jsx(ReportRows, { title: "Purchases", rows: rows, fields: ['purchase_date', 'reference_no', 'item_id', 'quantity', 'unit_cost'] }), reportType === 'repairs' && _jsx(ReportRows, { title: "Repairs", rows: rows, fields: ['repair_no', 'date_in', 'status', 'total_amount', 'labour_amount', 'payments_total'] }), reportType === 'warranty' && _jsx(ReportRows, { title: "Warranty Claims", rows: rows, fields: ['claim_no', 'created_at', 'item_id', 'quantity', 'decision', 'outcome'] }), reportType === 'cash-drawer' && isAdmin && _jsx(ReportRows, { title: "Cash Drawer", rows: rows, fields: ['business_date', 'opening_cash', 'expected_cash', 'actual_cash', 'difference', 'reload_total', 'reason'] }), comparison && _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Previous-period comparison" }), _jsxs("div", { className: "comparison-row", children: [_jsx("span", { children: "Sales" }), _jsx("div", { className: "compare-bar", children: _jsx("i", { style: { width: `${Math.min(100, Number(comparison.current.sales_total) / (Math.max(1, Number(comparison.previous.sales_total))) * 100)}%` } }) }), _jsxs("b", { children: ["Rs. ", money(comparison.current.sales_total), " vs Rs. ", money(comparison.previous.sales_total)] })] }), _jsxs("div", { className: "comparison-row", children: [_jsx("span", { children: "Bills" }), _jsx("div", { className: "compare-bar", children: _jsx("i", { style: { width: `${Math.min(100, Number(comparison.current.sales_count) / (Math.max(1, Number(comparison.previous.sales_count))) * 100)}%` } }) }), _jsxs("b", { children: [comparison.current.sales_count, " vs ", comparison.previous.sales_count] })] })] }), isAdmin && cashiers.length > 0 && _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Cashier Summary" }), cashiers.map(c => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [c.cashier_name, " \u00B7 ", c.sales_count, " bills"] }), _jsxs("b", { children: ["Rs. ", money(c.gross_profit), " gross profit"] })] }, c.cashier_id))] })] });
}
function ReportRows({ title, rows, fields }) { return _jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsx("h3", { children: title }), _jsxs("span", { className: "muted", children: [rows.length, " rows"] })] }), rows.length === 0 ? _jsx("p", { className: "muted", children: "No records for this date range." }) : rows.map((r, i) => _jsxs("div", { className: "stock-row", children: [_jsx("span", { children: fields.slice(0, Math.ceil(fields.length / 2)).map(f => _jsxs("span", { children: [f.replaceAll('_', ' '), ": ", String(r[f] ?? '—'), " \u00B7 "] }, f)) }), _jsx("b", { children: fields.slice(Math.ceil(fields.length / 2)).map(f => `${f.replaceAll('_', ' ')}: ${r[f] ?? '—'}`).join(' · ') })] }, r.id || r.purchase_line_id || r.claim_id || r.repair_id || `${title}-${i}`))] }); }
function DocumentsTab({ onError }) {
    const [q, setQ] = useState(''), [rows, setRows] = useState([]), [busy, setBusy] = useState(false), [last, setLast] = useState('');
    async function search() { const term = q.trim(); if (!term)
        return onError('Enter an invoice, repair number or payment proof number.'); try {
        setRows(await api(`/documents/search?q=${encodeURIComponent(term)}`));
        setLast('');
    }
    catch (e) {
        onError(e.message);
    } }
    async function reprint(r) { try {
        setBusy(true);
        const result = await api(`/documents/${r.document_type}/${r.document_id}/reprint`, { method: 'POST' });
        setLast(`Reprint event recorded · ${r.document_no} · Event ${result.reprint_event_id || 'saved'}`);
    }
    catch (e) {
        onError(e.message);
    }
    finally {
        setBusy(false);
    } }
    return _jsxs("section", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("h2", { children: "Documents / Reprint" }), _jsx("p", { className: "muted", children: "Search a sale, repair, repair payment proof or credit settlement and record a reprint event." })] }), _jsx("button", { onClick: search, children: "Search" })] }), _jsxs("div", { className: "search-row", children: [_jsx("input", { value: q, onChange: e => setQ(e.target.value), onKeyDown: e => e.key === 'Enter' && search(), placeholder: "Invoice / Repair No / Proof No" }), _jsx("button", { onClick: search, children: "Find Document" })] }), last && _jsx("div", { className: "success-banner", children: last }), rows.length === 0 ? _jsx("p", { className: "muted", children: "No matching documents." }) : rows.map(r => _jsxs("div", { className: "claim-row", children: [_jsxs("span", { children: [_jsx("b", { children: r.document_type }), " \u00B7 ", r.document_no, _jsxs("small", { children: [r.document_datetime ? ` · ${new Date(r.document_datetime).toLocaleString()}` : '', " \u00B7 ", r.status] })] }), _jsx("button", { disabled: busy, onClick: () => reprint(r), children: "Reprint" })] }, `${r.document_type}-${r.document_id}`))] });
}
const Metric = ({ t, v, icon }) => _jsxs("div", { className: "metric metric-animated", children: [_jsxs("span", { children: [_jsx("i", { children: icon || '•' }), t] }), _jsx("b", { children: v })] });
function ItemsTab({ onError }) {
    return _jsxs("section", { className: "items-page", children: [_jsxs("div", { className: "glass panel page-intro rise-in", children: [_jsx("span", { className: "eyebrow", children: "INVENTORY MASTER" }), _jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("h2", { children: "Items & Item Master" }), _jsx("p", { className: "muted", children: "Create or edit items, barcodes, variants and compatibility. Buy cost is never entered here." })] }), _jsx("span", { className: "feature-badge", children: "FIFO \u2022 IMEI \u2022 BARCODE" })] })] }), _jsx(ItemMasterPanel, { onError: onError })] });
}
function ItemMasterPanel({ onError }) {
    const empty = { description: '', category_id: '', item_type_id: '', brand: '', model: '', master_sale_price: '', barcode: '' };
    const [q, setQ] = useState(''), [rows, setRows] = useState([]), [masters, setMasters] = useState({ categories: [], item_types: [] }), [form, setForm] = useState(empty), [editing, setEditing] = useState(), [busy, setBusy] = useState(false), [variantName, setVariantName] = useState(''), [variantValue, setVariantValue] = useState(''), [variants, setVariants] = useState([]), [warranty, setWarranty] = useState({ warranty_type: 'NONE', duration_value: '', custom_rule: '' });
    async function load() { try {
        setBusy(true);
        const [r, m] = await Promise.all([api(`/items/admin-list?q=${encodeURIComponent(q)}`), api('/items/masters')]);
        setRows(r);
        setMasters(m);
    }
    catch (e) {
        onError(e.message);
    }
    finally {
        setBusy(false);
    } }
    useEffect(() => { load(); }, []);
    function startNew() { setEditing(undefined); setForm(empty); setWarranty({ warranty_type: 'NONE', duration_value: '', custom_rule: '' }); setVariants([]); setVariantName(''); setVariantValue(''); }
    async function edit(x) { setEditing(x); setForm({ description: x.description, category_id: x.category_id, item_type_id: x.item_type_id, brand: x.brand || '', model: x.model || '', master_sale_price: x.master_sale_price == null ? '' : String(x.master_sale_price), barcode: '' }); setWarranty({ warranty_type: x.warranty_default?.warranty_type || 'NONE', duration_value: x.warranty_default?.duration_value == null ? '' : String(x.warranty_default.duration_value), custom_rule: x.warranty_default?.custom_rule || '' }); try {
        setVariants(await api(`/items/${x.item_id}/variants`));
    }
    catch {
        setVariants([]);
    } }
    async function save() { try {
        if (!form.description || !form.category_id || !form.item_type_id) {
            onError('Description, category and item type are required.');
            return;
        }
        const payload = { description: form.description, category_id: form.category_id, item_type_id: form.item_type_id, brand: form.brand || null, model: form.model || null, master_sale_price: form.master_sale_price || null, version: editing?.version };
        const r = editing ? await api(`/items/${editing.item_id}`, { method: 'PUT', body: JSON.stringify(payload) }) : await api('/items', { method: 'POST', body: JSON.stringify({ ...payload, barcode: form.barcode || null }) });
        const itemId = editing?.item_id || r.item_id;
        if (itemId) {
            await api(`/items/${itemId}/warranty-default`, { method: 'PUT', body: JSON.stringify({ warranty_type: warranty.warranty_type, duration_value: warranty.duration_value ? Number(warranty.duration_value) : null, custom_rule: warranty.custom_rule || null }) });
        }
        if (editing && form.barcode.trim())
            await api(`/items/${editing.item_id}/barcodes`, { method: 'POST', body: JSON.stringify({ barcode: form.barcode.trim(), is_primary: false }) });
        setForm(empty);
        setEditing(undefined);
        await load();
        alert(editing ? 'Item updated' : 'Item created');
    }
    catch (e) {
        onError(e.message);
    } }
    return _jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsx("h3", { children: "Item Master" }), _jsx("button", { disabled: busy, onClick: load, children: "Refresh" })] }), _jsxs("div", { className: "search-row", children: [_jsx("input", { placeholder: "Item code / description / brand / model", value: q, onChange: e => setQ(e.target.value), onKeyDown: e => e.key === 'Enter' && load() }), _jsx("button", { onClick: load, children: "Search" }), _jsx("button", { onClick: startNew, children: "New Item" })] }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { placeholder: "Description", value: form.description, onChange: e => setForm({ ...form, description: e.target.value }) }), _jsxs("select", { value: form.category_id, onChange: e => setForm({ ...form, category_id: e.target.value }), children: [_jsx("option", { value: "", children: "Category" }), masters.categories?.map((c) => _jsx("option", { value: c.id, children: c.name }, c.id))] }), _jsxs("select", { value: form.item_type_id, onChange: e => setForm({ ...form, item_type_id: e.target.value }), children: [_jsx("option", { value: "", children: "Item Type" }), masters.item_types?.map((t) => _jsx("option", { value: t.id, children: t.name }, t.id))] }), _jsx("input", { placeholder: "Brand", value: form.brand, onChange: e => setForm({ ...form, brand: e.target.value }) }), _jsx("input", { placeholder: "Model", value: form.model, onChange: e => setForm({ ...form, model: e.target.value }) }), _jsx("input", { type: "number", min: "0", step: "0.01", placeholder: "Master sale price", value: form.master_sale_price, onChange: e => setForm({ ...form, master_sale_price: e.target.value }) }), _jsx("input", { placeholder: "Barcode", value: form.barcode, onChange: e => setForm({ ...form, barcode: e.target.value }) }), _jsxs("select", { value: warranty.warranty_type, onChange: e => setWarranty({ ...warranty, warranty_type: e.target.value }), children: [_jsx("option", { children: "NONE" }), _jsx("option", { children: "DAYS" }), _jsx("option", { children: "MONTHS" }), _jsx("option", { children: "CHECKING ONLY" }), _jsx("option", { children: "CUSTOM" })] }), warranty.warranty_type === "DAYS" || warranty.warranty_type === "MONTHS" ? _jsx("input", { type: "number", min: "1", placeholder: "Warranty duration", value: warranty.duration_value, onChange: e => setWarranty({ ...warranty, duration_value: e.target.value }) }) : null, warranty.warranty_type === "CUSTOM" ? _jsx("input", { placeholder: "Custom warranty rule", value: warranty.custom_rule, onChange: e => setWarranty({ ...warranty, custom_rule: e.target.value }) }) : null, _jsx("button", { onClick: save, children: editing ? 'Save Item' : 'Create Item' }), editing && _jsxs(_Fragment, { children: [_jsx("input", { placeholder: "Variant / compatibility name", value: variantName, onChange: e => setVariantName(e.target.value) }), _jsx("input", { placeholder: "Variant value (e.g. Original / A12)", value: variantValue, onChange: e => setVariantValue(e.target.value) }), _jsx("button", { disabled: !variantName.trim() || !variantValue.trim(), onClick: async () => { try {
                                    const r = await api(`/items/${editing.item_id}/variants`, { method: 'POST', body: JSON.stringify({ name: variantName, value: variantValue }) });
                                    setVariants(v => v.concat(r));
                                    setVariantName('');
                                    setVariantValue('');
                                }
                                catch (e) {
                                    onError(e.message);
                                } }, children: "Add Variant" })] })] }), editing && variants.length > 0 && _jsxs("div", { className: "stock-row", children: [_jsx("span", { children: "Variants / Compatibility" }), _jsx("b", { children: variants.map(v => `${v.name}: ${v.value}`).join(' · ') })] }), _jsxs("div", { className: "stock-row", children: [_jsx("span", { children: "Categories" }), _jsx("b", { children: masters.categories?.length ?? 0 }), _jsx("span", { children: "Item Types" }), _jsx("b", { children: masters.item_types?.length ?? 0 })] }), rows.map(x => _jsxs("div", { className: "claim-row", children: [_jsxs("span", { children: [_jsx("b", { children: x.item_code }), " \u00B7 ", x.description, x.brand ? ` · ${x.brand}` : '', x.model ? ` · ${x.model}` : '', _jsxs("small", { children: [" \u00B7 ", x.is_active ? 'ACTIVE' : 'INACTIVE', " \u00B7 ", x.barcodes?.join(', ') || 'No barcode'] })] }), _jsxs("span", { children: [_jsx("b", { children: x.master_sale_price == null ? 'No master price' : `Rs. ${money(x.master_sale_price)}` }), _jsx("button", { onClick: () => edit(x), children: "Edit" })] })] }, x.item_id))] });
}
function AdminTab({ onError }) {
    const [roles, setRoles] = useState([]), [perms, setPerms] = useState([]), [users, setUsers] = useState([]), [targets, setTargets] = useState([]), [approvals, setApprovals] = useState([]), [expenses, setExpenses] = useState([]), [audit, setAudit] = useState([]), [targetHistory, setTargetHistory] = useState([]), [suppliers, setSuppliers] = useState([]), [supplierName, setSupplierName] = useState(''), [supplierContact, setSupplierContact] = useState(''), [supplierAddress, setSupplierAddress] = useState(''), [expenseCats, setExpenseCats] = useState([]), [expenseCatName, setExpenseCatName] = useState(''), [target, setTarget] = useState({ target_type: 'SALES_AMOUNT', target_value: '', period_type: 'DAILY', period_start: today(), period_end: today() });
    async function load() { try {
        const [r, p, u, t, a, e, au, h, sp, ec] = await Promise.all([api('/admin/roles'), api('/admin/permissions'), api('/admin/users'), api('/admin/targets'), api('/admin/approvals'), api('/admin/pending-expenses'), api('/admin/audit'), api('/reports/target-history', { method: 'POST', body: JSON.stringify({ start: '2000-01-01', end: '2100-12-31' }) }), api('/admin/suppliers'), api('/admin/expense-categories')]);
        setRoles(r);
        setPerms(p);
        setUsers(u);
        setTargets(t);
        setApprovals(a);
        setExpenses(e);
        setAudit(au);
        setTargetHistory(h);
        setSuppliers(sp);
        setExpenseCats(ec);
    }
    catch (e) {
        onError(e.message);
    } }
    useEffect(() => { load(); }, []);
    async function saveRole(r) { try {
        const admin_password = window.prompt('Admin password (re-authentication required)') || '';
        await api(`/admin/roles/${r.role_id}/permissions?admin_password=${encodeURIComponent(admin_password)}`, { method: 'PUT', body: JSON.stringify({ permission_codes: r.permissions }) });
        load();
    }
    catch (e) {
        onError(e.message);
    } }
    async function addTarget() { try {
        await api('/admin/targets', { method: 'POST', body: JSON.stringify({ ...target, target_value: String(target.target_value) }) });
        setTarget({ ...target, target_value: '' });
        load();
    }
    catch (e) {
        onError(e.message);
    } }
    async function addExpenseCategory() { if (!expenseCatName.trim())
        return onError('Expense category name is required.'); try {
        await api('/admin/expense-categories', { method: 'POST', body: JSON.stringify({ name: expenseCatName.trim() }) });
        setExpenseCatName('');
        load();
    }
    catch (e) {
        onError(e.message);
    } }
    async function addSupplier() { if (!supplierName.trim())
        return onError('Supplier name is required.'); try {
        await api('/admin/suppliers', { method: 'POST', body: JSON.stringify({ name: supplierName.trim(), contact_no: supplierContact.trim() || null, address: supplierAddress.trim() || null }) });
        setSupplierName('');
        setSupplierContact('');
        setSupplierAddress('');
        load();
    }
    catch (e) {
        onError(e.message);
    } }
    async function reviewExpense(id, approve) { try {
        await api(`/admin/expenses/${id}/decision?approve=${approve}&reason=${encodeURIComponent(approve ? 'Approved by Admin' : 'Rejected by Admin')}`, { method: 'POST' });
        load();
    }
    catch (e) {
        onError(e.message);
    } }
    async function reviewApproval(a, approve) { try {
        await api(`/operations/approvals/${a.approval_id}/review`, { method: 'POST', body: JSON.stringify({ approve, reject_reason: approve ? null : 'Rejected by Admin' }) });
        load();
    }
    catch (e) {
        onError(e.message);
    } }
    return _jsxs("section", { className: "admin-page", children: [_jsx("div", { className: "glass panel", children: _jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("h2", { children: "Admin / Controls" }), _jsx("p", { className: "muted", children: "Security, users, permissions, suppliers, targets and approvals." })] }), _jsx("button", { onClick: load, children: "Refresh" })] }) }), _jsx(CategoryTypeManager, { onError: onError }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Expense Categories" }), _jsx("p", { className: "muted", children: "Admin can add categories beyond the locked defaults." }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { placeholder: "New expense category", value: expenseCatName, onChange: e => setExpenseCatName(e.target.value) }), _jsx("button", { disabled: !expenseCatName.trim(), onClick: addExpenseCategory, children: "Add Expense Category" })] }), expenseCats.map(c => _jsx("span", { className: "feature-badge", style: { display: 'inline-block', margin: '4px' }, children: c.name }, c.id))] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Suppliers" }), _jsx("p", { className: "muted", children: "Admin-only supplier master. Supplier payment is not part of purchase entry." }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { placeholder: "Supplier name", value: supplierName, onChange: e => setSupplierName(e.target.value) }), _jsx("input", { placeholder: "Contact no.", value: supplierContact, onChange: e => setSupplierContact(e.target.value) }), _jsx("input", { placeholder: "Address (optional)", value: supplierAddress, onChange: e => setSupplierAddress(e.target.value) }), _jsx("button", { disabled: !supplierName.trim(), onClick: addSupplier, children: "Add Supplier" })] }), suppliers.map(s => _jsx("div", { className: "stock-row", children: _jsxs("span", { children: [_jsx("b", { children: s.name }), " \u00B7 ", s.contact_no || 'No contact', " \u00B7 ", s.address || 'No address'] }) }, s.supplier_id))] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Users" }), users.map(u => _jsx(UserRow, { user: u, onError: onError, onSaved: load }, u.user_id))] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Cashier Password Reset" }), _jsx(PasswordResetPanel, { users: users.filter((u) => u.role !== 'ADMIN'), onError: onError })] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Pending Expense Approvals" }), expenses.length === 0 ? _jsx("p", { className: "muted", children: "No pending expenses." }) : expenses.map(x => _jsxs("div", { className: "claim-row", children: [_jsxs("span", { children: [x.expense_date, " \u00B7 Rs. ", money(x.amount), " \u00B7 ", x.description || 'Expense'] }), _jsx("button", { onClick: () => reviewExpense(x.expense_id, true), children: "Approve" }), _jsx("button", { className: "danger-button", onClick: () => reviewExpense(x.expense_id, false), children: "Reject" })] }, x.expense_id))] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Approval Requests" }), approvals.filter(x => x.status === 'PENDING').length === 0 ? _jsx("p", { className: "muted", children: "No pending approval requests." }) : approvals.filter(x => x.status === 'PENDING').map(x => _jsxs("div", { className: "claim-row", children: [_jsxs("span", { children: [x.action_type, " \u00B7 ", x.requester_user_id] }), _jsx("button", { onClick: () => reviewApproval(x, true), children: "Approve" }), _jsx("button", { className: "danger-button", onClick: () => reviewApproval(x, false), children: "Reject" })] }, x.approval_id))] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Targets" }), _jsxs("div", { className: "form-grid compact", children: [_jsx("select", { value: target.target_type, onChange: e => setTarget({ ...target, target_type: e.target.value }), children: ['SALES_AMOUNT', 'ITEM_SALES_PROFIT', 'REPAIR_INCOME', 'REPAIR_PROFIT', 'BILLS_COUNT', 'ITEMS_SOLD_COUNT'].map(x => _jsx("option", { children: x }, x)) }), _jsx("input", { placeholder: "Target value", value: target.target_value, onChange: e => setTarget({ ...target, target_value: e.target.value }) }), _jsxs("select", { value: target.period_type, onChange: e => setTarget({ ...target, period_type: e.target.value }), children: [_jsx("option", { children: "DAILY" }), _jsx("option", { children: "MONTHLY" })] }), _jsx("input", { type: "date", value: target.period_start, onChange: e => setTarget({ ...target, period_start: e.target.value }) }), _jsx("input", { type: "date", value: target.period_end, onChange: e => setTarget({ ...target, period_end: e.target.value }) }), _jsx("button", { onClick: addTarget, children: "Add Target" })] }), targets.map(t => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [t.target_type, " \u00B7 ", t.period_start, " \u2192 ", t.period_end] }), _jsx("b", { children: t.target_value })] }, t.target_id)), _jsx("h4", { children: "Target Progress History" }), targetHistory.length === 0 ? _jsx("p", { className: "muted", children: "No target history." }) : targetHistory.map(t => _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [t.target_type, " \u00B7 ", t.period_start, " \u2192 ", t.period_end] }), _jsx("b", { children: t.progress == null ? 'Not calculated' : `${money(t.progress)}%` })] }, `history-${t.target_id}`))] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Stock Adjustment" }), _jsx(StockAdjustPanel, { onError: onError })] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Role Permissions" }), roles.filter(r => r.code !== 'ADMIN').map(r => _jsx(RoleEditor, { role: r, perms: perms, onSave: saveRole }, r.role_id))] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Recent Audit" }), audit.slice(0, 20).map(x => _jsxs("div", { className: "audit-row", children: [_jsxs("span", { children: [new Date(x.timestamp).toLocaleString(), " \u00B7 ", x.action_type, " \u00B7 ", x.entity_type] }), _jsx("small", { children: x.reason || '' })] }, x.audit_id))] })] });
}
function CategoryTypeManager({ onError }) { const [categoryName, setCategoryName] = useState(''), [typeName, setTypeName] = useState(''), [code, setCode] = useState(''), [serialized, setSerialized] = useState(false), [busy, setBusy] = useState(false); async function addCategory() { try {
    setBusy(true);
    await api('/items/categories', { method: 'POST', body: JSON.stringify({ name: categoryName }) });
    setCategoryName('');
    alert('Category added');
}
catch (e) {
    onError(e.message);
}
finally {
    setBusy(false);
} } async function addType() { try {
    setBusy(true);
    await api('/items/item-types', { method: 'POST', body: JSON.stringify({ code, name: typeName, is_serialized: serialized }) });
    setCode('');
    setTypeName('');
    setSerialized(false);
    alert('Item type added');
}
catch (e) {
    onError(e.message);
}
finally {
    setBusy(false);
} } return _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Category / Item Type Management" }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { placeholder: "New category name", value: categoryName, onChange: e => setCategoryName(e.target.value) }), _jsx("button", { disabled: busy || !categoryName.trim(), onClick: addCategory, children: "Add Category" }), _jsx("input", { placeholder: "Item type code", value: code, onChange: e => setCode(e.target.value) }), _jsx("input", { placeholder: "Item type name", value: typeName, onChange: e => setTypeName(e.target.value) }), _jsxs("label", { className: "check", children: [_jsx("input", { type: "checkbox", checked: serialized, onChange: e => setSerialized(e.target.checked) }), " Serialized / IMEI"] }), _jsx("button", { disabled: busy || !code.trim() || !typeName.trim(), onClick: addType, children: "Add Item Type" })] })] }); }
function UserRow({ user, onError, onSaved }) { const [limit, setLimit] = useState(String(user.discount_limit_percent ?? 0)); const [busy, setBusy] = useState(false); async function save() { if (busy)
    return; const n = Number(limit); if (!Number.isFinite(n) || n < 0 || n > 100)
    return onError('Discount limit must be between 0 and 100%.'); if (user.version == null)
    return onError('User version is missing; refresh before editing.'); try {
    setBusy(true);
    await api(`/admin/users/${user.user_id}/discount-limit`, { method: 'PUT', body: JSON.stringify({ discount_limit_percent: String(n), version: user.version }) });
    onSaved();
}
catch (e) {
    onError(e.message);
}
finally {
    setBusy(false);
} } return _jsxs("div", { className: "stock-row", children: [_jsxs("span", { children: [user.username, " \u00B7 ", user.display_name, " \u00B7 ", user.role, " \u00B7 v", user.version ?? '—'] }), _jsxs("span", { className: "inline-control", children: ["Discount limit % ", _jsx("input", { type: "number", min: "0", max: "100", step: "0.01", value: limit, onChange: e => setLimit(e.target.value) }), _jsx("button", { disabled: busy, onClick: save, children: busy ? 'Saving…' : 'Save' })] })] }); }
function StockAdjustPanel({ onError }) { const [item, setItem] = useState(''), [search, setSearch] = useState(''), [items, setItems] = useState([]), [qty, setQty] = useState(''), [reason, setReason] = useState(''); async function find() { try {
    setItems(await api(`/inventory/items/search?q=${encodeURIComponent(search.trim())}`));
}
catch (e) {
    onError(e.message);
} } async function save() { try {
    const admin_password = window.prompt('Admin password (re-authentication required)') || '';
    await api(`/stock-control/adjust?admin_password=${encodeURIComponent(admin_password)}`, { method: 'POST', body: JSON.stringify({ item_id: item, quantity_delta: String(qty), reason: reason.trim() }) });
    setQty('');
    setReason('');
    alert('Stock adjustment saved');
}
catch (e) {
    onError(e.message);
} } return _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { placeholder: "Search item / code", value: search, onChange: e => setSearch(e.target.value), onKeyDown: e => e.key === 'Enter' && find() }), _jsx("button", { onClick: find, children: "Find Item" }), _jsxs("select", { value: item, onChange: e => setItem(e.target.value), children: [_jsx("option", { value: "", children: "Select item" }), items.map((x) => _jsxs("option", { value: x.item_id, children: [x.item_code, " \u00B7 ", x.description, " \u00B7 Stock ", x.stock] }, x.item_id))] }), _jsx("input", { placeholder: "+/- Quantity", value: qty, onChange: e => setQty(e.target.value) }), _jsx("input", { placeholder: "Required reason", value: reason, onChange: e => setReason(e.target.value) }), _jsx("button", { onClick: save, children: "Adjust Stock" })] }); }
function RoleEditor({ role, perms, onSave }) { const [selected, setSelected] = useState(role.permissions); return _jsxs("div", { className: "role-editor", children: [_jsx("b", { children: role.name }), _jsx("div", { className: "permission-grid", children: perms.map(p => _jsxs("label", { children: [_jsx("input", { type: "checkbox", checked: selected.includes(p.code), onChange: e => setSelected(e.target.checked ? [...selected, p.code] : selected.filter(x => x !== p.code)) }), p.code] }, p.code)) }), _jsx("button", { onClick: () => onSave({ ...role, permissions: selected }), children: "Save Permissions" })] }); }
function PasswordResetPanel({ users, onError }) { const [uid, setUid] = useState(''), [adminPass, setAdminPass] = useState(''), [newPass, setNewPass] = useState(''); async function reset() { try {
    await api('/admin/users/reset-password', { method: 'POST', body: JSON.stringify({ user_id: uid, admin_password: adminPass, new_password: newPass }) });
    setAdminPass('');
    setNewPass('');
    alert('Password reset. Cashier must change password on next login.');
}
catch (e) {
    onError(e.message);
} } return _jsxs("div", { className: "form-grid compact", children: [_jsxs("select", { value: uid, onChange: e => setUid(e.target.value), children: [_jsx("option", { value: "", children: "Select cashier" }), users.map(u => _jsxs("option", { value: u.user_id, children: [u.username, " \u00B7 ", u.display_name] }, u.user_id))] }), _jsx("input", { type: "password", placeholder: "Admin password", value: adminPass, onChange: e => setAdminPass(e.target.value) }), _jsx("input", { type: "password", placeholder: "Temporary new password", value: newPass, onChange: e => setNewPass(e.target.value) }), _jsx("button", { disabled: !uid || !adminPass || !newPass, onClick: reset, children: "Reset Cashier Password" })] }); }
function BackupTab({ onError }) { const [rows, setRows] = useState([]), [busy, setBusy] = useState(false); async function load() { try {
    setRows(await api('/backup/points'));
}
catch (e) {
    onError(e.message);
} } useEffect(() => { load(); }, []); async function create() { try {
    setBusy(true);
    await api('/backup/create', { method: 'POST', body: JSON.stringify({ filename: `lovely-tech-${Date.now()}.ltbak` }) });
    await load();
    alert('Encrypted PostgreSQL backup created and verified.');
}
catch (e) {
    onError(e.message);
}
finally {
    setBusy(false);
} } async function verify(id) { try {
    await api(`/backup/verify/${id}`, { method: 'POST' });
    await load();
}
catch (e) {
    onError(e.message);
} } async function sync(id) { try {
    await api(`/backup/sync/${id}`, { method: 'POST' });
    await load();
}
catch (e) {
    onError(e.message);
} } return _jsxs("section", { className: "glass panel", children: [_jsx("h2", { children: "Backup / Restore" }), _jsx("p", { className: "muted", children: "Only VERIFIED backups are valid restore points. Google Drive sync is optional and shown separately." }), _jsxs("div", { className: "button-row", children: [_jsx("button", { disabled: busy, onClick: create, children: busy ? 'Creating verified backup…' : 'Create Verified PostgreSQL Backup' }), _jsx("button", { onClick: load, children: "Refresh" })] }), rows.map(r => _jsxs("div", { className: "claim-row", children: [_jsxs("span", { children: [_jsx("b", { children: r.filename }), " \u00B7 ", r.state, " \u00B7 ", r.sync_state || '—', " \u00B7 ", r.sha256?.slice(0, 12) || ''] }), _jsxs("span", { children: [_jsx("button", { onClick: () => verify(r.backup_id), children: "Verify" }), r.state === 'VERIFIED' && r.sync_state !== 'SYNCED' && _jsx("button", { onClick: () => sync(r.backup_id), children: "Sync Google Drive" }), r.state === 'VERIFIED' && _jsx("button", { onClick: async () => { if (!window.confirm('Restore this verified backup? Current database will be replaced after a safety backup.'))
                                return; const pw = window.prompt('Admin password') || ''; try {
                                await api(`/backup/restore/${r.backup_id}?confirm=true&admin_password=${encodeURIComponent(pw)}`, { method: 'POST' });
                                alert('Restore completed. Please log in again if the server session was reset.');
                            }
                            catch (e) {
                                onError(e.message);
                            } }, children: "Restore" })] })] }, r.backup_id))] }); }
