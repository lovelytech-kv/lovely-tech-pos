import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { currentUser, logout, ensureApiBaseResolved, resetApiBaseResolution } from './api/client';
import { Login } from './features/auth/Login';
import { POSHome } from './features/pos/POSHome';
import { DiscoveryStatus } from './components/DiscoveryStatus';
import { AdminManualServerPanel } from './components/AdminManualServerPanel';
import { SetupRequired } from './components/SetupRequired';
import { isTauriEnvironment } from './services/discovery';
import { getResolvedServerIdentity } from './api/client';
import { getOrCreateMachineConfig, setSetupState, clearTransientSetupState, loadMachineConfig, applyVerifiedServerToClient, computeClientSetupState, isReadySetupState, requiresAdminSetup, isTransientSetupState, } from './services/machine-config';
import './styles.css';
// Shows the real error instead of a blank white screen, so problems can be reported and fixed quickly.
class ErrorBoundary extends React.Component {
    state = { error: null };
    static getDerivedStateFromError(error) { return { error }; }
    render() {
        if (!this.state.error)
            return this.props.children;
        const e = this.state.error;
        return (_jsxs("div", { style: { padding: 24, color: '#fff', background: '#111', minHeight: '100vh', fontFamily: 'sans-serif' }, children: [_jsx("h2", { style: { color: '#ff4d4d' }, children: "Something went wrong" }), _jsx("p", { children: "Please send a photo/screenshot of this screen to the developer." }), _jsxs("pre", { style: { whiteSpace: 'pre-wrap', background: '#222', padding: 12, borderRadius: 8 }, children: [e.message, '\n\n', (e.stack || '').slice(0, 1500)] }), _jsx("button", { onClick: () => { logout(); window.location.reload(); }, children: "Clear saved session and reload" })] }));
    }
}
function App() {
    const [user, setUser] = useState(currentUser());
    const [bootPhase, setBootPhase] = useState('discovering');
    const [showManualConfig, setShowManualConfig] = useState(false);
    const [machineRole, setMachineRoleState] = useState(null);
    const [machineConfig, setMachineConfig] = useState(null);
    const [setupState, setSetupStateLocal] = useState(null);
    useEffect(() => {
        const h = () => { logout(); setUser(null); };
        window.addEventListener('ltpos:session-expired', h);
        return () => window.removeEventListener('ltpos:session-expired', h);
    }, []);
    // Machine-role foundation: in a Tauri build the app is always a CLIENT.
    // In browser dev mode there is no machine role; we skip persistence.
    useEffect(() => {
        if (!isTauriEnvironment()) {
            setMachineRoleState(null);
            setSetupStateLocal(null);
            return;
        }
        const config = getOrCreateMachineConfig('CLIENT');
        setMachineRoleState(config.machine_role);
        setMachineConfig(config);
        setSetupStateLocal(config.setup_state);
    }, []);
    // Applies the verified server response to the CLIENT machine configuration.
    // Only a verified /discovery/info response can move the client to READY;
    // NEW_SHOP_REQUIRED / EXISTING_SHOP_REQUIRED mean the client waits for the
    // server Admin - the client never provisions the server itself.
    const applyVerifiedServerState = () => {
        if (!isTauriEnvironment())
            return;
        const identity = getResolvedServerIdentity();
        const updated = applyVerifiedServerToClient(identity);
        if (updated) {
            setMachineConfig(updated);
            setSetupStateLocal(updated.setup_state);
        }
    };
    // Startup discovery runs once on mount. It does not block browser development:
    // in a non-Tauri environment ensureApiBaseResolved resolves to /api/v1 immediately.
    useEffect(() => {
        let alive = true;
        (async () => {
            try {
                await ensureApiBaseResolved();
                if (alive) {
                    setBootPhase('ready');
                    applyVerifiedServerState();
                }
            }
            catch (err) {
                if (alive) {
                    setBootPhase('failed');
                    // On discovery failure for a CLIENT, transition to appropriate error/setup state
                    if (isTauriEnvironment()) {
                        const current = loadMachineConfig();
                        if (current?.machine_role === 'CLIENT') {
                            const error = err;
                            let result = 'error';
                            if (error.code === 'IDENTITY_MISMATCH')
                                result = 'identity_mismatch';
                            else if (error.code === 'NO_SERVERS')
                                result = 'no_servers';
                            else if (error.code === 'ALL_UNREACHABLE')
                                result = 'all_unreachable';
                            const nextState = computeClientSetupState(current.setup_state, result);
                            setSetupState(nextState);
                            setSetupStateLocal(nextState);
                            setMachineConfig(prev => (prev ? { ...prev, setup_state: nextState } : prev));
                        }
                    }
                }
            }
        })();
        return () => { alive = false; };
    }, []);
    const handleRetryDiscovery = async () => {
        try {
            await resetApiBaseResolution();
            setBootPhase('ready');
            applyVerifiedServerState();
        }
        catch (err) {
            setBootPhase('failed');
            if (isTauriEnvironment()) {
                const current = loadMachineConfig();
                if (current?.machine_role === 'CLIENT') {
                    const error = err;
                    let result = 'error';
                    if (error.code === 'IDENTITY_MISMATCH')
                        result = 'identity_mismatch';
                    else if (error.code === 'NO_SERVERS')
                        result = 'no_servers';
                    else if (error.code === 'ALL_UNREACHABLE')
                        result = 'all_unreachable';
                    const nextState = computeClientSetupState(current.setup_state, result);
                    setSetupState(nextState);
                    setSetupStateLocal(nextState);
                    setMachineConfig(prev => (prev ? { ...prev, setup_state: nextState } : prev));
                }
            }
        }
    };
    const handleConfigureManual = () => {
        setShowManualConfig(true);
        setBootPhase('failed');
    };
    const handleBackToDiscovery = () => {
        setShowManualConfig(false);
        setBootPhase('failed');
    };
    // If we're in a transient discovery state, clear it on successful boot
    if (bootPhase === 'ready' && machineConfig && isTransientSetupState(machineConfig.setup_state)) {
        clearTransientSetupState();
    }
    // Show discovery status during boot
    if (bootPhase === 'discovering') {
        return (_jsx(DiscoveryStatus, { onReady: () => setBootPhase('ready'), onConfigureManual: handleConfigureManual }));
    }
    // Show manual config or failed state
    if (bootPhase === 'failed' || showManualConfig) {
        return (_jsx(AdminManualServerPanel, { onConfigured: () => {
                setShowManualConfig(false);
                setBootPhase('ready');
                // The manual server was verified through /discovery/info: its
                // setup_state drives the client state exactly like automatic discovery.
                applyVerifiedServerState();
            }, onBack: () => {
                setShowManualConfig(false);
                setBootPhase('failed');
            }, onRetry: handleRetryDiscovery }));
    }
    // At this point, bootPhase is 'ready'. Check setup state for Tauri environments.
    if (isTauriEnvironment() && machineRole) {
        const config = loadMachineConfig();
        const currentSetupState = config?.setup_state ?? 'UNINITIALIZED';
        // For CLIENT machines, show setup-required UI if not READY
        if (machineRole === 'CLIENT' && !isReadySetupState(currentSetupState)) {
            const isAdmin = user?.role.toUpperCase() === 'ADMIN';
            return (_jsx(SetupRequired, { state: currentSetupState, isAdmin: isAdmin, onRetryDiscovery: handleRetryDiscovery, onConfigureManual: handleConfigureManual, onBackToDiscovery: handleBackToDiscovery }));
        }
        // For SERVER machines (not implemented in this packet, but reserved)
        if (machineRole === 'SERVER' && !isReadySetupState(currentSetupState)) {
            const isAdmin = user?.role.toUpperCase() === 'ADMIN';
            if (requiresAdminSetup(currentSetupState) && !isAdmin) {
                return (_jsx(SetupRequired, { state: currentSetupState, isAdmin: false, onRetryDiscovery: handleRetryDiscovery, onConfigureManual: handleConfigureManual, onBackToDiscovery: handleBackToDiscovery }));
            }
            // Admin would see the setup flow here (future packets)
        }
    }
    // Normal authenticated flow
    return user ? (_jsx(POSHome, { user: user, onLogout: () => setUser(null) })) : (_jsx(Login, { onLogin: setUser }));
}
createRoot(document.getElementById('root')).render(_jsx(React.StrictMode, { children: _jsx(ErrorBoundary, { children: _jsx(App, {}) }) }));
