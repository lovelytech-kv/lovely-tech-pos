import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { login, API_BASE_URL } from '../../api/client';
export function Login({ onLogin }) {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    async function submit(e) {
        e.preventDefault();
        setError('');
        setBusy(true);
        try {
            onLogin(await login(username.trim(), password));
        }
        catch (err) {
            setError(err instanceof Error ? err.message : 'Login failed');
        }
        finally {
            setBusy(false);
        }
    }
    return _jsxs("div", { className: "login-page", children: [_jsxs("div", { className: "login-decoration", children: [_jsx("div", { className: "login-orbit one" }), _jsx("div", { className: "login-orbit two" }), _jsx("div", { className: "login-grid" })] }), _jsxs("div", { className: "login-brand-panel", children: [_jsx("div", { className: "brand-mark", children: "LT" }), _jsx("span", { className: "eyebrow", children: "LOVELY TECH" }), _jsxs("h1", { children: ["Run the shop.", _jsx("br", {}), _jsx("em", { children: "Simply." })] }), _jsx("p", { children: "Sales, stock, repairs, warranty and day-end control in one offline-first POS." }), _jsxs("div", { className: "login-feature-list", children: [_jsx("span", { children: "\u2713 Branch-aware inventory" }), _jsx("span", { children: "\u2713 Atomic sales & payments" }), _jsx("span", { children: "\u2713 Audit-ready history" })] })] }), _jsxs("form", { className: "login-card glass-card", onSubmit: submit, children: [_jsxs("div", { className: "login-card-head", children: [_jsxs("div", { children: [_jsx("span", { className: "eyebrow", children: "SECURE SIGN IN" }), _jsx("h2", { children: "Welcome back" }), _jsx("p", { children: "Use your Lovely Tech account to continue." })] }), _jsx("span", { className: "secure-dot", children: "\u25CF" })] }), _jsxs("label", { children: ["Username", _jsx("input", { autoFocus: true, autoComplete: "username", placeholder: "Enter username", value: username, onChange: e => setUsername(e.target.value) })] }), _jsxs("label", { children: ["Password", _jsx("input", { type: "password", autoComplete: "current-password", placeholder: "Enter password", value: password, onChange: e => setPassword(e.target.value) })] }), error && _jsx("div", { className: "error login-error", children: error }), _jsxs("button", { "aria-label": "Login", className: "login-submit", disabled: busy || !username.trim() || !password, children: [busy ? 'Signing in…' : 'Sign in to POS', " ", _jsx("span", { children: "\u2192" })] }), _jsxs("div", { className: "login-footer", children: [_jsx("span", { children: "Server" }), _jsx("b", { children: API_BASE_URL })] })] })] });
}
