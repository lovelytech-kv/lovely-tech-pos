import { useEffect, useState } from 'react';
import { ensureApiBaseResolved, resetApiBaseResolution } from '../api/client';
import type { DiscoveryError } from '../services/discovery';

type Phase = 'discovering' | 'ready' | 'failed';

export function DiscoveryStatus({ onReady, onConfigureManual }: { onReady: () => void; onConfigureManual: () => void }) {
  const [phase, setPhase] = useState<Phase>('discovering');
  const [error, setError] = useState<DiscoveryError | null>(null);
  const [busy, setBusy] = useState(false);

  async function attempt() {
    setBusy(true);
    setError(null);
    try {
      await ensureApiBaseResolved();
      setPhase('ready');
      onReady();
    } catch (err) {
      const discoveryError = (err instanceof Error ? err : new Error(String(err))) as DiscoveryError;
      if (!discoveryError.code) (discoveryError as any).code = 'ALL_UNREACHABLE';
      (discoveryError as any).candidatesTried = (discoveryError as any).candidatesTried ?? 0;
      setError(discoveryError);
      setPhase('failed');
    } finally {
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
    } catch {
      // resetApiBaseResolution already re-resolves; attempt() below covers the retry outcome.
    }
    await attempt();
  }

  if (phase === 'ready') return null;

  return (
    <div className="discovery-overlay">
      <div className="discovery-card glass-card">
        {phase === 'discovering' ? (
          <>
            <div className="discovery-spinner" aria-hidden="true" />
            <h2>Discovering POS server</h2>
            <p className="muted">Looking for the Lovely Tech POS server on the LAN…</p>
          </>
        ) : (
          <>
            <div className="discovery-error-icon" aria-hidden="true">!</div>
            <h2>POS server not found</h2>
            <p className="muted">
              Automatic LAN discovery could not verify a Lovely Tech POS server.
              {error?.code === 'NO_SERVERS'
                ? ' No advertised servers were found on the network.'
                : error?.code === 'IDENTITY_MISMATCH'
                  ? ' A reachable server did not identify itself as a Lovely Tech POS server.'
                  : ' Check that the server laptop is on and on the same LAN.'}
            </p>
            <div className="discovery-actions">
              <button className="primary" disabled={busy} onClick={retry}>
                {busy ? 'Retrying…' : 'Retry Discovery'}
              </button>
              <button className="ghost" disabled={busy} onClick={onConfigureManual}>
                Configure server manually
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}