import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';

type Props = {
  onComplete: () => void;
  onCancel: () => void;
};

type Step = 'R1' | 'R2' | 'R3' | 'R4';

type InspectResult = {
  valid: boolean;
  format?: string;
  backup_date?: string | null;
  sha256?: string;
  size_bytes?: number;
  shop_uuid?: string | null;
  shop_name?: string | null;
  schema_version?: number | null;
  user_count?: number | null;
  branch_count?: number | null;
  source?: string | null;
  backup_point_id?: string | null;
};

type RestoreResult = {
  success: boolean;
  shop_uuid?: string;
  shop_name?: string | null;
  user_count?: number;
  branch_count?: number;
  requires_relogin?: boolean;
  safety_backup?: string;
};

const MAX_FILE_BYTES = 500 * 1024 * 1024;
const ALLOWED_EXT = '.ltbak';

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function validateFile(f: File | null): string | null {
  if (!f) return 'Please select a .ltbak file';
  if (!f.name.toLowerCase().endsWith(ALLOWED_EXT)) return 'Only .ltbak files are allowed';
  if (f.size <= 0) return 'File is empty';
  if (f.size > MAX_FILE_BYTES) return `File too large (${formatBytes(f.size)}). Max 500 MB`;
  return null;
}

export function RestoreFlow({ onComplete, onCancel }: Props) {
  const [step, setStep] = useState<Step>('R1');
  const [file, setFile] = useState<File | null>(null);
  const [emergencyKey, setEmergencyKey] = useState('');
  const [showEmergency, setShowEmergency] = useState(false);
  const [inspecting, setInspecting] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [metadata, setMetadata] = useState<InspectResult | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successData, setSuccessData] = useState<RestoreResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!restoring) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [restoring]);

  const fileError = validateFile(file);
  const canInspect = !fileError && !inspecting && !restoring;

  async function handleInspect() {
    if (!canInspect || !file) return;
    setError(null);
    setInspecting(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const result = await api<InspectResult>('/setup/inspect-backup', {
        method: 'POST',
        body: form,
        timeoutMs: 60000,
      });
      setMetadata(result);
      setStep('R3');
    } catch (e) {
      setError((e as Error).message || 'Failed to inspect backup');
    } finally {
      setInspecting(false);
    }
  }

  async function handleRestore() {
    if (!file || !confirmed || restoring) return;
    setError(null);
    setRestoring(true);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('confirm_replace', 'true');
      form.append('emergency_key', emergencyKey || '');
      const result = await api<RestoreResult>('/setup/restore-from-file', {
        method: 'POST',
        body: form,
        timeoutMs: 300000,
      });
      setSuccessData(result);
      setStep('R4');
      toast.success('Restore complete');
    } catch (e) {
      setError((e as Error).message || 'Restore failed');
    } finally {
      setRestoring(false);
    }
  }

  function handleCancelClick() {
    if (inspecting || restoring) return;
    if (file && step === 'R2') {
      if (!window.confirm('Discard selected file and go back?')) return;
    }
    onCancel();
  }

  function handleBackToR1() {
    if (inspecting || restoring) return;
    setFile(null);
    setError(null);
    setStep('R1');
  }

  function handleBackToR2() {
    if (restoring) return;
    setStep('R2');
    setConfirmed(false);
    setError(null);
  }

  if (step === 'R1') {
    return (
      <div className="restore-flow">
        <div className="restore-step">
          <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>Restore from backup</h2>
          <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>Choose where your backup file is stored.</p>
          <div className="restore-source-cards">
            <button type="button" className="restore-source-card" onClick={() => setStep('R2')}>
              <div className="restore-source-icon" style={{ fontSize: '1.6rem' }}>📁</div>
              <div style={{ textAlign: 'left' }}>
                <b>Upload from file</b>
                <p className="muted" style={{ margin: '0.2rem 0 0', fontSize: '0.78rem' }}>Select a .ltbak file from USB or local disk</p>
              </div>
            </button>
            <button type="button" className="restore-source-card" disabled>
              <div className="restore-source-icon" style={{ fontSize: '1.6rem' }}>☁️</div>
              <div style={{ textAlign: 'left' }}>
                <b>Google Drive</b>
                <p className="muted" style={{ margin: '0.2rem 0 0', fontSize: '0.78rem' }}>Available in Chunk 14c</p>
              </div>
            </button>
          </div>
        </div>
        <div className="setup-actions">
          <button type="button" className="btn-secondary" onClick={handleCancelClick}>Cancel</button>
        </div>
      </div>
    );
  }

  if (step === 'R2') {
    return (
      <div className="restore-flow">
        <div className="restore-step">
          <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>Select backup file</h2>
          <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>Choose a .ltbak file. Max size: 500 MB.</p>

          <div
            className={`restore-file-drop ${file ? 'has-file' : ''}`}
            onClick={() => !inspecting && fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef.current?.click(); } }}
            style={{ cursor: inspecting ? 'not-allowed' : 'pointer' }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".ltbak"
              style={{ display: 'none' }}
              disabled={inspecting}
              onChange={(e) => {
                const f = e.target.files?.[0] || null;
                setFile(f);
                setError(null);
              }}
            />
            {file ? (
              <div className="restore-file-info">
                <b>{file.name}</b>
                <span>{formatBytes(file.size)}</span>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: '2rem' }}>📁</div>
                <b>Click to select file</b>
                <p className="muted" style={{ margin: 0 }}>or drag and drop</p>
              </div>
            )}
          </div>

          {fileError && file && <span className="setup-error">{fileError}</span>}

          <div className="setup-form-row">
            <label>Emergency key (optional)</label>
            <div className="pwd-wrapper">
              <input
                type={showEmergency ? 'text' : 'password'}
                value={emergencyKey}
                onChange={(e) => setEmergencyKey(e.target.value)}
                placeholder="Only needed if setup is already complete"
                maxLength={255}
                disabled={inspecting}
                autoComplete="off"
              />
              <button
                type="button"
                className="pwd-toggle-btn"
                onClick={() => setShowEmergency((v) => !v)}
                aria-label={showEmergency ? 'Hide' : 'Show'}
                tabIndex={-1}
              >
                {showEmergency ? '🙈' : '👁'}
              </button>
            </div>
            <small className="muted" style={{ fontSize: '0.7rem' }}>{emergencyKey.length}/255</small>
          </div>

          {error && <div className="modal-error-banner">{error}</div>}
        </div>
        <div className="setup-actions">
          <button type="button" className="btn-secondary" onClick={handleBackToR1} disabled={inspecting}>← Back</button>
          <button type="button" className="primary" onClick={handleInspect} disabled={!canInspect}>
            {inspecting ? 'Inspecting…' : 'Continue →'}
          </button>
        </div>
      </div>
    );
  }

  if (step === 'R3') {
    return (
      <div className="restore-flow">
        <div className="restore-step">
          <h2 style={{ fontSize: '1.2rem', margin: '0 0 0.5rem' }}>Confirm restore</h2>
          <p className="muted" style={{ fontSize: '0.85rem', margin: 0 }}>Review the backup details before restoring.</p>

          <div className="restore-metadata">
            <div><small>Backup date</small><b>{metadata?.backup_date ? new Date(metadata.backup_date).toLocaleString() : 'Not available'}</b></div>
            <div><small>File size</small><b>{metadata?.size_bytes ? formatBytes(metadata.size_bytes) : '—'}</b></div>
            <div><small>Shop name</small><b>{metadata?.shop_name || 'Not available'}</b></div>
            <div><small>Users in backup</small><b>{metadata?.user_count ?? 'Not available'}</b></div>
            <div><small>Branches in backup</small><b>{metadata?.branch_count ?? 'Not available'}</b></div>
            <div><small>Shop UUID</small><b title={metadata?.shop_uuid || ''}>{metadata?.shop_uuid ? metadata.shop_uuid.slice(0, 8) + '…' : 'Not available'}</b></div>
          </div>

          <div className="restore-warning">
            <b>⚠ This will REPLACE the current database</b>
            <p style={{ margin: '0.3rem 0 0' }}>A safety backup is created automatically, but the current data on this machine will be replaced by the backup file.</p>
          </div>

          <label className="restore-confirm-check">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              disabled={restoring}
            />
            <span>I understand this will replace the current database</span>
          </label>

          {error && <div className="modal-error-banner">{error}</div>}
        </div>
        <div className="setup-actions">
          <button type="button" className="btn-secondary" onClick={handleBackToR2} disabled={restoring}>← Back</button>
          <button type="button" className="primary danger-button" onClick={handleRestore} disabled={!confirmed || restoring}>
            {restoring ? 'Restoring… do not close' : 'Restore Now'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="restore-flow">
      <div className="restore-step restore-success">
        <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'rgba(22, 163, 74, 0.15)', color: '#16a34a', display: 'grid', placeItems: 'center', fontSize: '2rem', margin: '0 auto 1rem' }}>✓</div>
        <h2 style={{ fontSize: '1.35rem', margin: '0 0 0.5rem' }}>Restore complete</h2>
        {successData?.shop_name ? <p className="muted" style={{ margin: '0 0 0.4rem' }}>Shop: <b style={{ color: 'var(--text)' }}>{successData.shop_name}</b></p> : null}
        <p className="muted" style={{ margin: '0 0 0.4rem' }}>Log in with your previous admin credentials.</p>
        {successData?.safety_backup ? <p className="muted" style={{ fontSize: '0.72rem', margin: '0.4rem 0 0', wordBreak: 'break-all' }}>Safety backup: {successData.safety_backup}</p> : null}
        <p className="muted" style={{ fontSize: '0.72rem', margin: '0.4rem 0 0' }}>Restore event logged in audit trail.</p>
      </div>
      <div className="setup-actions" style={{ justifyContent: 'center' }}>
        <button type="button" className="primary" onClick={onComplete}>Go to Login →</button>
      </div>
    </div>
  );
}

export default RestoreFlow;
