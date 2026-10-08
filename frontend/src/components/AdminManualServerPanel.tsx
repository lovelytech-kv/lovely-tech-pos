import { useState } from 'react';
import { configureManualServer } from '../api/client';

export function AdminManualServerPanel({
  onConfigured,
  onBack,
  onRetry,
}: {
  onConfigured: () => void;
  onBack: () => void;
  onRetry: () => Promise<void>;
}) {
  const [input, setInput] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [identity, setIdentity] = useState<Record<string, string> | null>(null);

  async function submit(e: React.FormEvent) {
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
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Manual configuration failed.';
      setError(message);
      setBusy(false);
    } finally {
      setVerifying(false);
    }
  }

  return (
    <div className="discovery-overlay">
      <div className="discovery-card glass-card admin-manual-panel">
        <div className="discovery-panel-head">
          <div>
            <span className="eyebrow">ADMIN · SERVER SETUP</span>
            <h2>Manual server configuration</h2>
            <p className="muted">
              Automatic discovery failed. Enter the POS server address. This control is Admin-only.
            </p>
          </div>
          <button className="ghost" onClick={onBack}>← Back</button>
        </div>

        <form className="manual-form" onSubmit={submit}>
          <label>
            Server address
            <input
              autoFocus
              placeholder="http://192.168.1.50:8000 or 192.168.1.50:8000"
              value={input}
              onChange={e => setInput(e.target.value)}
              spellCheck={false}
            />
          </label>
          <small className="muted">Enter a full URL or host:port. A reachable HTTP response alone is not enough.</small>
          {error && <div className="error manual-error" role="alert">{error}</div>}
          {identity && (
            <div className="manual-verified">
              <span className="status-good">● Verified Lovely Tech POS server</span>
              <div className="identity-grid">
                {(['product', 'instance_id', 'protocol_version', 'api_version', 'app_version', 'branch_code'] as const).map(field => (
                  <div key={field}>
                    <small className="muted">{field}</small>
                    <b>{identity[field] || '—'}</b>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="manual-actions">
            <button className="primary" type="submit" disabled={busy || verifying}>
              {verifying ? 'Verifying…' : busy ? 'Saving…' : 'Connect to server'}
            </button>
            <button className="ghost" type="button" disabled={busy} onClick={onBack}>
              Cancel
            </button>
          </div>
        </form>

        <div className="manual-footer">
          <button className="ghost" onClick={() => { onRetry().catch(() => {}); }}>
            Retry automatic discovery
          </button>
        </div>
      </div>
    </div>
  );
}