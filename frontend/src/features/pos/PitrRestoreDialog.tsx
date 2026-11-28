import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { Icon } from '../../components/Icon';
import { toast } from '../../ui/toast';

type Range = {
  earliest: string | null;
  latest: string | null;
  base_backup_count: number;
};

type Props = {
  onClose: () => void;
};

function toDatetimeLocal(iso: string | null): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return '';
  }
}

export function PitrRestoreDialog({ onClose }: Props) {
  const [range, setRange] = useState<Range | null>(null);
  const [loadingRange, setLoadingRange] = useState(false);
  const [rangeError, setRangeError] = useState<string | null>(null);

  const [targetTime, setTargetTime] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);

  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDiscard, setShowDiscard] = useState(false);

  async function loadRange() {
    if (!adminPassword) {
      setRangeError('Enter admin password first');
      return;
    }
    setLoadingRange(true);
    setRangeError(null);
    try {
      const r = await api<Range>(
        `/admin/pitr/restore-range?admin_password=${encodeURIComponent(adminPassword)}`,
        { timeoutMs: 15000 },
      );
      setRange(r);
      if (!r.earliest || !r.latest) {
        setRangeError('No base backups found. Create a base backup first.');
      }
    } catch (e) {
      setRangeError((e as Error).message || 'Failed to load restore range');
    } finally {
      setLoadingRange(false);
    }
  }

  const targetErr = useMemo(() => {
    if (!targetTime) return null;
    if (!range?.earliest || !range?.latest) return null;
    const t = new Date(targetTime).getTime();
    const e = new Date(range.earliest).getTime();
    const l = new Date(range.latest).getTime();
    if (isNaN(t)) return 'Invalid datetime';
    if (t < e) return `Too early (earliest: ${new Date(range.earliest).toLocaleString()})`;
    if (t > l) return `Too late (latest: ${new Date(range.latest).toLocaleString()})`;
    return null;
  }, [targetTime, range]);

  const canSubmit =
    !!targetTime
    && !targetErr
    && replaceText === 'RESTORE'
    && adminPassword.length > 0
    && !busy
    && !!range?.earliest
    && !!range?.latest;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api<Range>(
        `/admin/pitr/restore-range?admin_password=${encodeURIComponent(adminPassword)}`,
        { timeoutMs: 15000 },
      );
      if (!r.earliest || !r.latest) throw new Error('Restore range disappeared — refresh');
      const baseId = 1;
      const localTime = targetTime.replace('T', ' ');
      const cmd = `.\\scripts\\pitr_restore.ps1 -TargetTime "${localTime}" -BaseBackupId ${baseId} -ClusterPort 5432`;
      setResult(cmd);
      toast.success('PITR plan prepared. Run in elevated PowerShell.');
    } catch (e) {
      setError((e as Error).message || 'Failed to prepare PITR');
    } finally {
      setBusy(false);
    }
  }

  function requestClose() {
    if (busy) return;
    const hasInput = !!(targetTime || replaceText || adminPassword) && !result;
    if (hasInput) {
      setShowDiscard(true);
      return;
    }
    onClose();
  }

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) requestClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  });

  return (
    <>
      <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget && !busy) requestClose(); }}>
        <div className="modal-card" style={{ width: 'min(580px, 100%)' }} onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h3>PITR Restore (Point-in-Time)</h3>
            <button className="modal-close" onClick={requestClose} disabled={busy} aria-label="Close"><Icon name="close-x" size={16} /></button>
          </div>
          <div className="modal-body">
            <div
              className="recovery-warning"
              style={{ background: 'rgba(220, 38, 38, 0.1)', borderColor: 'rgba(220, 38, 38, 0.35)', color: '#b91c1c' }}
            >
              <b><Icon name="warning-triangle" size={15} /> DESTRUCTIVE OPERATION</b>
              <p style={{ margin: '0.3rem 0 0' }}>
                This will restore the ENTIRE database to the chosen time. All data after that time will be LOST.
                A safety backup is taken automatically. The script must be run manually in elevated PowerShell.
              </p>
            </div>

            <div className="setup-form-row">
              <label>Admin Password *</label>
              <div className="pwd-wrapper">
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                  placeholder="Enter admin password to load restore range"
                  disabled={busy || !!result}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="pwd-toggle-btn"
                  onClick={() => setShowPwd((v) => !v)}
                  aria-label={showPwd ? 'Hide' : 'Show'}
                >
                  {showPwd ? <Icon name="eye-off" size={16} /> : <Icon name="eye" size={16} />}
                </button>
              </div>
              <button
                type="button"
                className="btn-secondary"
                style={{ marginTop: '0.4rem', width: '100%' }}
                onClick={() => void loadRange()}
                disabled={!adminPassword || loadingRange || busy || !!result}
              >
                {loadingRange ? 'Loading range…' : 'Load Restore Range'}
              </button>
            </div>

            {rangeError && <div className="modal-error-banner">{rangeError}</div>}

            {range && range.earliest && range.latest && (
              <div className="machine-info-grid" style={{ marginBottom: '0.5rem' }}>
                <div><small>Earliest</small><b>{new Date(range.earliest).toLocaleString()}</b></div>
                <div><small>Latest</small><b>{new Date(range.latest).toLocaleString()}</b></div>
                <div><small>Base backups</small><b>{range.base_backup_count}</b></div>
              </div>
            )}

            {range && range.earliest && range.latest && !result && (
              <>
                <div className="setup-form-row">
                  <label>Target Date &amp; Time *</label>
                  <input
                    type="datetime-local"
                    value={targetTime}
                    onChange={(e) => setTargetTime(e.target.value)}
                    min={toDatetimeLocal(range.earliest)}
                    max={toDatetimeLocal(range.latest)}
                    disabled={busy}
                    className={targetErr ? 'input-error' : ''}
                  />
                  {targetErr && <span className="setup-error">{targetErr}</span>}
                </div>

                <div className="setup-form-row">
                  <label>Type <b>RESTORE</b> to confirm *</label>
                  <input
                    type="text"
                    value={replaceText}
                    onChange={(e) => setReplaceText(e.target.value)}
                    placeholder="Type RESTORE (all caps)"
                    disabled={busy}
                    autoComplete="off"
                  />
                  <small className="muted" style={{ fontSize: '0.7rem' }}>
                    {replaceText === 'RESTORE' ? <><Icon name="check" size={12} /> Matches</> : 'Must type exactly: RESTORE'}
                  </small>
                </div>

                {error && <div className="modal-error-banner">{error}</div>}
              </>
            )}

            {result && (
              <div
                className="recovery-warning"
                style={{ background: 'rgba(22, 163, 74, 0.1)', borderColor: 'rgba(22, 163, 74, 0.35)', color: '#16a34a' }}
              >
                <b><Icon name="check" size={15} /> PITR plan ready</b>
                <p style={{ margin: '0.3rem 0' }}>Run this command in ELEVATED PowerShell:</p>
                <pre style={{ background: 'rgba(0, 0, 0, 0.05)', padding: '0.5rem', borderRadius: 6, fontSize: '0.72rem', overflowX: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{result}</pre>
                <p style={{ margin: '0.3rem 0 0', fontSize: '0.75rem' }}>
                  The UI does NOT auto-execute. Copy → Run manually.
                </p>
              </div>
            )}
          </div>
          <div className="modal-actions">
            <button className="btn-secondary" onClick={requestClose} disabled={busy}>
              {result ? 'Close' : 'Cancel'}
            </button>
                    {!result && (
          <button
            type="button"
            onClick={() => void submit()}
            disabled={!canSubmit}
            style={{
              padding: '10px 20px',
              background: canSubmit ? '#dc2626' : '#9ca3af',
              color: '#ffffff',
              border: 0,
              borderRadius: 8,
              fontWeight: 700,
              fontSize: '0.85rem',
              cursor: canSubmit ? 'pointer' : 'not-allowed',
              opacity: 1,
              visibility: 'visible',
              minHeight: 40,
              minWidth: 200,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: canSubmit ? '0 2px 8px rgba(220, 38, 38, 0.3)' : 'none',
            }}
          >
            {busy ? 'Preparing…' : 'Proceed with PITR Restore'}
          </button>
        )}
          </div>
        </div>
      </div>

      {showDiscard && (
        <div className="modal-overlay" onClick={() => setShowDiscard(false)}>
          <div className="modal-card" style={{ width: 'min(400px, 100%)' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header"><h3>Discard changes?</h3></div>
            <div className="modal-body">
              <p style={{ margin: 0 }}>You have unsaved input. Close without proceeding?</p>
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setShowDiscard(false)}>Keep editing</button>
              <button
                className="btn-danger"
                onClick={() => { setShowDiscard(false); onClose(); }}
              >
                Discard
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
