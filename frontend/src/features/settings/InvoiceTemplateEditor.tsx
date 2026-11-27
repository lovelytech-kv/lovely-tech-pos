import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';
import { useModal } from '../../ui/modals';
import { useShopProfile } from './ShopContext';
import {
  DEFAULT_TEMPLATES,
  renderReceiptPreview,
  type PaperSize,
  type ReceiptTemplate,
} from '../receipt/receiptTemplate';

type TemplateRecord = ReceiptTemplate & {
  id: string;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  created_by: string | null;
};

type NewForm = {
  name: string;
  paper_size: PaperSize;
  base_id: string;
};

const MAX_HEADER = 200;
const MAX_FOOTER = 500;
const MAX_WARRANTY = 2000;

const PREVIEW_METRICS: Record<PaperSize, { width: number; height: number; scale: number; frameHeight: number }> = {
  '80mm': { width: 302, height: 640, scale: 1, frameHeight: 640 },
  A4: { width: 794, height: 900, scale: 0.44, frameHeight: 400 },
  A5: { width: 559, height: 794, scale: 0.6, frameHeight: 485 },
  A6: { width: 397, height: 559, scale: 0.8, frameHeight: 455 },
};

function editablePayload(t: TemplateRecord) {
  return {
    name: t.name,
    paper_size: t.paper_size,
    is_active: t.is_active,
    show_logo: t.show_logo,
    header_text: t.header_text,
    show_address: t.show_address,
    show_phone: t.show_phone,
    show_email: t.show_email,
    show_customer_name: t.show_customer_name,
    show_customer_phone: t.show_customer_phone,
    show_item_description: t.show_item_description,
    show_item_code: t.show_item_code,
    show_unit_price: t.show_unit_price,
    show_warranty_info: t.show_warranty_info,
    show_repair_details: t.show_repair_details,
    show_payment_method: t.show_payment_method,
    show_cashier: t.show_cashier,
    show_customer_notes: t.show_customer_notes,
    logo_monochrome: t.logo_monochrome,
    footer_text: t.footer_text,
    warranty_terms: t.warranty_terms,
    show_footer_note: t.show_footer_note,
  };
}

function serialize(t: TemplateRecord): string {
  return JSON.stringify(editablePayload(t));
}

function Toggle({ label, hint, checked, onChange }: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="toggle-row" style={{ marginTop: 0 }}>
      <span><b>{label}</b>{hint && <small>{hint}</small>}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <i />
    </label>
  );
}

function EditorFrame({ modal, onRequestClose, children }: {
  modal: boolean;
  onRequestClose: () => void;
  children: ReactNode;
}) {
  const shellRef = useRef<HTMLDivElement>(null);

  // Modal safety: lock page scroll, move focus in, keep Tab inside.
  useEffect(() => {
    if (!modal) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    shellRef.current?.focus();
    return () => { document.body.style.overflow = previousOverflow; };
  }, [modal]);

  if (!modal) {
    return <div className="glass-panel settings-card invoice-template-card">{children}</div>;
  }

  function trapFocus(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab' || !shellRef.current) return;
    const focusable = shellRef.current.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      className="invoice-editor-overlay"
      role="presentation"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onRequestClose(); }}
    >
      <div
        className="invoice-editor-shell"
        role="dialog"
        aria-modal="true"
        aria-label="Invoice template editor"
        tabIndex={-1}
        ref={shellRef}
        onKeyDown={trapFocus}
      >
        <div className="invoice-editor-head">
          <div>
            <h2>Invoice Templates</h2>
            <p className="muted">Customize receipt layout for 80mm thermal, A4, A5 and A6 printing. The Lovely Tech branding line is locked and always printed last.</p>
          </div>
          <button type="button" className="modal-close" onClick={onRequestClose} aria-label="Close template editor">×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function InvoiceTemplateEditor({ isAdmin, mode = 'inline', onClose }: {
  isAdmin: boolean;
  mode?: 'inline' | 'modal';
  onClose?: () => void;
}) {
  const shop = useShopProfile();
  const modal = useModal();

  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<TemplateRecord | null>(null);
  const [baseline, setBaseline] = useState('');
  const [previewDraft, setPreviewDraft] = useState<TemplateRecord | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [fullShop, setFullShop] = useState<{ address?: string | null; phone?: string | null; email?: string | null } | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [newOpen, setNewOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newForm, setNewForm] = useState<NewForm>({ name: '', paper_size: '80mm', base_id: 'builtin' });

  const dirty = draft !== null && baseline !== '' && serialize(draft) !== baseline;
  const closeGuardRef = useRef<() => void>(() => {});

  async function load(preferredId?: string) {
    setLoading(true);
    setError('');
    try {
      const rows = await api<TemplateRecord[]>('/invoice-templates');
      setTemplates(rows);
      const pick = rows.find((t) => t.id === preferredId)
        ?? rows.find((t) => t.is_default && t.paper_size === '80mm')
        ?? rows[0];
      if (pick) {
        setSelectedId(pick.id);
        setDraft({ ...pick });
        setBaseline(serialize(pick));
      } else {
        setSelectedId(null);
        setDraft(null);
        setBaseline('');
      }
    } catch (e) {
      const message = (e as Error).message;
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!isAdmin) return;
    void load();
    (async () => {
      try { setFullShop(await api<{ address?: string | null; phone?: string | null; email?: string | null }>('/branch/profile')); } catch { /* preview still works */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  // Debounced live preview (300ms).
  useEffect(() => {
    if (!draft) {
      setPreviewDraft(null);
      return;
    }
    const id = window.setTimeout(() => setPreviewDraft({ ...draft }), 300);
    return () => window.clearTimeout(id);
  }, [draft]);

  // Render the preview asynchronously because the B&W logo conversion uses Canvas.
  useEffect(() => {
    if (!previewDraft) {
      setPreviewHtml('');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const html = await renderReceiptPreview(previewDraft, shop, fullShop);
        if (!cancelled) setPreviewHtml(html);
      } catch {
        if (!cancelled) setPreviewHtml('');
      }
    })();
    return () => { cancelled = true; };
  }, [previewDraft, shop, fullShop]);

  // Discard guard for tab close / reload.
  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  useEffect(() => {
    if (!newOpen) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !creating) setNewOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [newOpen, creating]);

  // Modal: Escape closes the editor, but unsaved drafts must be confirmed.
  useEffect(() => {
    if (mode !== 'modal') return;
    const handler = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || newOpen) return;
      event.preventDefault();
      event.stopPropagation();
      closeGuardRef.current();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [mode, newOpen]);

  // Keep the close guard pointing at the latest dirty/onClose values.
  useEffect(() => {
    closeGuardRef.current = () => { void requestClose(); };
  });

  if (!isAdmin) return null;

  async function requestClose() {
    if (dirty) {
      const ok = await modal.confirm({
        title: 'Discard unsaved changes?',
        message: 'The current template has unsaved changes. Closing the editor will discard them.',
        confirmText: 'Discard',
      });
      if (!ok) return;
    }
    onClose?.();
  }

  function patch(patchValue: Partial<TemplateRecord>) {
    setDraft((current) => current ? { ...current, ...patchValue } : current);
  }

  async function choose(template: TemplateRecord) {
    if (template.id === selectedId) return;
    if (dirty) {
      const ok = await modal.confirm({
        title: 'Discard unsaved changes?',
        message: 'The current template has unsaved changes. Switching will discard them.',
        confirmText: 'Discard',
      });
      if (!ok) return;
    }
    setSelectedId(template.id);
    setDraft({ ...template });
    setBaseline(serialize(template));
  }

  async function save() {
    if (!draft) return;
    if (!draft.name.trim()) {
      toast.error('Template name is required.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const result = await api<TemplateRecord>(`/invoice-templates/${draft.id}`, {
        method: 'PUT',
        body: JSON.stringify(editablePayload(draft)),
      });
      setTemplates((rows) => rows.map((t) => t.id === result.id ? result : t));
      setDraft({ ...result });
      setBaseline(serialize(result));
      toast.success('Invoice template saved.');
    } catch (e) {
      const message = (e as Error).message;
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  async function resetToDefaults() {
    if (!draft) return;
    const ok = await modal.confirm({
      title: 'Reset template?',
      message: 'All header, body and footer fields will return to the built-in defaults. The template name and paper size stay unchanged. Save afterwards to apply.',
      confirmText: 'Reset',
    });
    if (!ok) return;
    const defaults = DEFAULT_TEMPLATES[draft.paper_size];
    setDraft({
      ...draft,
      ...defaults,
      name: draft.name,
      paper_size: draft.paper_size,
      is_default: draft.is_default,
      is_active: draft.is_active,
    });
  }

  async function makeDefault(template: TemplateRecord) {
    try {
      const result = await api<TemplateRecord>(`/invoice-templates/${template.id}/set-default`, { method: 'POST' });
      setTemplates((rows) => rows.map((t) => {
        if (t.id === result.id) return result;
        if (t.paper_size === result.paper_size) return { ...t, is_default: false };
        return t;
      }));
      if (draft?.id === result.id) {
        setDraft((current) => current ? { ...current, is_default: true } : current);
      }
      toast.success(`Default ${result.paper_size} template updated.`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function remove(template: TemplateRecord) {
    const ok = await modal.confirm({
      title: 'Delete template?',
      message: `Delete "${template.name}"? This cannot be undone.`,
      confirmText: 'Delete',
    });
    if (!ok) return;
    try {
      await api(`/invoice-templates/${template.id}`, { method: 'DELETE' });
      toast.success('Template deleted.');
      await load(selectedId === template.id ? undefined : selectedId ?? undefined);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function create() {
    if (!newForm.name.trim()) {
      toast.error('Template name is required.');
      return;
    }
    setCreating(true);
    try {
      const base = newForm.base_id === 'builtin'
        ? undefined
        : templates.find((t) => t.id === newForm.base_id);
      const defaults = DEFAULT_TEMPLATES[newForm.paper_size];
      const seed: TemplateRecord = {
        ...(base ?? defaults),
        id: '',
        name: newForm.name.trim(),
        paper_size: newForm.paper_size,
        is_default: false,
        is_active: true,
        created_at: '',
        updated_at: '',
        created_by: null,
      };
      const result = await api<TemplateRecord>('/invoice-templates', {
        method: 'POST',
        body: JSON.stringify(editablePayload(seed)),
      });
      setNewOpen(false);
      setNewForm({ name: '', paper_size: '80mm', base_id: 'builtin' });
      toast.success('Template created.');
      await load(result.id);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return (
      <EditorFrame modal={mode === 'modal'} onRequestClose={() => closeGuardRef.current()}>
        {mode !== 'modal' && (
          <div className="settings-card-title">
            <div><h3>Invoice Template</h3><p className="muted">Loading templates…</p></div>
            <span className="settings-symbol">🧾</span>
          </div>
        )}
        <div style={{ textAlign: 'center', padding: '1rem' }}><span className="spinner" /></div>
      </EditorFrame>
    );
  }

  const previewPaper = previewDraft?.paper_size ?? '80mm';
  const previewMetrics = PREVIEW_METRICS[previewPaper];

  return (
    <EditorFrame modal={mode === 'modal'} onRequestClose={() => closeGuardRef.current()}>
      {mode !== 'modal' && (
        <div className="settings-card-title">
          <div>
            <h3>Invoice Template</h3>
            <p className="muted">Customize receipt layout for 80mm thermal, A4, A5 and A6 printing. The Lovely Tech branding line is locked and always printed last.</p>
          </div>
          <span className="settings-symbol">🧾</span>
        </div>
      )}

      {error && <div className="error-banner" role="alert" style={{ marginBottom: '0.75rem' }}><span>{error}</span></div>}

      <div className="invoice-editor-layout">
        <aside className="invoice-template-list">
          {templates.length === 0 && <p className="muted">No templates found. Create one to start printing.</p>}
          {templates.map((template) => (
            <button
              key={template.id}
              type="button"
              className={`invoice-template-item${template.id === selectedId ? ' selected' : ''}`}
              onClick={() => void choose(template)}
            >
              <span className="invoice-template-name">{template.name}</span>
              <span className="invoice-template-meta">
                <span className="invoice-paper-badge">{template.paper_size}</span>
                {template.is_default && <span className="invoice-default-badge">★ Default</span>}
                {!template.is_active && <span className="invoice-inactive-badge">Inactive</span>}
              </span>
            </button>
          ))}

          <button type="button" className="btn-secondary" style={{ marginTop: '0.5rem' }} onClick={() => setNewOpen(true)}>
            + New Template
          </button>

          {draft && (
            <div className="invoice-template-actions">
              <button type="button" className="btn-secondary" onClick={() => void makeDefault(draft)} disabled={draft.is_default}>
                Set as default
              </button>
              <button
                type="button"
                className="btn-secondary"
                style={{ color: '#dc2626' }}
                onClick={() => void remove(draft)}
                disabled={draft.is_default}
                title={draft.is_default ? 'Set another template as default first' : undefined}
              >
                Delete
              </button>
            </div>
          )}
        </aside>

        {draft ? (
          <div className="invoice-editor-main">
            <div>
              <div className="invoice-form-section">
                <h4>Template</h4>
                <div className="invoice-form-grid">
                  <label className="invoice-field">
                    <span>Name *</span>
                    <input value={draft.name} maxLength={100} onChange={(e) => patch({ name: e.target.value })} />
                    <small className="muted">{draft.name.length}/100</small>
                  </label>
                  <label className="invoice-field">
                    <span>Paper size</span>
                    <select value={draft.paper_size} onChange={(e) => patch({ paper_size: e.target.value as PaperSize })}>
                      <option value="80mm">80mm thermal</option>
                      <option value="A4">A4</option>
                      <option value="A5">A5</option>
                      <option value="A6">A6</option>
                    </select>
                  </label>
                  <Toggle label="Template active" hint="Inactive templates cannot be default or printed by new sales." checked={draft.is_active} onChange={(value) => patch({ is_active: value })} />
                  <Toggle label="Use as default for this paper size" hint="Print flows pick the default template automatically." checked={draft.is_default} onChange={() => {
                    if (!draft.is_default) void makeDefault(draft);
                  }} />
                </div>
              </div>

              <div className="invoice-form-section">
                <h4>Header</h4>
                <Toggle label="Show logo" hint="Uses the light logo from Shop Profile." checked={draft.show_logo} onChange={(value) => patch({ show_logo: value })} />
                {draft.paper_size === '80mm' && (
                  <Toggle
                    label="Monochrome logo (80mm)"
                    hint="Converts the light logo to 1-bit black & white for thermal printing."
                    checked={draft.logo_monochrome}
                    onChange={(value) => patch({ logo_monochrome: value })}
                  />
                )}
                <label className="invoice-field">
                  <span>Header text override</span>
                  <textarea
                    rows={2}
                    value={draft.header_text ?? ''}
                    maxLength={MAX_HEADER}
                    placeholder="Leave empty to use the shop name"
                    onChange={(e) => patch({ header_text: e.target.value || null })}
                  />
                  <small className="muted">{(draft.header_text ?? '').length}/{MAX_HEADER} · tokens: {'{shop_name}'} {'{phone}'}</small>
                </label>
                <div className="invoice-form-grid">
                  <Toggle label="Show address" checked={draft.show_address} onChange={(value) => patch({ show_address: value })} />
                  <Toggle label="Show phone" checked={draft.show_phone} onChange={(value) => patch({ show_phone: value })} />
                  <Toggle label="Show email" checked={draft.show_email} onChange={(value) => patch({ show_email: value })} />
                </div>
              </div>

              <div className="invoice-form-section">
                <h4>Body</h4>
                <div className="invoice-form-grid">
                  <Toggle label="Customer name" checked={draft.show_customer_name} onChange={(value) => patch({ show_customer_name: value })} />
                  <Toggle label="Customer phone" checked={draft.show_customer_phone} onChange={(value) => patch({ show_customer_phone: value })} />
                  <Toggle label="Item description" checked={draft.show_item_description} onChange={(value) => patch({ show_item_description: value })} />
                  <Toggle label="Item code" checked={draft.show_item_code} onChange={(value) => patch({ show_item_code: value })} />
                  <Toggle label="Unit price" hint="Hides the quantity × price line; line totals stay visible." checked={draft.show_unit_price} onChange={(value) => patch({ show_unit_price: value })} />
                  <Toggle label="Warranty terms" hint="Prints the warranty text below." checked={draft.show_warranty_info} onChange={(value) => patch({ show_warranty_info: value })} />
                  <Toggle label="Repair details" hint="Only shown when the sale carries repair information." checked={draft.show_repair_details} onChange={(value) => patch({ show_repair_details: value })} />
                  <Toggle label="Payment method" hint="Prints the payment mix (Cash, Card, Cash + Card)." checked={draft.show_payment_method} onChange={(value) => patch({ show_payment_method: value })} />
                  <Toggle label="Cashier" hint="Prints the cashier who completed the sale." checked={draft.show_cashier} onChange={(value) => patch({ show_cashier: value })} />
                  <Toggle label="Customer notes" hint="Prints notes saved on the customer record." checked={draft.show_customer_notes} onChange={(value) => patch({ show_customer_notes: value })} />
                </div>
              </div>

              <div className="invoice-form-section">
                <h4>Footer</h4>
                <label className="invoice-field">
                  <span>Footer note</span>
                  <textarea
                    rows={2}
                    value={draft.footer_text ?? ''}
                    maxLength={MAX_FOOTER}
                    placeholder="Thank you for shopping at {shop_name}!"
                    onChange={(e) => patch({ footer_text: e.target.value || null })}
                  />
                  <small className="muted">{(draft.footer_text ?? '').length}/{MAX_FOOTER} · tokens: {'{shop_name}'} {'{phone}'}</small>
                </label>
                <label className="invoice-field">
                  <span>Warranty terms / conditions</span>
                  <textarea
                    rows={4}
                    value={draft.warranty_terms ?? ''}
                    maxLength={MAX_WARRANTY}
                    placeholder="Warranty covers manufacturing defects only. Physical or liquid damage voids warranty."
                    onChange={(e) => patch({ warranty_terms: e.target.value || null })}
                  />
                  <small className="muted">{(draft.warranty_terms ?? '').length}/{MAX_WARRANTY}</small>
                </label>
                <Toggle label="Show footer note" checked={draft.show_footer_note} onChange={(value) => patch({ show_footer_note: value })} />

                <div className="invoice-locked-note" title="Required branding — cannot be edited">
                  <span aria-hidden="true">🔒</span>
                  <span>
                    <b>Software by Lovely Tech · {shop.getDeveloperPhone()}</b>
                    <small>Required branding — cannot be edited</small>
                  </span>
                </div>
              </div>

              <div className="button-row" style={{ marginTop: '1rem', flexWrap: 'wrap' }}>
                <button type="button" className="primary" onClick={() => void save()} disabled={saving || !dirty}>
                  {saving ? 'Saving…' : 'Save template'}
                </button>
                <button type="button" className="btn-secondary" onClick={() => void resetToDefaults()} disabled={saving}>
                  Reset to defaults
                </button>
                {dirty && <span className="muted" style={{ fontSize: '0.75rem', alignSelf: 'center' }}>Unsaved changes</span>}
              </div>
            </div>

            <div className="invoice-preview-pane">
              <div className="invoice-preview-title">
                <b>Live preview</b>
                <span className="invoice-paper-badge">{previewPaper}</span>
              </div>
              <div className="invoice-preview-frame" style={{ height: previewMetrics.frameHeight }}>
                {previewHtml
                  ? (
                    <iframe
                      title="Receipt preview"
                      srcDoc={previewHtml}
                      sandbox="allow-same-origin"
                      style={{
                        width: previewMetrics.width,
                        height: previewMetrics.height,
                        transform: previewMetrics.scale === 1 ? 'none' : `scale(${previewMetrics.scale})`,
                        transformOrigin: 'top left',
                        border: 'none',
                        background: '#fff',
                        display: 'block',
                      }}
                    />
                  )
                  : <p className="muted" style={{ padding: '1rem' }}>{previewDraft ? 'Preparing preview…' : 'Preview unavailable.'}</p>}
              </div>
              <p className="muted" style={{ fontSize: '0.7rem', margin: '0.4rem 0 0' }}>
                Preview updates 300ms after the last change and always prints on white paper.
              </p>
            </div>
          </div>
        ) : (
          <div className="empty-state" style={{ padding: '1.5rem' }}>
            <b>No templates</b>
            <span>Create a template to control the receipt layout.</span>
            <button type="button" onClick={() => setNewOpen(true)}>+ New Template</button>
          </div>
        )}
      </div>

      {newOpen && (
        <div
          className="invoice-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="New invoice template"
          onClick={() => { if (!creating) setNewOpen(false); }}
        >
          <div className="invoice-modal" onClick={(e) => e.stopPropagation()}>
            <h3>New invoice template</h3>
            <label className="invoice-field">
              <span>Name *</span>
              <input
                autoFocus
                value={newForm.name}
                maxLength={100}
                placeholder="e.g. Compact 80mm"
                onChange={(e) => setNewForm({ ...newForm, name: e.target.value })}
                onKeyDown={(e) => { if (e.key === 'Enter') void create(); }}
              />
            </label>
            <label className="invoice-field">
              <span>Paper size</span>
              <select value={newForm.paper_size} onChange={(e) => setNewForm({ ...newForm, paper_size: e.target.value as PaperSize })}>
                <option value="80mm">80mm thermal</option>
                <option value="A4">A4</option>
                <option value="A5">A5</option>
                <option value="A6">A6</option>
              </select>
            </label>
            <label className="invoice-field">
              <span>Start from</span>
              <select value={newForm.base_id} onChange={(e) => setNewForm({ ...newForm, base_id: e.target.value })}>
                <option value="builtin">Built-in defaults</option>
                {templates.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.paper_size})</option>)}
              </select>
            </label>
            <div className="button-row" style={{ marginTop: '1rem', justifyContent: 'flex-end' }}>
              <button type="button" className="btn-secondary" onClick={() => setNewOpen(false)} disabled={creating}>Cancel</button>
              <button type="button" className="primary" onClick={() => void create()} disabled={creating || !newForm.name.trim()}>
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </EditorFrame>
  );
}
