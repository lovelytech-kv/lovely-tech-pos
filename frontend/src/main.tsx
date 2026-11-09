import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { currentUser, logout, ensureApiBaseResolved, resetApiBaseResolution, api } from './api/client';
import { Login } from './features/auth/Login';
import { ChangePassword } from './features/auth/ChangePassword';
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
  computeClientSetupState,
  computeServerSetupState,
  isReadySetupState,
  requiresAdminSetup,
  isTransientSetupState,
  fetchMachineIdentityFromBackend,
  syncLocalFromBackend,
  type MachineRole,
  type MachineConfig,
  type SetupState,
} from './services/machine-config';
import { ThemeProvider } from './theme/ThemeProvider';
import { ShopProvider } from './features/settings/ShopContext';
import { ToastContainer } from './ui/ToastContainer';
import { ModalProvider } from './ui/modals';
import { SetupWizard } from './features/setup/SetupWizard';
import './styles.css';

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

async function testServerUrlClient(url: string): Promise<boolean> {
  const clean = url.replace(/\/$/, '');
  const apiBase = clean.endsWith('/api/v1') ? clean : `${clean}/api/v1`;
  const candidates = [`${apiBase}/health`, `${clean}/health`];

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 5000);

  try {
    for (const u of candidates) {
      try {
        const res = await fetch(u, { signal: controller.signal, cache: 'no-store' });
        if (res.ok) {
          try {
            const body = await res.json();
            if (body?.status === 'ok') return true;
          } catch {
            /* try next */
          }
        }
      } catch (e) {
        if ((e as Error).name === 'AbortError') return false;
      }
    }
    return false;
  } finally {
    window.clearTimeout(timer);
  }
}

function App() {
  const [user, setUser] = useState(currentUser());
  const [bootPhase, setBootPhase] = useState<'discovering' | 'failed' | 'ready'>('discovering');
  const [setupStatus, setSetupStatus] = useState<'checking' | 'required' | 'ready'>('checking');
  const [machineStatus, setMachineStatus] = useState<'idle' | 'checking' | 'ready' | 'client-error'>('idle');
  const [machineCheckTrigger, setMachineCheckTrigger] = useState(0);
  const [machineError, setMachineError] = useState<string | null>(null);
  const [showManualConfig, setShowManualConfig] = useState(false);
  const [machineRole, setMachineRoleState] = useState<MachineRole | null>(null);
  const [machineConfig, setMachineConfig] = useState<MachineConfig | null>(null);
  const [setupState, setSetupStateLocal] = useState<SetupState | null>(null);

  useEffect(() => {
    const h = () => { logout(); setUser(null); };
    window.addEventListener('ltpos:session-expired', h);
    return () => window.removeEventListener('ltpos:session-expired', h);
  }, []);

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

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        await ensureApiBaseResolved();
        if (alive) {
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
        }
      } catch (err) {
        if (alive) {
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
      }
    })();
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (bootPhase !== 'ready') return;
    let alive = true;
    (async () => {
      try {
        const result = await api<{ is_initialized: boolean; reason: string; user_count: number; has_admin: boolean }>('/setup/status');
        if (!alive) return;
        setSetupStatus(result.is_initialized ? 'ready' : 'required');
      } catch {
        if (alive) setSetupStatus('ready');
      }
    })();
    return () => { alive = false; };
  }, [bootPhase]);

  // Chunk 12b — Machine identity check after setup is ready
  useEffect(() => {
    if (setupStatus !== 'ready') return;
    let alive = true;
    (async () => {
      setMachineStatus('checking');
      setMachineError(null);
      try {
        const identity = await fetchMachineIdentityFromBackend();
        if (!alive) return;
        if (!identity) {
          // Backend unreachable → assume SERVER (safe default for existing installs)
          setMachineStatus('ready');
          return;
        }
        try { syncLocalFromBackend(identity); } catch { /* ignore */ }
        if (identity.machine_role === 'CLIENT') {
          if (!identity.server_url) {
            setMachineError('This machine is configured as a CLIENT but no server URL is set. Contact your administrator.');
            setMachineStatus('client-error');
            return;
          }
          const ok = await testServerUrlClient(identity.server_url);
          if (!alive) return;
          if (!ok) {
            setMachineError(`Cannot reach server at ${identity.server_url}. Check that the server laptop is on and connected to the same network.`);
            setMachineStatus('client-error');
            return;
          }
        }
        setMachineStatus('ready');
      } catch {
        if (alive) setMachineStatus('ready');
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setupStatus, machineCheckTrigger]);

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

  const handleSetupComplete = () => {
    window.location.reload();
  };

  const handleRetryMachineCheck = () => {
    setMachineError(null);
    setMachineStatus('idle');
    setMachineCheckTrigger((t) => t + 1);
  };

  if (bootPhase === 'ready' && machineConfig && isTransientSetupState(machineConfig.setup_state)) {
    clearTransientSetupState();
  }

  if (bootPhase === 'discovering') {
    return (
      <DiscoveryStatus
        onReady={() => setBootPhase('ready')}
        onConfigureManual={handleConfigureManual}
      />
    );
  }

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

  if (isTauriEnvironment() && machineRole) {
    const config = loadMachineConfig();
    const currentSetupState = config?.setup_state ?? 'UNINITIALIZED';

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
    }
  }

  if (setupStatus === 'checking') {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'var(--page)', color: 'var(--muted)' }}>
        <div style={{ display: 'grid', placeItems: 'center', gap: '0.75rem' }}>
          <span className="spinner spinner-lg" />
          <span style={{ fontSize: '0.85rem' }}>Checking setup…</span>
        </div>
      </div>
    );
  }

  if (setupStatus === 'required') {
    return <SetupWizard onComplete={handleSetupComplete} />;
  }

  if (machineStatus === 'checking' || machineStatus === 'idle') {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'var(--page)', color: 'var(--muted)' }}>
        <div style={{ display: 'grid', placeItems: 'center', gap: '0.75rem' }}>
          <span className="spinner spinner-lg" />
          <span style={{ fontSize: '0.85rem' }}>Verifying machine…</span>
        </div>
      </div>
    );
  }

  if (machineStatus === 'client-error') {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'var(--page)', padding: '2rem' }}>
        <div style={{ maxWidth: 520, background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 14, padding: '1.5rem', boxShadow: '0 20px 48px rgba(0,0,0,0.08)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '1.8rem' }}>⚠</span>
            <h2 style={{ margin: 0, fontSize: '1.2rem', color: '#dc2626' }}>Server Connection Issue</h2>
          </div>
          <p className="muted" style={{ margin: '0 0 1rem', lineHeight: 1.6, fontSize: '0.9rem' }}>
            {machineError || 'This machine cannot reach its configured server.'}
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button type="button" className="primary" onClick={handleRetryMachineCheck}>Retry</button>
            <button type="button" className="btn-secondary" onClick={() => { logout(); setUser(null); setMachineStatus('ready'); }}>
              Skip and Go to Login
            </button>
          </div>
          <p className="muted" style={{ margin: '0.75rem 0 0', fontSize: '0.72rem' }}>
            If the server is unreachable, contact your administrator to verify the server URL in Settings → Machine Role.
          </p>
        </div>
      </div>
    );
  }

  return user ? (
    user.must_change_password ? (
      <ChangePassword user={user} onDone={setUser} onLogout={() => { logout(); setUser(null); }} />
    ) : (
      <POSHome user={user} onLogout={() => setUser(null)} />
    )
  ) : (
    <Login onLogin={setUser} />
  );
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <ShopProvider>
          <ModalProvider>
            <App />
            <ToastContainer />
          </ModalProvider>
        </ShopProvider>
      </ThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>
);