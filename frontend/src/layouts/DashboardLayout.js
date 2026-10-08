import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useRef, useState } from 'react';
import { checkServerHealth } from '../api/client';
const primary = [
    ['Dashboard', 'Overview'], ['Sales', 'POS'], ['Items', 'Inventory'], ['Customers', 'Customers'],
    ['Repairs', 'Repairs'], ['Warranty', 'Warranty'], ['Stock', 'Stock'], ['Purchases', 'Purchases'],
    ['Cash/Day', 'Cash / Day'], ['Reports', 'Reports'],
];
const more = [['Returns', 'Returns'], ['Expenses', 'Expenses'], ['Documents', 'Documents'], ['Settings', 'Settings']];
const glyph = { Dashboard: '⌂', Sales: '▣', Items: '▤', Customers: '♙', Repairs: '⚒', Warranty: '✓', Stock: '▦', Purchases: '⇩', 'Cash/Day': '◉', Reports: '▥', Returns: '↩', Expenses: '¤', Documents: '▧', Settings: '⚙', Admin: '◆', Backup: '↥' };
export function DashboardLayout({ user, activeKey, onNavigate, onLogout, children }) {
    const [serverState, setServerState] = useState('checking');
    const searchRef = useRef(null);
    const isAdmin = user.role.toUpperCase() === 'ADMIN';
    useEffect(() => {
        const theme = (localStorage.getItem('ltpos_theme') || 'light');
        const accent = localStorage.getItem('ltpos_accent') || '#df3b32';
        const density = localStorage.getItem('ltpos_density') || 'comfortable';
        const resolved = theme === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : theme;
        document.documentElement.dataset.theme = resolved;
        document.documentElement.dataset.density = density;
        document.documentElement.style.setProperty('--accent', accent);
        const n = parseInt(accent.replace('#', ''), 16);
        document.documentElement.style.setProperty('--accent-rgb', `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`);
    }, []);
    useEffect(() => {
        let alive = true;
        const check = async () => {
            try {
                await checkServerHealth();
                if (alive)
                    setServerState('online');
            }
            catch {
                if (alive)
                    setServerState('offline');
            }
        };
        check();
        const timer = window.setInterval(check, 15000);
        const focusSearch = (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
                event.preventDefault();
                searchRef.current?.focus();
                searchRef.current?.select();
            }
        };
        window.addEventListener('keydown', focusSearch);
        return () => { alive = false; window.clearInterval(timer); window.removeEventListener('keydown', focusSearch); };
    }, []);
    const activeLabel = [...primary, ...more, ...(isAdmin ? [['Admin', 'Admin'], ['Backup', 'Backup']] : [])].find(([, key]) => key === activeKey)?.[0] ?? 'Lovely Tech POS';
    return (_jsxs("main", { className: "v0-shell", children: [_jsxs("aside", { className: "v0-sidebar glass-card", children: [_jsxs("button", { className: "v0-brand", onClick: () => onNavigate('Dashboard'), "aria-label": "Go to dashboard", children: [_jsx("span", { className: "brand-mark", children: "LT" }), _jsxs("span", { children: [_jsx("strong", { children: "Lovely Tech" }), _jsx("small", { children: "POS System" })] })] }), _jsxs("div", { className: "v0-sidebar-scroll", children: [_jsx("div", { className: "v0-sidebar-label", children: "Workspace" }), _jsx("nav", { className: "v0-nav", "aria-label": "Main navigation", children: primary.map(([key, label]) => _jsxs("button", { className: activeKey === key ? 'active' : '', onClick: () => onNavigate(key), children: [_jsx("span", { className: "nav-icon", children: glyph[key] }), _jsx("span", { children: label }), key === 'Sales' && _jsx("b", { className: "nav-badge", children: "POS" })] }, key)) }), _jsx("div", { className: "v0-sidebar-label more-label", children: "More" }), _jsxs("nav", { className: "v0-nav v0-nav-secondary", children: [more.map(([key, label]) => _jsxs("button", { className: activeKey === key ? 'active' : '', onClick: () => onNavigate(key), children: [_jsx("span", { className: "nav-icon", children: glyph[key] }), _jsx("span", { children: label })] }, key)), isAdmin && _jsxs(_Fragment, { children: [_jsxs("button", { className: activeKey === 'Admin' ? 'active' : '', onClick: () => onNavigate('Admin'), children: [_jsx("span", { className: "nav-icon", children: glyph.Admin }), _jsx("span", { children: "Admin" })] }), _jsxs("button", { className: activeKey === 'Backup' ? 'active' : '', onClick: () => onNavigate('Backup'), children: [_jsx("span", { className: "nav-icon", children: glyph.Backup }), _jsx("span", { children: "Backup" })] })] })] })] }), _jsxs("div", { className: "v0-sidebar-footer", children: [_jsxs("div", { className: `v0-connection connection-${serverState}`, "aria-live": "polite", children: [_jsx("span", { className: "online-dot" }), _jsxs("span", { children: [_jsx("b", { children: serverState === 'online' ? 'LAN connected' : serverState === 'offline' ? 'LAN offline' : 'Checking LAN…' }), _jsxs("small", { children: ["Branch ", user.branch_id] })] })] }), _jsxs("button", { className: "v0-user-mini", onClick: onLogout, children: [_jsx("span", { className: "avatar", children: user.display_name.slice(0, 2).toUpperCase() }), _jsxs("span", { children: [_jsx("b", { children: user.display_name }), _jsxs("small", { children: [user.role, " \u00B7 Logout"] })] }), _jsx("span", { className: "logout-arrow", children: "\u2197" })] })] })] }), _jsxs("section", { className: "v0-main", children: [_jsxs("header", { className: "v0-header glass-card", children: [_jsxs("div", { children: [_jsxs("span", { className: "breadcrumb", children: ["Lovely Tech ", _jsx("b", { children: "/" }), " ", activeLabel] }), _jsx("h1", { children: activeLabel })] }), _jsxs("div", { className: "v0-header-actions", children: [_jsxs("label", { className: "global-search", children: [_jsx("span", { children: "\u2315" }), _jsx("input", { ref: searchRef, "aria-label": "Quick search", placeholder: "Search products, customers, invoices...", onKeyDown: (e) => { if (e.key === 'Escape')
                                                    e.currentTarget.blur(); } }), _jsx("kbd", { children: "Ctrl K" })] }), _jsxs("span", { className: `header-status header-${serverState}`, "aria-live": "polite", children: [_jsx("i", { className: "online-dot" }), " ", serverState === 'online' ? 'Online' : serverState === 'offline' ? 'Offline' : 'Checking…'] }), _jsx("button", { className: "icon-button", "aria-label": "Notifications", children: "\u2662" }), _jsx("button", { className: "header-avatar", "aria-label": "Account", onClick: onLogout, children: user.display_name.slice(0, 1).toUpperCase() })] })] }), _jsx("div", { className: "v0-content", children: children })] })] }));
}
