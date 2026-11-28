import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { Icon } from '../../components/Icon';
import { toast } from '../../ui/toast';
import { useModal } from '../../ui/modals';

type CategoryRow = { id: string; name: string; parent_id: string | null };
type ItemTypeRow = { id: string; code: string; name: string; is_serialized: boolean };
type MastersResponse = { categories?: CategoryRow[]; item_types?: ItemTypeRow[] };
type CategoryDraft = { id: string; name: string; parent_id: string | null };
type TypeDraft = { id: string; code: string; name: string; is_serialized: boolean; original_serialized: boolean };

export function slugifyTypeCode(name: string): string {
  return name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 50);
}

export function CategoryTypeManager({
  onClose,
  onError,
  onChanged,
}: {
  onClose: () => void;
  onError: (message: string) => void;
  onChanged?: () => Promise<void> | void;
}) {
  const modal = useModal();
  const [categories, setCategories] = useState<CategoryRow[]>([]);
  const [types, setTypes] = useState<ItemTypeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState('');
  const [categoryName, setCategoryName] = useState('');
  const [typeName, setTypeName] = useState('');
  const [typeCode, setTypeCode] = useState('');
  const [typeCodeTouched, setTypeCodeTouched] = useState(false);
  const [typeCodeOpen, setTypeCodeOpen] = useState(false);
  const [serialized, setSerialized] = useState(false);
  const [editCat, setEditCat] = useState<CategoryDraft | null>(null);
  const [editType, setEditType] = useState<TypeDraft | null>(null);
  const [editTypeCodeOpen, setEditTypeCodeOpen] = useState(false);

  const dialogRef = useRef<HTMLDivElement>(null);
  const firstFieldRef = useRef<HTMLInputElement>(null);
  const busyRef = useRef(false);
  const dirtyRef = useRef(false);
  const closeRef = useRef<() => void>(() => undefined);
  const confirmOpenRef = useRef(false);

  const effectiveTypeCode = typeCodeTouched ? typeCode : slugifyTypeCode(typeName);
  const dirty = categoryName.trim() !== ''
    || typeName.trim() !== ''
    || effectiveTypeCode.trim() !== ''
    || editCat !== null
    || editType !== null;
  busyRef.current = !!busy;
  dirtyRef.current = dirty;

  async function load() {
    setLoading(true);
    setLoadError('');
    try {
      const masters = await api<MastersResponse>('/items/masters');
      setCategories(masters.categories ?? []);
      setTypes(masters.item_types ?? []);
    } catch (err) {
      setLoadError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previous; };
  }, []);

  useEffect(() => {
    if (!loading) firstFieldRef.current?.focus();
  }, [loading]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => element.offsetParent !== null);
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
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  async function requestClose() {
    if (busyRef.current || confirmOpenRef.current) return;
    if (dirtyRef.current) {
      confirmOpenRef.current = true;
      try {
        const discard = await modal.confirm({
          title: 'Discard changes?',
          message: 'Unsaved category or item type text will be lost.',
          confirmText: 'Discard',
          cancelText: 'Keep editing',
        });
        if (!discard) return;
      } finally {
        confirmOpenRef.current = false;
      }
    }
    onClose();
  }
  closeRef.current = () => { void requestClose(); };

  async function notifyChanged() {
    if (!onChanged) return;
    try {
      await onChanged();
    } catch (err) {
      onError((err as Error).message);
    }
  }

  async function addCategory() {
    const name = categoryName.trim();
    if (!name || busyRef.current) return;
    setBusy('add-category');
    try {
      await api('/items/categories', { method: 'POST', body: JSON.stringify({ name }) });
      setCategoryName('');
      await load();
      await notifyChanged();
      toast.success('Category added');
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function saveCategory() {
    if (!editCat || busyRef.current) return;
    const name = editCat.name.trim();
    if (!name) { toast.error('Category name is required'); return; }
    setBusy('edit-category');
    try {
      await api(`/items/categories/${editCat.id}`, {
        method: 'PUT',
        body: JSON.stringify({ name, parent_id: editCat.parent_id || null }),
      });
      setEditCat(null);
      await load();
      await notifyChanged();
      toast.success('Category updated');
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function removeCategory(category: CategoryRow) {
    if (busyRef.current) return;
    const confirmed = await modal.confirm({
      title: 'Delete category?',
      message: `Delete “${category.name}”? This fails if any item or child category still uses it.`,
      confirmText: 'Delete category',
    });
    if (!confirmed) return;
    setBusy(`delete-category-${category.id}`);
    try {
      await api(`/items/categories/${category.id}`, { method: 'DELETE' });
      await load();
      await notifyChanged();
      toast.success('Category deleted');
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function addType() {
    const name = typeName.trim();
    const code = (typeCodeTouched ? typeCode : slugifyTypeCode(name)).trim().replace(/\s+/g, '_').slice(0, 50)
      || slugifyTypeCode(name);
    if (!name) { toast.error('Item type name is required'); return; }
    if (!code) { toast.error('Enter a code or a name that can generate one'); return; }
    if (busyRef.current) return;
    setBusy('add-type');
    try {
      await api('/items/item-types', {
        method: 'POST',
        body: JSON.stringify({ code, name, is_serialized: serialized }),
      });
      setTypeName('');
      setTypeCode('');
      setTypeCodeTouched(false);
      setTypeCodeOpen(false);
      setSerialized(false);
      await load();
      await notifyChanged();
      toast.success('Item type added');
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function saveType() {
    if (!editType || busyRef.current) return;
    const name = editType.name.trim();
    const code = (editType.code.trim() || slugifyTypeCode(name)).slice(0, 50);
    if (!name || !code) { toast.error('Item type code and name are required'); return; }
    if (editType.is_serialized !== editType.original_serialized) {
      const confirmed = await modal.confirm({
        title: 'Change serialized setting?',
        message: 'Items already using this type may need IMEI/serial handling. Change it anyway?',
        confirmText: 'Change setting',
      });
      if (!confirmed) return;
    }
    setBusy('edit-type');
    try {
      const result = await api<{ warning?: string }>(`/items/item-types/${editType.id}`, {
        method: 'PUT',
        body: JSON.stringify({ code, name, is_serialized: editType.is_serialized }),
      });
      setEditType(null);
      setEditTypeCodeOpen(false);
      await load();
      await notifyChanged();
      toast.success('Item type updated');
      if (result?.warning) toast.error(result.warning);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  async function removeType(type: ItemTypeRow) {
    if (busyRef.current) return;
    const confirmed = await modal.confirm({
      title: 'Delete item type?',
      message: `Delete “${type.name}”? This fails if any item still uses it.`,
      confirmText: 'Delete item type',
    });
    if (!confirmed) return;
    setBusy(`delete-type-${type.id}`);
    try {
      await api(`/items/item-types/${type.id}`, { method: 'DELETE' });
      await load();
      await notifyChanged();
      toast.success('Item type deleted');
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy('');
    }
  }

  function startEditType(type: ItemTypeRow) {
    setEditType({
      id: type.id,
      code: type.code,
      name: type.name,
      is_serialized: type.is_serialized,
      original_serialized: type.is_serialized,
    });
    setEditTypeCodeOpen(false);
  }

  const categoryOptions = categories.filter((category) => category.id !== editCat?.id);

  return (
    <div
      className="modal-overlay"
      onClick={(event) => { if (event.target === event.currentTarget && !busyRef.current) closeRef.current(); }}
    >
      <div
        ref={dialogRef}
        className="modal-card category-manager-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="category-manager-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <span className="eyebrow">ITEM MASTER</span>
            <h3 id="category-manager-title">Categories &amp; Item Types</h3>
          </div>
          <button type="button" className="modal-close" onClick={() => closeRef.current()} aria-label="Close" disabled={!!busy}><Icon name="close-x" size={16} /></button>
        </div>

        <div className="modal-body category-manager-body">
          {loadError && (
            <div className="modal-error-banner" role="alert">
              <div className="modal-error-banner-title"><span><Icon name="warning-triangle" size={14} /></span> Could not load categories and types</div>
              <div>{loadError}</div>
              <button type="button" className="ghost" onClick={() => void load()}>Retry</button>
            </div>
          )}

          {loading ? (
            <div className="category-manager-loading" aria-live="polite">
              <span className="spinner spinner-lg" aria-hidden="true" />
              <span>Loading categories and item types…</span>
            </div>
          ) : (
            <div className="category-manager-grid">
              <section className="category-manager-section" aria-labelledby="category-manager-categories">
                <div>
                  <h4 id="category-manager-categories">Categories</h4>
                  <p className="item-hint">Group items for filtering and colour tiles. Deletion is blocked while items still use a category.</p>
                </div>

                <div className="category-manager-form">
                  <input
                    ref={firstFieldRef}
                    value={categoryName}
                    maxLength={120}
                    placeholder="New category name"
                    aria-label="New category name"
                    onChange={(event) => setCategoryName(event.target.value)}
                    onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); void addCategory(); } }}
                  />
                  <button type="button" className="primary" disabled={!!busy || !categoryName.trim()} onClick={() => void addCategory()}>
                    {busy === 'add-category' ? 'Saving…' : 'Add Category'}
                  </button>
                </div>

                <div className="category-manager-list">
                  {categories.length === 0 && <p className="muted">No active categories.</p>}
                  {categories.map((category) => editCat && editCat.id === category.id ? (
                    <div className="category-manager-row" key={category.id}>
                      <input
                        value={editCat.name}
                        maxLength={120}
                        aria-label="Category name"
                        onChange={(event) => setEditCat({ ...editCat, name: event.target.value })}
                      />
                      <select
                        value={editCat.parent_id || ''}
                        aria-label="Parent category"
                        onChange={(event) => setEditCat({ ...editCat, parent_id: event.target.value || null })}
                      >
                        <option value="">No parent</option>
                        {categoryOptions.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}
                      </select>
                      <span className="category-manager-actions">
                        <button type="button" disabled={busy === 'edit-category'} onClick={() => void saveCategory()}>
                          {busy === 'edit-category' ? 'Saving…' : 'Save'}
                        </button>
                        <button type="button" className="ghost" disabled={busy === 'edit-category'} onClick={() => setEditCat(null)}>Cancel</button>
                      </span>
                    </div>
                  ) : (
                    <div className="category-manager-row" key={category.id}>
                      <span className="category-manager-name">{category.name}</span>
                      <span className="category-manager-actions">
                        <button
                          type="button"
                          className="ghost"
                          disabled={!!busy}
                          onClick={() => setEditCat({ id: category.id, name: category.name, parent_id: category.parent_id || null })}
                        >Edit</button>
                        <button
                          type="button"
                          className="danger-button"
                          disabled={!!busy}
                          onClick={() => void removeCategory(category)}
                        >{busy === `delete-category-${category.id}` ? 'Deleting…' : 'Delete'}</button>
                      </span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="category-manager-section" aria-labelledby="category-manager-types">
                <div>
                  <h4 id="category-manager-types">Item Types</h4>
                  <p className="item-hint">Codes are generated from the name. Open Advanced only when a specific code is required.</p>
                </div>

                <div className="category-manager-form category-manager-type-form">
                  <input
                    value={typeName}
                    maxLength={120}
                    placeholder="Item type name"
                    aria-label="Item type name"
                    onChange={(event) => setTypeName(event.target.value)}
                    onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); void addType(); } }}
                  />
                  <label className="check">
                    <input type="checkbox" checked={serialized} onChange={(event) => setSerialized(event.target.checked)} />
                    Serialized / IMEI
                  </label>
                  <button
                    type="button"
                    className="ghost category-manager-advanced-toggle"
                    aria-expanded={typeCodeOpen}
                    onClick={() => setTypeCodeOpen((value) => !value)}
                  >{typeCodeOpen ? 'Hide advanced' : 'Advanced'}</button>
                  <button type="button" className="primary" disabled={!!busy || !typeName.trim()} onClick={() => void addType()}>
                    {busy === 'add-type' ? 'Saving…' : 'Add Item Type'}
                  </button>
                  {typeCodeOpen && (
                    <div className="category-manager-advanced wide-field">
                      <label htmlFor="new-type-code">Code (auto from name)</label>
                      <input
                        id="new-type-code"
                        value={typeCodeTouched ? typeCode : slugifyTypeCode(typeName)}
                        maxLength={50}
                        placeholder="e.g. screen"
                        onChange={(event) => { setTypeCode(event.target.value); setTypeCodeTouched(true); }}
                      />
                      <small className="item-hint">Lowercase letters, numbers and underscores. Leave blank to keep the auto code.</small>
                    </div>
                  )}
                </div>

                <div className="category-manager-list">
                  {types.length === 0 && <p className="muted">No active item types.</p>}
                  {types.map((type) => editType && editType.id === type.id ? (
                    <div className="category-manager-row category-manager-type-row" key={type.id}>
                      <input
                        value={editType.name}
                        maxLength={120}
                        aria-label="Item type name"
                        onChange={(event) => setEditType({ ...editType, name: event.target.value })}
                      />
                      <label className="check">
                        <input
                          type="checkbox"
                          checked={editType.is_serialized}
                          onChange={(event) => setEditType({ ...editType, is_serialized: event.target.checked })}
                        />
                        IMEI
                      </label>
                      <button
                        type="button"
                        className="ghost category-manager-advanced-toggle"
                        aria-expanded={editTypeCodeOpen}
                        onClick={() => setEditTypeCodeOpen((value) => !value)}
                      >{editTypeCodeOpen ? 'Hide code' : 'Code'}</button>
                      {editTypeCodeOpen && (
                        <input
                          value={editType.code}
                          maxLength={50}
                          aria-label="Item type code"
                          onChange={(event) => setEditType({ ...editType, code: event.target.value })}
                        />
                      )}
                      <span className="category-manager-actions">
                        <button type="button" disabled={busy === 'edit-type'} onClick={() => void saveType()}>
                          {busy === 'edit-type' ? 'Saving…' : 'Save'}
                        </button>
                        <button
                          type="button"
                          className="ghost"
                          disabled={busy === 'edit-type'}
                          onClick={() => { setEditType(null); setEditTypeCodeOpen(false); }}
                        >Cancel</button>
                      </span>
                    </div>
                  ) : (
                    <div className="category-manager-row" key={type.id}>
                      <span className="category-manager-name">
                        <b className="category-manager-code">{type.code}</b>
                        {type.name}
                        {type.is_serialized ? <span className="category-manager-tag">IMEI</span> : null}
                      </span>
                      <span className="category-manager-actions">
                        <button type="button" className="ghost" disabled={!!busy} onClick={() => startEditType(type)}>Edit</button>
                        <button
                          type="button"
                          className="danger-button"
                          disabled={!!busy}
                          onClick={() => void removeType(type)}
                        >{busy === `delete-type-${type.id}` ? 'Deleting…' : 'Delete'}</button>
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}
        </div>

        <div className="modal-actions">
          <button type="button" className="btn-secondary" onClick={() => closeRef.current()} disabled={!!busy}>Close</button>
        </div>
      </div>
    </div>
  );
}
