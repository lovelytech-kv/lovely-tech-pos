import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { api } from '../../api/client';
export function WarrantyWorkspace({ isAdmin, onError }) {
    const [claims, setClaims] = useState([]);
    const [itemQuery, setItemQuery] = useState('');
    const [items, setItems] = useState([]);
    const [itemId, setItemId] = useState('');
    const [claimQuantity, setClaimQuantity] = useState('1');
    const [warrantyId, setWarrantyId] = useState('');
    const [claimNotes, setClaimNotes] = useState('');
    const [serial, setSerial] = useState('');
    const [warrantyNo, setWarrantyNo] = useState('');
    const [lookup, setLookup] = useState(null);
    const [startDate, setStartDate] = useState(today());
    const [warrantyType, setWarrantyType] = useState('DAYS');
    const [duration, setDuration] = useState('30');
    const [customRule, setCustomRule] = useState('');
    const [calculation, setCalculation] = useState(null);
    const [manualReference, setManualReference] = useState('');
    const [manualStart, setManualStart] = useState(today());
    const [manualExpiry, setManualExpiry] = useState('');
    const [manualDescription, setManualDescription] = useState('');
    const [manualCustomer, setManualCustomer] = useState('');
    const [manualNotes, setManualNotes] = useState('');
    const [outcomeQuantity, setOutcomeQuantity] = useState({});
    async function loadClaims() {
        try {
            setClaims(await api('/warranty/claims'));
        }
        catch (error) {
            onError(error.message);
        }
    }
    useEffect(() => { void loadClaims(); }, []);
    async function searchItems() {
        try {
            setItems(await api(`/inventory/items/search?q=${encodeURIComponent(itemQuery.trim())}`));
        }
        catch (error) {
            onError(error.message);
        }
    }
    async function calculate() {
        try {
            const params = new URLSearchParams({ start_date: startDate, warranty_type: warrantyType });
            if (warrantyType === 'DAYS' || warrantyType === 'MONTHS')
                params.set('duration_value', duration);
            if (warrantyType === 'CUSTOM')
                params.set('custom_rule', customRule);
            setCalculation(await api(`/warranty/calculator?${params.toString()}`));
        }
        catch (error) {
            onError(error.message);
        }
    }
    async function lookupSerial() {
        if (!serial.trim()) {
            onError('Enter a serial number or IMEI.');
            return;
        }
        try {
            setLookup(await api(`/warranty/serial-lookup?serial_number=${encodeURIComponent(serial.trim())}`));
        }
        catch (error) {
            onError(error.message);
        }
    }
    async function lookupWarranty() {
        if (!warrantyNo.trim()) {
            onError('Enter a warranty number.');
            return;
        }
        try {
            setLookup(await api(`/warranty/lookup?warranty_no=${encodeURIComponent(warrantyNo.trim())}`));
        }
        catch (error) {
            onError(error.message);
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
        }
        catch (error) {
            onError(error.message);
        }
    }
    async function decision(claim, path, body) {
        try {
            await api(`/warranty/claims/${encodeURIComponent(claim.claim_id)}/${path}`, {
                method: 'POST',
                body: JSON.stringify({ version: claim.version, ...body }),
            });
            await loadClaims();
        }
        catch (error) {
            onError(error.message);
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
        }
        catch (error) {
            onError(error.message);
        }
    }
    return (_jsxs("section", { className: "workspace", children: [_jsxs("div", { className: "split", children: [_jsxs("div", { className: "glass panel", children: [_jsx("div", { className: "section-head", children: _jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "WARRANTY" }), _jsx("h2", { children: "Warranty lookup" }), _jsx("p", { className: "muted", children: "Search a warranty number or serial/IMEI and show the exact stored warranty dates and status." })] }) }), _jsxs("div", { className: "search-row", children: [_jsx("input", { value: serial, onChange: (event) => setSerial(event.target.value), onKeyDown: (event) => { if (event.key === 'Enter')
                                            void lookupSerial(); }, placeholder: "Serial / IMEI" }), _jsx("button", { onClick: () => void lookupSerial(), children: "Search Serial" })] }), _jsxs("div", { className: "search-row", children: [_jsx("input", { value: warrantyNo, onChange: (event) => setWarrantyNo(event.target.value), onKeyDown: (event) => { if (event.key === 'Enter')
                                            void lookupWarranty(); }, placeholder: "Warranty number" }), _jsx("button", { onClick: () => void lookupWarranty(), children: "Search Warranty" })] }), lookup && (_jsxs("div", { className: "day-card", children: [_jsx("span", { children: "Warranty" }), _jsx("b", { children: lookup.warranty_no }), _jsx("span", { children: "Item" }), _jsxs("b", { children: [lookup.item_code || '—', " ", lookup.description ? `· ${lookup.description}` : ''] }), _jsx("span", { children: "Serial" }), _jsx("b", { children: lookup.serial_number || '—' }), _jsx("span", { children: "Type" }), _jsx("b", { children: lookup.warranty_type }), _jsx("span", { children: "Start" }), _jsx("b", { children: lookup.start_date }), _jsx("span", { children: "Expiry" }), _jsx("b", { children: lookup.expiry_date || '—' }), _jsx("span", { children: "Status" }), _jsx("b", { children: lookup.status })] }))] }), _jsxs("div", { className: "glass panel", children: [_jsx("div", { className: "section-head", children: _jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "WARRANTY RULES" }), _jsx("h2", { children: "Expiry calculator" }), _jsx("p", { className: "muted", children: "Use the same calendar warranty calculation as the backend before recording an exception." })] }) }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { type: "date", value: startDate, onChange: (event) => setStartDate(event.target.value) }), _jsxs("select", { value: warrantyType, onChange: (event) => setWarrantyType(event.target.value), children: [_jsx("option", { value: "NONE", children: "NONE" }), _jsx("option", { value: "DAYS", children: "DAYS" }), _jsx("option", { value: "MONTHS", children: "MONTHS" }), _jsx("option", { value: "CHECKING ONLY", children: "CHECKING ONLY" }), _jsx("option", { value: "CUSTOM", children: "CUSTOM" })] }), (warrantyType === 'DAYS' || warrantyType === 'MONTHS') && _jsx("input", { type: "number", min: "1", value: duration, onChange: (event) => setDuration(event.target.value), placeholder: "Duration" }), warrantyType === 'CUSTOM' && _jsx("input", { value: customRule, onChange: (event) => setCustomRule(event.target.value), placeholder: "Custom rule, e.g. 45 DAYS" }), _jsx("button", { onClick: () => void calculate(), children: "Calculate" })] }), calculation && _jsxs("div", { className: "success-banner", children: [calculation.status, " \u00B7 ", calculation.start_date, " \u2192 ", calculation.expiry_date || 'No expiry'] })] })] }), _jsxs("div", { className: "glass panel", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "WARRANTY CLAIMS" }), _jsx("h2", { children: "Create and manage claims" }), _jsx("p", { className: "muted", children: "Claims hold the reported quantity. Admin decisions are version-protected, so a stale screen cannot approve the same claim twice." })] }), _jsx("button", { className: "ghost", onClick: () => void loadClaims(), children: "Refresh" })] }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { value: itemQuery, onChange: (event) => setItemQuery(event.target.value), onKeyDown: (event) => { if (event.key === 'Enter')
                                    void searchItems(); }, placeholder: "Item code / barcode / description" }), _jsx("button", { onClick: () => void searchItems(), children: "Find Item" }), _jsxs("select", { value: itemId, onChange: (event) => setItemId(event.target.value), children: [_jsx("option", { value: "", children: "Select item" }), items.map((item) => _jsxs("option", { value: item.item_id, children: [item.item_code, " \u00B7 ", item.description] }, item.item_id))] }), _jsx("input", { type: "number", min: "0.001", step: "0.001", value: claimQuantity, onChange: (event) => setClaimQuantity(event.target.value), placeholder: "Quantity" }), _jsx("input", { value: warrantyId, onChange: (event) => setWarrantyId(event.target.value), placeholder: "Product warranty ID (optional)" }), _jsx("input", { value: claimNotes, onChange: (event) => setClaimNotes(event.target.value), placeholder: "Reported issue / claim notes" }), _jsx("button", { disabled: !itemId, onClick: () => void createClaim(), children: "Create Warranty Claim" })] }), _jsxs("div", { className: "list-stack", children: [claims.length === 0 && _jsx("div", { className: "empty-state", children: _jsx("span", { children: "No warranty claims found." }) }), claims.map((claim) => (_jsxs("div", { className: "claim-row", children: [_jsxs("div", { children: [_jsx("b", { children: claim.claim_no }), _jsxs("small", { children: ["Qty ", claim.quantity, " \u00B7 Version ", claim.version, claim.notes ? ` · ${claim.notes}` : ''] })] }), _jsx("span", { className: "status-pill", children: claim.admin_decision }), claim.replacement_outcome && _jsx("span", { className: "status-pill", children: claim.replacement_outcome }), isAdmin && claim.admin_decision === 'PENDING_ADMIN' && (_jsxs("div", { className: "button-row", children: [_jsx("button", { onClick: () => void decision(claim, 'supplier', { supplier_process: 'SUPPLIER_WARRANTY_CLAIM', notes: 'Approved supplier warranty claim' }), children: "Supplier Claim" }), _jsx("button", { className: "danger-button", onClick: () => void decision(claim, 'damage', { notes: 'Approved as damage/loss' }), children: "Damage / Loss" })] })), isAdmin && claim.admin_decision === 'SUPPLIER_WARRANTY_CLAIM' && !claim.replacement_outcome && (_jsxs("div", { className: "button-row", children: [_jsx("input", { type: "number", min: "0.001", step: "0.001", value: outcomeQuantity[claim.claim_id] ?? String(claim.quantity), onChange: (event) => setOutcomeQuantity((current) => ({ ...current, [claim.claim_id]: event.target.value })), "aria-label": `Supplier outcome quantity for ${claim.claim_no}` }), _jsx("button", { onClick: () => void decision(claim, 'supplier-outcome', { outcome: 'REPLACEMENT', quantity: outcomeQuantity[claim.claim_id] ?? String(claim.quantity), notes: 'Replacement received from supplier' }), children: "Replacement Received" }), _jsx("button", { className: "danger-button", onClick: () => void decision(claim, 'supplier-outcome', { outcome: 'SHOP_HELD_DAMAGE', quantity: outcomeQuantity[claim.claim_id] ?? String(claim.quantity), notes: 'Supplier rejected; shop-held item damaged/lost' }), children: "Shop Damage" }), _jsx("button", { onClick: () => void decision(claim, 'supplier-outcome', { outcome: 'CUSTOMER_KEEPS_ITEM', quantity: outcomeQuantity[claim.claim_id] ?? String(claim.quantity), notes: 'Customer keeps item' }), children: "Customer Keeps" })] }))] }, claim.claim_id)))] })] }), isAdmin && (_jsxs("div", { className: "glass panel", children: [_jsx("div", { className: "section-head", children: _jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "ADMIN EXCEPTION" }), _jsx("h2", { children: "Manual warranty registration" }), _jsx("p", { className: "muted", children: "For controlled manual-document exceptions only. Normal product warranties should originate from the sale transaction." })] }) }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { value: manualReference, onChange: (event) => setManualReference(event.target.value), placeholder: "Manual reference number" }), _jsx("input", { value: manualCustomer, onChange: (event) => setManualCustomer(event.target.value), placeholder: "Customer name (optional)" }), _jsx("input", { value: manualDescription, onChange: (event) => setManualDescription(event.target.value), placeholder: "Item description" }), _jsx("input", { type: "date", value: manualStart, onChange: (event) => setManualStart(event.target.value) }), _jsx("input", { type: "date", value: manualExpiry, onChange: (event) => setManualExpiry(event.target.value) }), _jsx("input", { value: manualNotes, onChange: (event) => setManualNotes(event.target.value), placeholder: "Exception notes" }), _jsx("button", { onClick: () => void manualRegister(), children: "Register Manual Warranty" })] })] }))] }));
}
function today() {
    return new Date().toISOString().slice(0, 10);
}
