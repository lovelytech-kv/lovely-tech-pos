import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { Icon } from '../../components/Icon';
import { InvoiceTemplateEditor } from './InvoiceTemplateEditor';

type SummaryRow = {
  id: string;
  paper_size: string;
  is_active: boolean;
  is_default: boolean;
};

const PAPER_LABELS: Record<string, string> = {
  '80mm': '80mm',
  A4: 'A4',
  A5: 'A5',
  A6: 'A6',
};

export function InvoiceTemplatesCard({ isAdmin }: { isAdmin: boolean }) {
  const [rows, setRows] = useState<SummaryRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!isAdmin || open) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const result = await api<SummaryRow[]>('/invoice-templates');
        if (!cancelled) setRows(result);
      } catch {
        // Summary is informational only; the editor reports real errors.
        if (!cancelled) setRows(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [isAdmin, open]);

  if (!isAdmin) return null;

  const count = rows?.length ?? 0;
  const paperSizes = Array.from(new Set((rows ?? []).map((row) => row.paper_size))).sort();

  return (
    <>
      <div className="glass-panel settings-card invoice-template-summary">
        <div className="settings-card-title">
          <div>
            <h3>Invoice Templates</h3>
            <p className="muted">
              {loading
                ? 'Checking configured templates…'
                : rows === null
                ? 'Template summary unavailable. Open the editor to manage templates.'
                : count === 0
                ? 'No templates configured yet. Create one to control receipt printing.'
                : `${count} template${count === 1 ? '' : 's'} configured. Customize receipt layout and live preview in a dedicated editor.`}
            </p>
          </div>
          <span className="settings-symbol"><Icon name="receipt" size={20} /></span>
        </div>
        <div className="invoice-summary-badges">
          {paperSizes.map((size) => (
            <span key={size} className="invoice-paper-badge">{PAPER_LABELS[size] ?? size}</span>
          ))}
        </div>
        <div className="button-row" style={{ marginTop: '0.5rem' }}>
          <button type="button" className="primary" onClick={() => setOpen(true)}>
            Manage templates
          </button>
        </div>
      </div>

      {open && (
        <InvoiceTemplateEditor
          isAdmin={isAdmin}
          mode="modal"
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
