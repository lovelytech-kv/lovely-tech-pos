import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
const DENOMS = [5000, 2000, 1000, 500, 100, 50, 20];
const today = () => new Date().toISOString().slice(0, 10);
export function DayEnd({ isAdmin = false, onError }) {
    const [status, setStatus] = useState(null);
    const [backup, setBackup] = useState(null);
    const [counts, setCounts] = useState({});
    const [opening, setOpening] = useState('');
    const [openingDenoms, setOpeningDenoms] = useState({});
    const [reason, setReason] = useState('');
    const [note, setNote] = useState('');
    const [reload, setReload] = useState('');
    const [reloadProvider, setReloadProvider] = useState('Dialog');
    const [cashIn, setCashIn] = useState('');
    const [busy, setBusy] = useState(false);
    const [cashCountStarted, setCashCountStarted] = useState(false);
    const [correctionCash, setCorrectionCash] = useState('');
    const [correctionReason, setCorrectionReason] = useState('');
    const [correctionDenoms, setCorrectionDenoms] = useState({});
    const counted = useMemo(() => DENOMS.reduce((sum, d) => sum + d * Number(counts[String(d)] || 0), 0), [counts]);
    const openingCounted = useMemo(() => DENOMS.reduce((sum, d) => sum + d * Number(openingDenoms[String(d)] || 0), 0), [openingDenoms]);
    async function load() {
        try {
            const [day, back] = await Promise.all([api('/operations/day/status'), api('/backup/status')]);
            setStatus(day);
            setBackup(back);
        }
        catch (e) {
            onError?.(e.message);
        }
    }
    useEffect(() => { load(); }, []);
    function setDenom(target, d, value) {
        const clean = value.replace(/[^0-9]/g, '');
        if (target === 'open')
            setOpeningDenoms(prev => ({ ...prev, [String(d)]: clean }));
        else {
            setCashCountStarted(true);
            setCounts(prev => ({ ...prev, [String(d)]: clean }));
        }
    }
    async function startDay() {
        if (busy)
            return;
        const openingCash = opening || String(openingCounted);
        if (Number(openingCash) < 0)
            return onError?.('Opening cash cannot be negative.');
        if (Math.abs(Number(openingCash) - openingCounted) > 0.0001)
            return onError?.('Opening cash must equal the denomination total.');
        try {
            setBusy(true);
            await api('/operations/day/start', { method: 'POST', body: JSON.stringify({ business_date: today(), opening_cash: openingCash, denominations: Object.fromEntries(DENOMS.map(d => [String(d), Number(openingDenoms[String(d)] || 0)])) }) });
            await load();
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    async function shiftEnd() {
        if (!status?.day_session_id || busy)
            return;
        try {
            setBusy(true);
            await api('/operations/day/shift-end', { method: 'POST', body: JSON.stringify({ start: status.business_date, end: status.business_date }) });
            await load();
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    async function continueBusiness() {
        if (!isAdmin || !status?.business_date || busy)
            return;
        try {
            setBusy(true);
            await api('/operations/day/continue', { method: 'POST', body: JSON.stringify({ start: status.business_date, end: status.business_date }) });
            await load();
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    async function addReload() {
        if (!status?.day_session_id || !reload || busy)
            return;
        try {
            setBusy(true);
            await api('/operations/day/reload', { method: 'POST', body: JSON.stringify({ day_session_id: status.day_session_id, provider: reloadProvider, amount: reload }) });
            setReload('');
            await load();
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    async function addCashIn() {
        if (!cashIn || busy)
            return;
        try {
            setBusy(true);
            await api('/operations/day/cash-in', { method: 'POST', body: JSON.stringify({ amount: cashIn, note: 'POS cash-in' }) });
            setCashIn('');
            await load();
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    async function dayEnd() {
        if (!status?.day_session_id || busy)
            return;
        if (!reason.trim())
            return onError?.('Day End reason is required.');
        if (!cashCountStarted)
            return onError?.('Enter the physical cash denominations before Day End. Zero cash is allowed if intentionally counted.');
        try {
            setBusy(true);
            await api(`/operations/day/${status.day_session_id}/end`, { method: 'POST', body: JSON.stringify({ actual_cash: String(counted), denominations: Object.fromEntries(DENOMS.map(d => [String(d), Number(counts[String(d)] || 0)])), reason: reason.trim(), note: note.trim() || null, version: status.version }) });
            setCounts({});
            setCashCountStarted(false);
            setReason('');
            setNote('');
            await load();
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    async function correctOpening() {
        if (!isAdmin || !status?.day_session_id || busy)
            return;
        const denomTotal = DENOMS.reduce((sum, d) => sum + d * Number(correctionDenoms[String(d)] || 0), 0);
        if (!correctionCash || Number(correctionCash) < 0 || Math.abs(denomTotal - Number(correctionCash)) > 0.0001)
            return onError?.('Opening cash must equal the denomination total.');
        if (!correctionReason.trim())
            return onError?.('Opening correction reason is required.');
        if (status.version == null)
            return onError?.('Day version is missing; refresh before correcting opening cash.');
        const password = window.prompt('Admin password (re-authentication required)') || '';
        if (!password)
            return;
        try {
            setBusy(true);
            await api(`/operations/day/opening-correction?admin_password=${encodeURIComponent(password)}`, { method: 'POST', body: JSON.stringify({ day_session_id: status.day_session_id, opening_cash: correctionCash, denominations: Object.fromEntries(DENOMS.map(d => [String(d), Number(correctionDenoms[String(d)] || 0)])), reason: correctionReason.trim(), version: status.version }) });
            setCorrectionCash('');
            setCorrectionReason('');
            setCorrectionDenoms({});
            await load();
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    async function reopen() {
        if (!isAdmin || !status?.business_date || busy)
            return;
        const password = window.prompt('Admin password (re-authentication required)') || '';
        if (!password)
            return;
        try {
            setBusy(true);
            await api(`/operations/day/reopen?admin_password=${encodeURIComponent(password)}`, { method: 'POST', body: JSON.stringify({ start: status.business_date, end: status.business_date }) });
            await load();
        }
        catch (e) {
            onError?.(e.message);
        }
        finally {
            setBusy(false);
        }
    }
    const closed = status?.status === 'CLOSED';
    const open = Boolean(status?.day_session_id) && (status?.status === 'OPEN' || status?.status === 'SHIFT_ENDED');
    return _jsxs("section", { className: "glass panel day-end-card", children: [_jsxs("div", { className: "section-head", children: [_jsxs("div", { children: [_jsx("h2", { children: "Cash / Day Start \u00B7 Shift End \u00B7 Day End" }), _jsx("p", { className: "muted", children: "One workflow for the physical cash drawer and business-day lifecycle." })] }), _jsx("button", { onClick: load, children: "Refresh" })] }), _jsxs("div", { className: "day-card", children: [_jsx("span", { children: "Business Date" }), _jsx("b", { children: status?.business_date || today() }), _jsx("span", { children: "Status" }), _jsx("b", { children: status?.status || 'NOT_STARTED' }), _jsx("span", { children: "Expected Cash" }), _jsxs("b", { children: ["Rs. ", Number(status?.expected_cash || 0).toFixed(2)] }), _jsx("span", { children: "Live Difference" }), _jsxs("b", { children: ["Rs. ", (counted - Number(status?.expected_cash || 0)).toFixed(2)] }), _jsx("span", { children: "Backup" }), _jsxs("b", { children: [backup?.status || '—', backup?.last_backup_time ? ` · ${new Date(backup.last_backup_time).toLocaleString()}` : ''] })] }), !status?.day_session_id && _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Day Start" }), _jsx("div", { className: "form-grid compact", children: _jsxs("label", { children: ["Opening Cash", _jsx("input", { type: "number", min: "0", step: "0.01", value: opening, onChange: e => setOpening(e.target.value), placeholder: openingCounted.toFixed(2) })] }) }), _jsx("div", { className: "denomination-grid", children: DENOMS.map(d => _jsxs("label", { children: [_jsxs("span", { children: ["Rs. ", d] }), _jsx("input", { inputMode: "numeric", type: "number", min: "0", step: "1", value: openingDenoms[String(d)] || '', onChange: e => setDenom('open', d, e.target.value), placeholder: "0" }), _jsxs("small", { children: ["\u00D7 Rs. ", d * Number(openingDenoms[String(d)] || 0)] })] }, `open-${d}`)) }), _jsxs("div", { className: "cash-total-box", children: [_jsx("span", { children: "Denomination Total" }), _jsxs("strong", { children: ["Rs. ", openingCounted.toFixed(2)] })] }), _jsx("button", { disabled: busy, onClick: startDay, children: busy ? 'Starting…' : 'Start Day' })] }), open && _jsxs(_Fragment, { children: [isAdmin && _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Admin \u00B7 Opening Cash Correction" }), _jsx("p", { className: "muted", children: "Use only when the recorded Day Start opening cash is wrong. Every correction is re-authenticated and audited." }), _jsxs("div", { className: "form-grid compact", children: [_jsx("input", { type: "number", min: "0", step: "0.01", placeholder: "Correct opening cash", value: correctionCash, onChange: e => setCorrectionCash(e.target.value) }), _jsx("input", { placeholder: "Correction reason", value: correctionReason, onChange: e => setCorrectionReason(e.target.value) })] }), _jsx("div", { className: "denomination-grid", children: DENOMS.map(d => _jsxs("label", { children: [_jsxs("span", { children: ["Rs. ", d] }), _jsx("input", { inputMode: "numeric", type: "number", min: "0", step: "1", value: correctionDenoms[String(d)] || '', onChange: e => setCorrectionDenoms(prev => ({ ...prev, [String(d)]: e.target.value })) })] }, `correct-${d}`)) }), _jsxs("div", { className: "cash-total-box", children: [_jsx("span", { children: "Corrected denomination total" }), _jsxs("strong", { children: ["Rs. ", DENOMS.reduce((sum, d) => sum + d * Number(correctionDenoms[String(d)] || 0), 0).toFixed(2)] })] }), _jsx("button", { disabled: busy || !correctionCash || !correctionReason.trim(), onClick: correctOpening, children: "Correct Opening Cash" })] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "During Business" }), _jsxs("div", { className: "form-grid compact", children: [_jsxs("select", { value: reloadProvider, onChange: e => setReloadProvider(e.target.value), children: [_jsx("option", { children: "Dialog" }), _jsx("option", { children: "Airtel" }), _jsx("option", { children: "Mobitel" }), _jsx("option", { children: "Hutch" })] }), _jsx("input", { type: "number", min: "0.01", step: "0.01", placeholder: "Day-End Reload", value: reload, onChange: e => setReload(e.target.value) }), _jsx("button", { disabled: busy || !reload, onClick: addReload, children: "Add Reload" }), _jsx("input", { type: "number", min: "0.01", step: "0.01", placeholder: "Other Cash In", value: cashIn, onChange: e => setCashIn(e.target.value) }), _jsx("button", { disabled: busy || !cashIn, onClick: addCashIn, children: "Add Cash In" })] }), _jsx("p", { className: "muted", children: "Reload is recorded once for Day End. Other Cash In is a separate cash transaction." })] }), _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Physical Cash Count" }), _jsx("div", { className: "denomination-grid", children: DENOMS.map(d => _jsxs("label", { children: [_jsxs("span", { children: ["Rs. ", d] }), _jsx("input", { inputMode: "numeric", type: "number", min: "0", step: "1", value: counts[String(d)] || '', onChange: e => setDenom('actual', d, e.target.value), placeholder: "0" }), _jsxs("small", { children: ["\u00D7 Rs. ", d * Number(counts[String(d)] || 0)] })] }, d)) }), _jsxs("div", { className: "cash-total-box", children: [_jsx("span", { children: "Actual Cash" }), _jsxs("strong", { children: ["Rs. ", counted.toFixed(2)] })] }), _jsxs("label", { className: "wide-field", children: ["Mandatory Day End Reason", _jsx("textarea", { value: reason, onChange: e => setReason(e.target.value), placeholder: "Explain any difference or closing note" })] }), _jsxs("label", { className: "wide-field", children: ["Optional Note", _jsx("textarea", { value: note, onChange: e => setNote(e.target.value) })] }), _jsxs("div", { className: "form-actions", children: [_jsx("button", { disabled: busy || !cashCountStarted || !reason.trim(), onClick: dayEnd, children: busy ? 'Closing…' : 'Complete Day End' }), status?.status === 'OPEN' && _jsx("button", { className: "ghost", disabled: busy, onClick: shiftEnd, children: "Cashier Shift End" })] })] }), status?.status === 'SHIFT_ENDED' && isAdmin && _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Continue Today Business" }), _jsx("p", { className: "muted", children: "Admin can continue the same business day within the allowed window." }), _jsx("button", { disabled: busy, onClick: continueBusiness, children: "Continue Today Business" })] })] }), closed && isAdmin && _jsxs("div", { className: "glass panel", children: [_jsx("h3", { children: "Admin Reopen" }), _jsx("p", { className: "muted", children: "Reopening is a critical Admin action and requires re-authentication." }), _jsx("button", { disabled: busy, onClick: reopen, children: "Reopen Closed Day" })] })] });
}
