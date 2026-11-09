import { useState } from 'react';

type Props = {
  codes: string[];
  title?: string;
  subtitle?: string;
  onContinue?: () => void;
  onClose?: () => void;
};

export function RecoveryCodesDisplay({
  codes,
  title = 'Save Your Recovery Codes',
  subtitle = 'These are one-time recovery codes for your admin account. Save them somewhere safe.',
  onContinue,
  onClose,
}: Props) {
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);

  async function copyAll() {
    try {
      await navigator.clipboard.writeText(codes.join('\n'));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = codes.join('\n');
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    }
  }

  function downloadTxt() {
    const header = `Lovely Tech POS - Admin Recovery Codes\nGenerated: ${new Date().toLocaleString()}\n\n`;
    const content = header + codes.map((c, i) => `${i + 1}. ${c}`).join('\n') + '\n\nKeep these codes safe. Each can be used only once.\n';
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lovely-tech-recovery-codes-${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function print() {
    const w = window.open('', '_blank', 'width=800,height=600');
    if (!w) {
      alert('Print popup was blocked. Please allow popups for this site and try again.');
      return;
    }
    const safeTitle = (title || 'Recovery Codes').replace(/[<>&"]/g, '');
    const safeSubtitle = (subtitle || '').replace(/[<>&"]/g, '');
    const codesHtml = codes
      .map((c, i) => `<div class="code"><span>${i + 1}.</span>${c}</div>`)
      .join('');
    w.document.write(`<!DOCTYPE html>
<html><head><title>Recovery Codes — Lovely Tech POS</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, 'Segoe UI', sans-serif; padding: 28px; color: #111; margin: 0; }
  h1 { font-size: 20px; margin: 0 0 8px; letter-spacing: -0.02em; }
  .subtitle { color: #555; font-size: 13px; margin-bottom: 16px; line-height: 1.5; }
  .warning { background: #fffbe6; border: 1px solid #facc15; padding: 12px 14px; border-radius: 8px; color: #713f12; font-size: 13px; margin-bottom: 20px; line-height: 1.55; }
  .codes { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
  .code { padding: 10px 14px; border: 1px solid #e5e7eb; border-radius: 8px; font-family: 'Consolas', 'Menlo', monospace; font-size: 14px; letter-spacing: 0.05em; font-weight: 600; display: flex; gap: 10px; align-items: center; background: #fafafa; }
  .code span { color: #888; font-size: 11px; font-weight: 700; min-width: 18px; }
  .footer { margin-top: 24px; font-size: 11px; color: #888; text-align: center; border-top: 1px solid #e5e7eb; padding-top: 14px; }
  @media print {
    body { padding: 18px; }
    .codes { page-break-inside: avoid; }
  }
</style></head><body>
  <h1>${safeTitle}</h1>
  ${safeSubtitle ? `<div class="subtitle">${safeSubtitle}</div>` : ''}
  <div class="warning"><b>Important:</b> Each code can be used ONCE. Save them somewhere safe — they will NOT be shown again.</div>
  <div class="codes">${codesHtml}</div>
  <div class="footer">Generated ${new Date().toLocaleString()} · Lovely Tech POS</div>
  <script>window.onload = function(){ window.print(); };</script>
</body></html>`);
    w.document.close();
  }
  return (
    <div className="recovery-codes-container">
      <div className="recovery-print-area">
        <h2 className="recovery-title">{title}</h2>
        {subtitle && <p className="recovery-subtitle">{subtitle}</p>}

        <div className="recovery-warning">
          <b>⚠ Important:</b> These codes will NOT be shown again. Each code can be used ONCE to reset your password.
          If you lose all codes AND forget your password, you will need physical access to the server laptop for emergency reset.
        </div>

        <div className="recovery-codes-grid">
          {codes.map((code, idx) => (
            <div key={idx} className="recovery-code-item" title={`Code ${idx + 1}`}>
              <span className="recovery-code-index">{idx + 1}.</span>
              <span className="recovery-code-value">{code}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="recovery-codes-actions">
        <button type="button" className="btn-secondary" onClick={copyAll}>
          {copied ? '✓ Copied' : '📋 Copy All'}
        </button>
        <button type="button" className="btn-secondary" onClick={downloadTxt}>
          💾 Download .txt
        </button>
        <button type="button" className="btn-secondary" onClick={print}>
          🖨 Print
        </button>
      </div>

      {onContinue && (
        <>
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.85rem', marginTop: '1rem' }}>
            <input
              type="checkbox"
              checked={saved}
              onChange={(e) => setSaved(e.target.checked)}
              style={{ marginTop: '3px' }}
            />
            <span>
              <b>I have saved these codes</b> somewhere safe. I understand they will not be shown again.
            </span>
          </label>
          <div className="form-actions" style={{ marginTop: '1rem', justifyContent: 'center' }}>
            <button type="button" className="primary" onClick={onContinue} disabled={!saved}>
              Continue
            </button>
          </div>
        </>
      )}

      {onClose && !onContinue && (
        <div className="form-actions" style={{ marginTop: '1rem', justifyContent: 'center' }}>
          <button type="button" className="primary" onClick={onClose}>
            Close
          </button>
        </div>
      )}
    </div>
  );
}