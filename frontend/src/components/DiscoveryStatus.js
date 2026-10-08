import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { ensureApiBaseResolved, resetApiBaseResolution } from '../api/client';
export function DiscoveryStatus({ onReady, onConfigureManual }) {
    const [phase, setPhase] = useState('discovering');
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    async function attempt() {
        setBusy(true);
        setError(null);
        try {
            await ensureApiBaseResolved();
            setPhase('ready');
            onReady();
        }
        catch (err) {
            const discoveryError = (err instanceof Error ? err : new Error(String(err)));
            if (!discoveryError.code)
                discoveryError.code = 'ALL_UNREACHABLE';
            discoveryError.candidatesTried = discoveryError.candidatesTried ?? 0;
            setError(discoveryError);
            setPhase('failed');
        }
        finally {
            setBusy(false);
        }
    }
    useEffect(() => {
        let alive = true;
        attempt();
        return () => { alive = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    async function retry() {
        try {
            await resetApiBaseResolution();
        }
        catch {
            // resetApiBaseResolution already re-resolves; attempt() below covers the retry outcome.
        }
        await attempt();
    }
    if (phase === 'ready')
        return null;
    return (_jsx("div", { className: "discovery-overlay", children: _jsx("div", { className: "discovery-card glass-card", children: phase === 'discovering' ? (_jsxs(_Fragment, { children: [_jsx("div", { className: "discovery-spinner", "aria-hidden": "true" }), _jsx("h2", { children: "Discovering POS server" }), _jsx("p", { className: "muted", children: "Looking for the Lovely Tech POS server on the LAN\u2026" })] })) : (_jsxs(_Fragment, { children: [_jsx("div", { className: "discovery-error-icon", "aria-hidden": "true", children: "!" }), _jsx("h2", { children: "POS server not found" }), _jsxs("p", { className: "muted", children: ["Automatic LAN discovery could not verify a Lovely Tech POS server.", error?.code === 'NO_SERVERS'
                                ? ' No advertised servers were found on the network.'
                                : error?.code === 'IDENTITY_MISMATCH'
                                    ? ' A reachable server did not identify itself as a Lovely Tech POS server.'
                                    : ' Check that the server laptop is on and on the same LAN.'] }), _jsxs("div", { className: "discovery-actions", children: [_jsx("button", { className: "primary", disabled: busy, onClick: retry, children: busy ? 'Retrying…' : 'Retry Discovery' }), _jsx("button", { className: "ghost", disabled: busy, onClick: onConfigureManual, children: "Configure server manually" })] })] })) }) }));
}
