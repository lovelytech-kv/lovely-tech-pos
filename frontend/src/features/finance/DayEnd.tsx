import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';

const DENOMS = [5000, 2000, 1000, 500, 100, 50, 20] as const;
const today = () => new Date().toISOString().slice(0, 10);
type Props = { isAdmin?: boolean; onError?: (message: string) => void };

export function DayEnd({ isAdmin = false, onError }: Props) {
  const [status, setStatus] = useState<any>(null);
  const [backup, setBackup] = useState<any>(null);
  const [counts, setCounts] = useState<Record<string, string>>({});
  const [opening, setOpening] = useState('');
  const [openingDenoms, setOpeningDenoms] = useState<Record<string, string>>({});
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [reload, setReload] = useState('');
  const [reloadProvider, setReloadProvider] = useState('Dialog');
  const [cashIn, setCashIn] = useState('');
  const [busy, setBusy] = useState(false);
  const [cashCountStarted, setCashCountStarted] = useState(false);
  const [correctionCash, setCorrectionCash] = useState('');
  const [correctionReason, setCorrectionReason] = useState('');
  const [correctionDenoms, setCorrectionDenoms] = useState<Record<string,string>>({});

  const counted = useMemo(() => DENOMS.reduce((sum, d) => sum + d * Number(counts[String(d)] || 0), 0), [counts]);
  const openingCounted = useMemo(() => DENOMS.reduce((sum, d) => sum + d * Number(openingDenoms[String(d)] || 0), 0), [openingDenoms]);

  async function load() {
    try {
      const [day, back] = await Promise.all([api('/operations/day/status'), api('/backup/status')]);
      setStatus(day); setBackup(back);
    } catch (e) { onError?.((e as Error).message); }
  }
  useEffect(() => { load(); }, []);

  function setDenom(target: 'open' | 'actual', d: number, value: string) {
    const clean = value.replace(/[^0-9]/g, '');
    if (target === 'open') setOpeningDenoms(prev => ({ ...prev, [String(d)]: clean }));
    else { setCashCountStarted(true); setCounts(prev => ({ ...prev, [String(d)]: clean })); }
  }

  async function startDay() {
    if (busy) return;
    const openingCash = opening || String(openingCounted);
    if (Number(openingCash) < 0) return onError?.('Opening cash cannot be negative.');
    if (Math.abs(Number(openingCash) - openingCounted) > 0.0001) return onError?.('Opening cash must equal the denomination total.');
    try {
      setBusy(true);
      await api('/operations/day/start', { method: 'POST', body: JSON.stringify({ business_date: today(), opening_cash: openingCash, denominations: Object.fromEntries(DENOMS.map(d => [String(d), Number(openingDenoms[String(d)] || 0)])) }) });
      await load();
    } catch (e) { onError?.((e as Error).message); } finally { setBusy(false); }
  }

  async function shiftEnd() {
    if (!status?.day_session_id || busy) return;
    try { setBusy(true); await api('/operations/day/shift-end', { method: 'POST', body: JSON.stringify({ start: status.business_date, end: status.business_date }) }); await load(); }
    catch (e) { onError?.((e as Error).message); } finally { setBusy(false); }
  }

  async function continueBusiness() {
    if (!isAdmin || !status?.business_date || busy) return;
    try { setBusy(true); await api('/operations/day/continue', { method: 'POST', body: JSON.stringify({ start: status.business_date, end: status.business_date }) }); await load(); }
    catch (e) { onError?.((e as Error).message); } finally { setBusy(false); }
  }

  async function addReload() {
    if (!status?.day_session_id || !reload || busy) return;
    try { setBusy(true); await api('/operations/day/reload', { method: 'POST', body: JSON.stringify({ day_session_id: status.day_session_id, provider: reloadProvider, amount: reload }) }); setReload(''); await load(); }
    catch (e) { onError?.((e as Error).message); } finally { setBusy(false); }
  }

  async function addCashIn() {
    if (!cashIn || busy) return;
    try { setBusy(true); await api('/operations/day/cash-in', { method: 'POST', body: JSON.stringify({ amount: cashIn, note: 'POS cash-in' }) }); setCashIn(''); await load(); }
    catch (e) { onError?.((e as Error).message); } finally { setBusy(false); }
  }

  async function dayEnd() {
    if (!status?.day_session_id || busy) return;
    if (!reason.trim()) return onError?.('Day End reason is required.');
    if (!cashCountStarted) return onError?.('Enter the physical cash denominations before Day End. Zero cash is allowed if intentionally counted.');
    try {
      setBusy(true);
      await api(`/operations/day/${status.day_session_id}/end`, { method: 'POST', body: JSON.stringify({ actual_cash: String(counted), denominations: Object.fromEntries(DENOMS.map(d => [String(d), Number(counts[String(d)] || 0)])), reason: reason.trim(), note: note.trim() || null, version: status.version }) });
      setCounts({}); setCashCountStarted(false); setReason(''); setNote(''); await load();
    } catch (e) { onError?.((e as Error).message); } finally { setBusy(false); }
  }

  async function correctOpening() {
    if (!isAdmin || !status?.day_session_id || busy) return;
    const denomTotal = DENOMS.reduce((sum,d)=>sum+d*Number(correctionDenoms[String(d)]||0),0);
    if (!correctionCash || Number(correctionCash)<0 || Math.abs(denomTotal-Number(correctionCash))>0.0001) return onError?.('Opening cash must equal the denomination total.');
    if (!correctionReason.trim()) return onError?.('Opening correction reason is required.');
    if (status.version == null) return onError?.('Day version is missing; refresh before correcting opening cash.');
    const password = window.prompt('Admin password (re-authentication required)') || '';
    if (!password) return;
    try { setBusy(true); await api(`/operations/day/opening-correction?admin_password=${encodeURIComponent(password)}`, { method:'POST', body:JSON.stringify({day_session_id:status.day_session_id,opening_cash:correctionCash,denominations:Object.fromEntries(DENOMS.map(d=>[String(d),Number(correctionDenoms[String(d)]||0)])),reason:correctionReason.trim(),version:status.version}) }); setCorrectionCash(''); setCorrectionReason(''); setCorrectionDenoms({}); await load(); } catch(e){ onError?.((e as Error).message); } finally { setBusy(false); }
  }

  async function reopen() {
    if (!isAdmin || !status?.business_date || busy) return;
    const password = window.prompt('Admin password (re-authentication required)') || '';
    if (!password) return;
    try { setBusy(true); await api(`/operations/day/reopen?admin_password=${encodeURIComponent(password)}`, { method: 'POST', body: JSON.stringify({ start: status.business_date, end: status.business_date }) }); await load(); }
    catch (e) { onError?.((e as Error).message); } finally { setBusy(false); }
  }

  const closed = status?.status === 'CLOSED';
  const open = Boolean(status?.day_session_id) && (status?.status === 'OPEN' || status?.status === 'SHIFT_ENDED');

  return <section className="glass panel day-end-card">
    <div className="section-head"><div><h2>Cash / Day Start · Shift End · Day End</h2><p className="muted">One workflow for the physical cash drawer and business-day lifecycle.</p></div><button onClick={load}>Refresh</button></div>
    <div className="day-card"><span>Business Date</span><b>{status?.business_date || today()}</b><span>Status</span><b>{status?.status || 'NOT_STARTED'}</b><span>Expected Cash</span><b>Rs. {Number(status?.expected_cash || 0).toFixed(2)}</b><span>Live Difference</span><b>Rs. {(counted-Number(status?.expected_cash||0)).toFixed(2)}</b><span>Backup</span><b>{backup?.status || '—'}{backup?.last_backup_time ? ` · ${new Date(backup.last_backup_time).toLocaleString()}` : ''}</b></div>

    {!status?.day_session_id && <div className="glass panel"><h3>Day Start</h3><div className="form-grid compact"><label>Opening Cash<input type="number" min="0" step="0.01" value={opening} onChange={e => setOpening(e.target.value)} placeholder={openingCounted.toFixed(2)} /></label></div><div className="denomination-grid">{DENOMS.map(d => <label key={`open-${d}`}><span>Rs. {d}</span><input inputMode="numeric" type="number" min="0" step="1" value={openingDenoms[String(d)] || ''} onChange={e => setDenom('open', d, e.target.value)} placeholder="0" /><small>× Rs. {d * Number(openingDenoms[String(d)] || 0)}</small></label>)}</div><div className="cash-total-box"><span>Denomination Total</span><strong>Rs. {openingCounted.toFixed(2)}</strong></div><button disabled={busy} onClick={startDay}>{busy ? 'Starting…' : 'Start Day'}</button></div>}

    {open && <>
      {isAdmin && <div className="glass panel"><h3>Admin · Opening Cash Correction</h3><p className="muted">Use only when the recorded Day Start opening cash is wrong. Every correction is re-authenticated and audited.</p><div className="form-grid compact"><input type="number" min="0" step="0.01" placeholder="Correct opening cash" value={correctionCash} onChange={e=>setCorrectionCash(e.target.value)}/><input placeholder="Correction reason" value={correctionReason} onChange={e=>setCorrectionReason(e.target.value)}/></div><div className="denomination-grid">{DENOMS.map(d=><label key={`correct-${d}`}><span>Rs. {d}</span><input inputMode="numeric" type="number" min="0" step="1" value={correctionDenoms[String(d)]||''} onChange={e=>setCorrectionDenoms(prev=>({...prev,[String(d)]:e.target.value}))}/></label>)}</div><div className="cash-total-box"><span>Corrected denomination total</span><strong>Rs. {DENOMS.reduce((sum,d)=>sum+d*Number(correctionDenoms[String(d)]||0),0).toFixed(2)}</strong></div><button disabled={busy||!correctionCash||!correctionReason.trim()} onClick={correctOpening}>Correct Opening Cash</button></div>}
      <div className="glass panel"><h3>During Business</h3><div className="form-grid compact"><select value={reloadProvider} onChange={e => setReloadProvider(e.target.value)}><option>Dialog</option><option>Airtel</option><option>Mobitel</option><option>Hutch</option></select><input type="number" min="0.01" step="0.01" placeholder="Day-End Reload" value={reload} onChange={e => setReload(e.target.value)} /><button disabled={busy || !reload} onClick={addReload}>Add Reload</button><input type="number" min="0.01" step="0.01" placeholder="Other Cash In" value={cashIn} onChange={e => setCashIn(e.target.value)} /><button disabled={busy || !cashIn} onClick={addCashIn}>Add Cash In</button></div><p className="muted">Reload is recorded once for Day End. Other Cash In is a separate cash transaction.</p></div>
      <div className="glass panel"><h3>Physical Cash Count</h3><div className="denomination-grid">{DENOMS.map(d => <label key={d}><span>Rs. {d}</span><input inputMode="numeric" type="number" min="0" step="1" value={counts[String(d)] || ''} onChange={e => setDenom('actual', d, e.target.value)} placeholder="0" /><small>× Rs. {d * Number(counts[String(d)] || 0)}</small></label>)}</div><div className="cash-total-box"><span>Actual Cash</span><strong>Rs. {counted.toFixed(2)}</strong></div><label className="wide-field">Mandatory Day End Reason<textarea value={reason} onChange={e => setReason(e.target.value)} placeholder="Explain any difference or closing note" /></label><label className="wide-field">Optional Note<textarea value={note} onChange={e => setNote(e.target.value)} /></label><div className="form-actions"><button disabled={busy || !cashCountStarted || !reason.trim()} onClick={dayEnd}>{busy ? 'Closing…' : 'Complete Day End'}</button>{status?.status === 'OPEN' && <button className="ghost" disabled={busy} onClick={shiftEnd}>Cashier Shift End</button>}</div></div>
      {status?.status === 'SHIFT_ENDED' && isAdmin && <div className="glass panel"><h3>Continue Today Business</h3><p className="muted">Admin can continue the same business day within the allowed window.</p><button disabled={busy} onClick={continueBusiness}>Continue Today Business</button></div>}
    </>}

    {closed && isAdmin && <div className="glass panel"><h3>Admin Reopen</h3><p className="muted">Reopening is a critical Admin action and requires re-authentication.</p><button disabled={busy} onClick={reopen}>Reopen Closed Day</button></div>}
  </section>;
}
