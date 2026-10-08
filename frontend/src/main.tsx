import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { currentUser, logout, ensureApiBaseResolved, resetApiBaseResolution } from './api/client';
import { Login } from './features/auth/Login';
import { POSHome } from './features/pos/POSHome';
import { DiscoveryStatus } from './components/DiscoveryStatus';
import { AdminManualServerPanel } from './components/AdminManualServerPanel';
import { SetupRequired } from './components/SetupRequired';
import { isTauriEnvironment } from './services/discovery';
import {
  getOrCreateMachineConfig,
  setMachineRole,
  setSetupState,
  clearTransientSetupState,
  loadMachineConfig,
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

  // Startup discovery runs once on mount. It does not block browser development:
  // in a non-Tauri environment ensureApiBaseResolved resolves to /api/v1 immediately.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        await ensureApiBaseResolved();
        if (alive) {
          setBootPhase('ready');
          // On successful discovery for a CLIENT, transition to SERVER_DETECTED
          if (isTauriEnvironment()) {
            const current = loadMachineConfig();
            if (current?.machine_role === 'CLIENT') {
              const nextState = computeClientSetupState(current.setup_state, 'success');
              if (nextState === 'SERVER_DETECTED') {
                setSetupState(nextState);
                setSetupStateLocal(nextState);
              } else if (isReadySetupState(nextState)) {
                setSetupStateLocal(nextState);
              }
            }
          }
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
      if (isTauriEnvironment()) {
        const current = loadMachineConfig();
        if (current?.machine_role === 'CLIENT') {
          const nextState = computeClientSetupState(current.setup_state, 'success');
          if (nextState === 'SERVER_DETECTED') {
            setSetupState(nextState);
            setSetupStateLocal(nextState);
          } else if (isReadySetupState(nextState)) {
            setSetupStateLocal(nextState);
          }
        }
      }
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
          onRetryDiscovery={handleRetryDiscovery}
          onConfigureManual={handleConfigureManual}
          onBackToDiscovery={handleBackToDiscovery}
        />
      );
    }

    // For SERVER machines (not implemented in this packet, but reserved)
    if (machineRole === 'SERVER' && !isReadySetupState(currentSetupState)) {
      const isAdmin = user?.role.toUpperCase() === 'ADMIN';
      if (requiresAdminSetup(currentSetupState) && !isAdmin) {
        return (
          <SetupRequired
            state={currentSetupState}
            isAdmin={false}
            onRetryDiscovery={handleRetryDiscovery}
            onConfigureManual={handleConfigureManual}
            onBackToDiscovery={handleBackToDiscovery}
          />
        );
      }
      // Admin would see the setup flow here (future packets)
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