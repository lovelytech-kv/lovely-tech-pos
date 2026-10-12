import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { currentUser, logout, ensureApiBaseResolved, resetApiBaseResolution, type BootstrapShopResponse, refreshServerSetupState } from './api/client';
import { Login } from './features/auth/Login';
import { POSHome } from './features/pos/POSHome';
import { DiscoveryStatus } from './components/DiscoveryStatus';
import { AdminManualServerPanel } from './components/AdminManualServerPanel';
import { SetupRequired } from './components/SetupRequired';
import { isTauriEnvironment, isServerSetupState } from './services/discovery';
import { getResolvedServerIdentity } from './api/client';
import {
  getOrCreateMachineConfig,
  setMachineRole,
  setSetupState,
  clearTransientSetupState,
  loadMachineConfig,
  applyVerifiedServerToClient,
  type MachineRole,
  type MachineConfig,
  type SetupState,
  computeClientSetupState,
  computeServerSetupState,
  isReadySetupState,
  requiresAdminSetup,
  isTransientSetupState,
} from './services/machine-config';
import './styles.css';

// Shows the real error instead of a blank white screen, so problems can be reported and fixed quickly.
class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (!this.state.error) return this.props.children;
    const e = this.state.error;
    return (
      <div style={{ padding: 24, color: '#fff', background: '#111', minHeight: '100vh', fontFamily: 'sans-serif' }}>
        <h2 style={{ color: '#ff4d4d' }}>Something went wrong</h2>
        <p>Please send a photo/screenshot of this screen to the developer.</p>
        <pre style={{ whiteSpace: 'pre-wrap', background: '#222', padding: 12, borderRadius: 8 }}>
          {e.message}{'\n\n'}{(e.stack || '').slice(0, 1500)}
        </pre>
        <button onClick={() => { logout(); window.location.reload(); }}>
          Clear saved session and reload
        </button>
      </div>
    );
  }
}

function App() {
  const [user, setUser] = useState(currentUser());
  const [bootPhase, setBootPhase] = useState<'discovering' | 'failed' | 'ready'>('discovering');
  const [showManualConfig, setShowManualConfig] = useState(false);
  const [machineRole, setMachineRoleState] = useState<MachineRole | null>(null);
  const [machineConfig, setMachineConfig] = useState<MachineConfig | null>(null);
  const [setupState, setSetupStateLocal] = useState<SetupState | null>(null);

  useEffect(() => {
    const h = () => { logout(); setUser(null); };
    window.addEventListener('ltpos:session-expired', h);
    return () => window.removeEventListener('ltpos:session-expired', h);
  }, []);

  // Machine-role selection: preserve persisted role; if none, probe localhost backend.
  // In browser dev mode there is no machine role; we skip persistence.
  useEffect(() => {
    if (!isTauriEnvironment()) {
      setMachineRoleState(null);
      setSetupStateLocal(null);
      return;
    }
    const initializeRole = async () => {
      const existing = loadMachineConfig();
      if (existing && existing.machine_role === 'SERVER' || existing && existing.machine_role === 'CLIENT') {
        setMachineRoleState(existing.machine_role);
        setMachineConfig(existing);
        setSetupStateLocal(existing.setup_state);
        return;
      }
      // No valid persisted role - probe localhost
      let selectedRole: MachineRole = 'CLIENT';
      let detectedServerSetupState: SetupState = 'SETUP_ERROR';
      try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 800);
        try {
          const res = await fetch('http://127.0.0.1:8000/discovery/info', {
            method: 'GET',
            cache: 'no-store',
            signal: controller.signal,
          });
          if (res.ok) {
            const data = await res.json();
            if (
              data &&
              typeof data === 'object' &&
              data.product === 'Lovely Tech POS System' &&
              typeof data.instance_id === 'string' &&
              data.instance_id !== ''
            ) {
              selectedRole = 'SERVER';
              detectedServerSetupState = isServerSetupState(data.setup_state)
                ? data.setup_state
                : 'SETUP_ERROR';
            }
          }
        } finally {
          clearTimeout(timeout);
        }
      } catch (err) {
        selectedRole = 'CLIENT';
      }
      const config = getOrCreateMachineConfig(selectedRole);
      const initializedConfig = selectedRole === 'SERVER'
        ? setSetupState(detectedServerSetupState) ?? config
        : config;
      setMachineRoleState(config.machine_role);
      setMachineConfig(initializedConfig);
      setSetupStateLocal(initializedConfig.setup_state);
    };
    initializeRole();
  }, []);

  // Applies the verified server response to the CLIENT machine configuration.
  // Only a verified /discovery/info response can move the client to READY;
  // NEW_SHOP_REQUIRED / EXISTING_SHOP_REQUIRED mean the client waits for the
  // server Admin - the client never provisions the server itself.
  const applyVerifiedServerState = () => {
    if (!isTauriEnvironment()) return;
    const identity = getResolvedServerIdentity();
    if (!identity || !isServerSetupState(identity.setup_state)) {
      const updated = setSetupState('SETUP_ERROR');
      if (updated) setMachineConfig(updated);
      setSetupStateLocal('SETUP_ERROR');
      return;
    }
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
      } catch (err) {
        if (alive) {
          setBootPhase('failed');
          // On discovery failure for a CLIENT, transition to appropriate error/setup state
          if (isTauriEnvironment()) {
            const current = loadMachineConfig();
            if (current?.machine_role === 'CLIENT') {
              const error = err as { code?: string };
              let result: 'success' | 'identity_mismatch' | 'no_servers' | 'all_unreachable' | 'error' = 'error';
              if (error.code === 'IDENTITY_MISMATCH') result = 'identity_mismatch';
              else if (error.code === 'NO_SERVERS') result = 'no_servers';
              else if (error.code === 'ALL_UNREACHABLE') result = 'all_unreachable';
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
    const current = loadMachineConfig();
    if (isTauriEnvironment() && current?.machine_role === 'SERVER' && current.setup_state === 'SETUP_ERROR') {
      try {
        const identity = await refreshServerSetupState();
        if (!isServerSetupState(identity.setup_state) || identity.setup_state !== 'READY') {
          throw new Error('The server has not reached READY.');
        }
        applyVerifiedServerState();
        const updated = setSetupState('READY');
        if (updated) setMachineConfig(updated);
        setSetupStateLocal('READY');
      } catch {
        const updated = setSetupState('SETUP_ERROR');
        if (updated) setMachineConfig(updated);
        setSetupStateLocal('SETUP_ERROR');
      }
      return;
    }

    try {
      await resetApiBaseResolution();
      setBootPhase('ready');
      applyVerifiedServerState();
    } catch (err) {
      setBootPhase('failed');
      if (isTauriEnvironment()) {
        const current = loadMachineConfig();
        if (current?.machine_role === 'CLIENT') {
          const error = err as { code?: string };
          let result: 'success' | 'identity_mismatch' | 'no_servers' | 'all_unreachable' | 'error' = 'error';
          if (error.code === 'IDENTITY_MISMATCH') result = 'identity_mismatch';
          else if (error.code === 'NO_SERVERS') result = 'no_servers';
          else if (error.code === 'ALL_UNREACHABLE') result = 'all_unreachable';
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

  // Bootstrap success (NEW_SHOP_REQUIRED server Admin): establish the same
  // authenticated session that a normal login establishes (the token + user
  // are already persisted by bootstrapShop via the shared persistSession),
  // then refresh /discovery/info to verify the server's current setup state.
  // Only a verified READY discovery response advances the SERVER setup state.
  const handleBootstrapSuccess = async (result: BootstrapShopResponse) => {
    setUser(result);
    if (!isTauriEnvironment()) return;

    try {
      const identity = await refreshServerSetupState();
      // Only advance when the refreshed identity confirms READY.
      if (isServerSetupState(identity.setup_state) && identity.setup_state === 'READY') {
        applyVerifiedServerState();
        const updated = setSetupState('READY');
        if (updated) setMachineConfig(updated);
        setSetupStateLocal('READY');
      }
    } catch {
      // Refresh failed or identity is invalid: keep the authenticated session
      // intact and let the existing SETUP_ERROR/retry UI surface the problem.
      // Do not repeat bootstrap automatically.
      const updated = setSetupState('SETUP_ERROR');
      if (updated) setMachineConfig(updated);
      setSetupStateLocal('SETUP_ERROR');
    }
  };

  // If we're in a transient discovery state, clear it on successful boot
  if (bootPhase === 'ready' && machineConfig && isTransientSetupState(machineConfig.setup_state)) {
    clearTransientSetupState();
  }

  // Show discovery status during boot
  if (bootPhase === 'discovering') {
    return (
      <DiscoveryStatus
        onReady={() => setBootPhase('ready')}
        onConfigureManual={handleConfigureManual}
      />
    );
  }

  // Show manual config or failed state
  if (bootPhase === 'failed' || showManualConfig) {
    return (
      <AdminManualServerPanel
        onConfigured={() => {
          setShowManualConfig(false);
          setBootPhase('ready');
          // The manual server was verified through /discovery/info: its
          // setup_state drives the client state exactly like automatic discovery.
          applyVerifiedServerState();
        }}
        onBack={() => {
          setShowManualConfig(false);
          setBootPhase('failed');
        }}
        onRetry={handleRetryDiscovery}
      />
    );
  }

  // At this point, bootPhase is 'ready'. Check setup state for Tauri environments.
  if (isTauriEnvironment() && machineRole) {
    const config = loadMachineConfig();
    const currentSetupState = config?.setup_state ?? 'UNINITIALIZED';

    // For CLIENT machines, show setup-required UI if not READY
    if (machineRole === 'CLIENT' && !isReadySetupState(currentSetupState)) {
      const isAdmin = user?.role.toUpperCase() === 'ADMIN';
      return (
        <SetupRequired
          state={currentSetupState}
          isAdmin={isAdmin}
          machineRole="CLIENT"
          onRetryDiscovery={handleRetryDiscovery}
          onConfigureManual={handleConfigureManual}
          onBackToDiscovery={handleBackToDiscovery}
        />
      );
    }

    // For SERVER machines
    if (machineRole === 'SERVER' && !isReadySetupState(currentSetupState)) {
      const isAdmin = user?.role.toUpperCase() === 'ADMIN';
      const firstRunBootstrap = currentSetupState === 'NEW_SHOP_REQUIRED';
      if (requiresAdminSetup(currentSetupState) && !isAdmin && !firstRunBootstrap) {
        return (
          <SetupRequired
            state={currentSetupState}
            isAdmin={false}
            machineRole="SERVER"
            onRetryDiscovery={handleRetryDiscovery}
            onConfigureManual={handleConfigureManual}
            onBackToDiscovery={handleBackToDiscovery}
          />
        );
      }
      // Admin would see the setup flow here
      return (
        <SetupRequired
          state={currentSetupState}
          isAdmin={isAdmin || firstRunBootstrap}
          machineRole="SERVER"
          onRetryDiscovery={handleRetryDiscovery}
          onConfigureManual={handleConfigureManual}
          onBackToDiscovery={handleBackToDiscovery}
          onBootstrapSuccess={handleBootstrapSuccess}
        />
      );
    }
  }

  // Normal authenticated flow
  return user ? (
    <POSHome user={user} onLogout={() => setUser(null)} />
  ) : (
    <Login onLogin={setUser} />
  );
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);