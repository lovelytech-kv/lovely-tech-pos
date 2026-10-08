import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from 'react';
import { AdminManualServerPanel } from '../components/AdminManualServerPanel';
const stateMessages = {
    UNINITIALIZED: {
        title: 'Welcome to Lovely Tech POS',
        description: 'This machine has not been set up yet. Starting automatic server discovery…',
        showRetry: false,
        showManual: false,
        adminOnly: false,
    },
    DISCOVERING: {
        title: 'Discovering POS server',
        description: 'Looking for the Lovely Tech POS server on the LAN…',
        showRetry: false,
        showManual: false,
        adminOnly: false,
    },
    SERVER_DETECTED: {
        title: 'Server found',
        description: 'A Lovely Tech POS server was detected. Verifying identity…',
        showRetry: false,
        showManual: false,
        adminOnly: false,
    },
    CLIENT_SETUP_REQUIRED: {
        title: 'Setup required',
        description: 'This client machine needs to be connected to a POS server. No server was found automatically.',
        showRetry: true,
        showManual: true,
        adminOnly: true,
    },
    NEW_SHOP_REQUIRED: {
        title: 'New shop setup required',
        description: 'The POS server has no shop configured yet. An Admin must provision a new shop on the server before this machine can continue.',
        showRetry: false,
        showManual: false,
        adminOnly: true,
    },
    EXISTING_SHOP_REQUIRED: {
        title: 'Existing shop setup required',
        description: 'The POS server must be linked to an existing shop. An Admin must select the shop on the server before this machine can continue.',
        showRetry: false,
        showManual: false,
        adminOnly: true,
    },
    RESTORE_REQUIRED: {
        title: 'Restore required',
        description: 'This server machine needs to be restored from a verified backup. An Admin must select the backup.',
        showRetry: false,
        showManual: false,
        adminOnly: true,
    },
    READY: {
        title: 'Ready',
        description: 'Machine is configured and ready.',
        showRetry: false,
        showManual: false,
        adminOnly: false,
    },
    SETUP_ERROR: {
        title: 'Setup error',
        description: 'An error occurred during setup. Please retry discovery or contact support.',
        showRetry: true,
        showManual: true,
        adminOnly: true,
    },
};
export function SetupRequired({ state, isAdmin, onRetryDiscovery, onConfigureManual, onBackToDiscovery, }) {
    const [showManualConfig, setShowManualConfig] = useState(false);
    const info = stateMessages[state];
    if (state === 'READY')
        return null;
    if (info.adminOnly && !isAdmin) {
        return (_jsx("div", { className: "discovery-overlay", children: _jsxs("div", { className: "discovery-card glass-card", children: [_jsx("div", { className: "discovery-spinner", "aria-hidden": "true" }), _jsx("h2", { children: "Setup in progress" }), _jsx("p", { className: "muted", children: "This machine requires Admin setup. Please wait for an Administrator to complete the configuration." })] }) }));
    }
    if (state === 'DISCOVERING' || state === 'UNINITIALIZED' || state === 'SERVER_DETECTED') {
        return (_jsx("div", { className: "discovery-overlay", children: _jsxs("div", { className: "discovery-card glass-card", children: [state === 'DISCOVERING' || state === 'UNINITIALIZED' ? (_jsx("div", { className: "discovery-spinner", "aria-hidden": "true" })) : (_jsx("div", { className: "status-good", style: { fontSize: '28px' }, children: "\u25CF" })), _jsx("h2", { children: info.title }), _jsx("p", { className: "muted", children: info.description })] }) }));
    }
    if (showManualConfig) {
        return (_jsx(AdminManualServerPanel, { onConfigured: onRetryDiscovery, onBack: () => setShowManualConfig(false), onRetry: onRetryDiscovery }));
    }
    return (_jsx("div", { className: "discovery-overlay", children: _jsxs("div", { className: "discovery-card glass-card", children: [_jsx("div", { className: "discovery-error-icon", "aria-hidden": "true", children: "!" }), _jsx("h2", { children: info.title }), _jsx("p", { className: "muted", children: info.description }), _jsxs("div", { className: "discovery-actions", children: [info.showRetry && (_jsx("button", { className: "primary", onClick: onRetryDiscovery, children: "Retry Discovery" })), info.showManual && (_jsx("button", { className: "ghost", onClick: () => setShowManualConfig(true), children: "Configure server manually" })), state === 'SETUP_ERROR' && (_jsx("button", { className: "ghost", onClick: onBackToDiscovery, children: "Back to discovery" }))] })] }) }));
}
