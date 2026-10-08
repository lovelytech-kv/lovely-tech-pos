import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { configureManualServer } from '../api/client';
export function AdminManualServerPanel({ onConfigured, onBack, onRetry, }) {
    const [input, setInput] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const [verifying, setVerifying] = useState(false);
    const [identity, setIdentity] = useState(null);
    async function submit(e) {
        e.preventDefault();
        setError('');
        setIdentity(null);
        if (!input.trim()) {
            setError('Enter a server URL or host:port.');
            return;
        }
        setBusy(true);
        setVerifying(true);
        try {
            const result = await configureManualServer(input);
            setIdentity(result.identity ?? null);
            setBusy(false);
            onConfigured();
        }
        catch (err) {
            const message = err instanceof Error ? err.message : 'Manual configuration failed.';
            setError(message);
            setBusy(false);
        }
        finally {
            setVerifying(false);
        }
    }
    return (_jsx("div", { className: "discovery-overlay", children: _jsxs("div", { className: "discovery-card glass-card admin-manual-panel", children: [_jsxs("div", { className: "discovery-panel-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "ADMIN \u00B7 SERVER SETUP" }), _jsx("h2", { children: "Manual server configuration" }), _jsx("p", { className: "muted", children: "Automatic discovery failed. Enter the POS server address. This control is Admin-only." })] }), _jsx("button", { className: "ghost", onClick: onBack, children: "\u2190 Back" })] }), _jsxs("form", { className: "manual-form", onSubmit: submit, children: [_jsxs("label", { children: ["Server address", _jsx("input", { autoFocus: true, placeholder: "http://192.168.1.50:8000 or 192.168.1.50:8000", value: input, onChange: e => setInput(e.target.value), spellCheck: false })] }), _jsx("small", { className: "muted", children: "Enter a full URL or host:port. A reachable HTTP response alone is not enough." }), error && _jsx("div", { className: "error manual-error", role: "alert", children: error }), identity && (_jsxs("div", { className: "manual-verified", children: [_jsx("span", { className: "status-good", children: "\u25CF Verified Lovely Tech POS server" }), _jsx("div", { className: "identity-grid", children: ['product', 'instance_id', 'protocol_version', 'api_version', 'app_version', 'branch_code'].map(field => (_jsxs("div", { children: [_jsx("small", { className: "muted", children: field }), _jsx("b", { children: identity[field] || '—' })] }, field))) })] })), _jsxs("div", { className: "manual-actions", children: [_jsx("button", { className: "primary", type: "submit", disabled: busy || verifying, children: verifying ? 'Verifying…' : busy ? 'Saving…' : 'Connect to server' }), _jsx("button", { className: "ghost", type: "button", disabled: busy, onClick: onBack, children: "Cancel" })] })] }), _jsx("div", { className: "manual-footer", children: _jsx("button", { className: "ghost", onClick: () => { onRetry().catch(() => { }); }, children: "Retry automatic discovery" }) })] }) }));
}
