import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { api } from '../../api/client';
import { money } from '../../services/money';
import { moneyInputProps } from '../../utils/numberInput';
import { toast } from '../../ui/toast';
import { useModal } from '../../ui/modals';
import { CategoryTypeManager } from './CategoryTypeManager';

type Category = { id: string; name: string; parent_id: string | null };
type ItemType = { id: string; code: string; name: string; is_serialized: boolean };
type Masters = { categories: Category[]; item_types: ItemType[] };
type WarrantyDefault = { warranty_type: string; duration_value: number | null; custom_rule: string | null };
type ItemRow = {
  item_id: string;
  item_code: string;
  description: string;
  brand: string | null;
  model: string | null;
  compatible_models: string | null;
  category_id: string;
  item_type_id: string;
  master_sale_price: string | number | null;
  low_stock_threshold: number;
  version: number;
  is_active: boolean;
  barcodes: string[];
  warranty_default: WarrantyDefault | null;
};
type VariantRow = { variant_id: string; name: string; value: string };
type StockRow = { item_id: string; stock: string | number };

type StockFilter = 'ALL' | 'IN' | 'LOW' | 'OUT';
type ViewMode = 'grid' | 'list';

const DEFAULT_LOW_STOCK = 5;
const TILE_HUES = [6, 28, 45, 88, 148, 192, 216, 262, 312];
const EMPTY_MASTERS: Masters = { categories: [], item_types: [] };

function tileHue(categoryId: string): number {
  let hash = 0;
  for (let i = 0; i < categoryId.length; i += 1) {
    hash = (hash * 31 + categoryId.charCodeAt(i)) % 100000;
  }
  return TILE_HUES[hash % TILE_HUES.length];
}

function initialOf(name: string): string {
  const first = Array.from(name.trim())[0];
  return first ? first.toUpperCase() : '?';
}

function numericStock(value: string | number | null | undefined): number {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
}

function lowStockThreshold(item: Pick<ItemRow, 'low_stock_threshold'>): number {
  const value = Number(item.low_stock_threshold);
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : DEFAULT_LOW_STOCK;
}

function stockTone(stock: number | null, threshold: number): 'ok' | 'low' | 'out' | 'unknown' {
  if (stock === null) return 'unknown';
  if (stock <= 0) return 'out';
  if (stock <= threshold) return 'low';
  return 'ok';
}

function stockLabel(stock: number | null, threshold: number): string {
  if (stock === null) return '—';
  if (stock <= 0) return 'Out';
  if (stock <= threshold) return `${stock} left`;
  return String(stock);
}

function stockFilterMatch(filter: StockFilter, stock: number | null, threshold: number): boolean {
  if (filter === 'ALL') return true;
  if (stock === null) return false;
  if (filter === 'OUT') return stock <= 0;
  if (filter === 'LOW') return stock > 0 && stock <= threshold;
  return stock > threshold;
}

export function ItemsWorkspace({ isAdmin, onError }: { isAdmin: boolean; onError: (message: string) => void }) {
  const modal = useModal();
  const [rows, setRows] = useState<ItemRow[]>([]);
  const [masters, setMasters] = useState<Masters>(EMPTY_MASTERS);
  const [stockMap, setStockMap] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [stockFilter, setStockFilter] = useState<StockFilter>('ALL');
  const [view, setView] = useState<ViewMode>('grid');
  const [showInactive, setShowInactive] = useState(false);
  const [modalItem, setModalItem] = useState<ItemRow | 'new' | null>(null);
  const [masterManagerOpen, setMasterManagerOpen] = useState(false);
  const [reactivatingId, setReactivatingId] = useState<string | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const masterManagerTriggerRef = useRef<HTMLElement | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [items, masterData, stockRows] = await Promise.all([
        api<ItemRow[]>('/items/admin-list'),
        api<Masters>('/items/masters'),
        api<StockRow[]>('/inventory/summary').catch(() => null),
      ]);
      setRows(items);
      setMasters(masterData);
      if (stockRows) {
        const next: Record<string, number> = {};
        stockRows.forEach((row) => { next[row.item_id] = numericStock(row.stock); });
        setStockMap(next);
      } else {
        setStockMap(null);
      }
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function refreshMasters(): Promise<Masters> {
    const masterData = await api<Masters>('/items/masters');
    setMasters(masterData);
    return masterData;
  }

  useEffect(() => { void load(); }, []);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedQuery(query), 300);
    return () => window.clearTimeout(id);
  }, [query]);

  const categoryNames = useMemo(() => {
    const map = new Map<string, string>();
    masters.categories.forEach((category) => map.set(category.id, category.name));
    return map;
  }, [masters.categories]);

  const filtered = useMemo(() => {
    const term = debouncedQuery.trim().toLowerCase();
    return rows.filter((item) => {
      if (!item.is_active && !(isAdmin && showInactive)) return false;
      if (categoryId && item.category_id !== categoryId) return false;
      const stock = stockMap && item.item_id in stockMap ? stockMap[item.item_id] : null;
      if (!stockFilterMatch(stockFilter, stock, lowStockThreshold(item))) return false;
      if (!term) return true;
      const haystack = [
        item.description,
        item.item_code,
        item.brand ?? '',
        item.model ?? '',
        item.compatible_models ?? '',
        item.barcodes.join(' '),
      ].join(' ').toLowerCase();
      return haystack.includes(term);
    });
  }, [rows, debouncedQuery, categoryId, stockFilter, stockMap, isAdmin, showInactive]);

  const hasFilters = !!query.trim() || !!categoryId || stockFilter !== 'ALL' || showInactive;

  function clearFilters() {
    setQuery('');
    setDebouncedQuery('');
    setCategoryId('');
    setStockFilter('ALL');
    setShowInactive(false);
  }

  function openItem(item: ItemRow) {
    triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setModalItem(item);
  }

  function addItem() {
    triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setModalItem('new');
  }

  function closeModal() {
    setModalItem(null);
    window.setTimeout(() => triggerRef.current?.focus(), 0);
  }

  function openMasterManager() {
    masterManagerTriggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setMasterManagerOpen(true);
  }

  function closeMasterManager() {
    setMasterManagerOpen(false);
    window.setTimeout(() => masterManagerTriggerRef.current?.focus(), 0);
  }

  async function reactivateItem(item: ItemRow) {
    if (reactivatingId) return;
    const confirmed = await modal.confirm({
      title: 'Reactivate item?',
      message: `“${item.description}” will be active again in the item list and POS. Stock and history are unchanged.`,
      confirmText: 'Reactivate item',
      cancelText: 'Keep inactive',
    });
    if (!confirmed) return;
    setReactivatingId(item.item_id);
    try {
      await api(`/items/${item.item_id}/reactivate`, { method: 'POST' });
      await load();
      toast.success('Item reactivated');
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setReactivatingId(null);
    }
  }

  return (
    <section className="items-page">
      <div className="glass panel page-intro rise-in">
        <span className="eyebrow">INVENTORY MASTER</span>
        <div className="section-head">
          <div>
            <h2>Items</h2>
            <p className="muted">
              {isAdmin
                ? 'Create or edit items, prices, barcodes, warranties and compatibility.'
                : 'Read-only item master. Ask an Admin to create or edit items.'}
            </p>
          </div>
          <div className="button-row">
            {isAdmin && <button className="ghost" onClick={openMasterManager}>Manage Categories &amp; Types</button>}
            {isAdmin && <button className="primary" onClick={addItem}>+ Add Item</button>}
            <span className="feature-badge">FIFO • IMEI • BARCODE</span>
          </div>
        </div>
      </div>

      <div className="glass panel items-toolbar">
        <div className="items-search">
          <span className="items-search-icon" aria-hidden="true">⌕</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search name, barcode or item code…"
            aria-label="Search items"
          />
          {query && (
            <button type="button" className="items-search-clear" onClick={() => setQuery('')} aria-label="Clear search">×</button>
          )}
        </div>

        <select
          className="items-filter-select"
          value={categoryId}
          onChange={(event) => setCategoryId(event.target.value)}
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {masters.categories.map((category) => (
            <option key={category.id} value={category.id}>{category.name}</option>
          ))}
        </select>

        <select
          className="items-filter-select"
          value={stockFilter}
          onChange={(event) => setStockFilter(event.target.value as StockFilter)}
          aria-label="Filter by stock level"
          disabled={stockMap === null}
          title={stockMap === null ? 'Stock levels are unavailable for this account' : undefined}
        >
          <option value="ALL">All stock</option>
          <option value="IN">In stock</option>
          <option value="LOW">Low stock (at or below alert)</option>
          <option value="OUT">Out of stock</option>
        </select>

        <div className="items-view-toggle" role="group" aria-label="View mode">
          <button
            type="button"
            className={view === 'grid' ? 'selected' : ''}
            onClick={() => setView('grid')}
            aria-pressed={view === 'grid'}
          >
            <span aria-hidden="true">▦</span> Grid
          </button>
          <button
            type="button"
            className={view === 'list' ? 'selected' : ''}
            onClick={() => setView('list')}
            aria-pressed={view === 'list'}
          >
            <span aria-hidden="true">☰</span> List
          </button>
        </div>

        {isAdmin && (
          <button
            type="button"
            className="ghost"
            onClick={() => setShowInactive((value) => !value)}
            aria-pressed={showInactive}
            title="Include deactivated items for audit"
          >
            {showInactive ? 'Hide inactive' : 'Show inactive'}
          </button>
        )}

        <button type="button" className="ghost items-refresh" onClick={() => void load()} disabled={loading}>
          {loading ? 'Refreshing…' : '⟳ Refresh'}
        </button>
      </div>

      <div className="items-result-bar">
        <span>{loading ? 'Loading items…' : `${filtered.length} of ${rows.length} item${rows.length === 1 ? '' : 's'}`}</span>
        {stockMap === null && !loading && <span className="items-result-note">Stock levels unavailable for this account</span>}
        {hasFilters && <button type="button" className="items-clear-link" onClick={clearFilters}>Clear filters</button>}
      </div>

      {loading && (
        <div className={view === 'grid' ? 'items-grid' : 'items-list'} aria-busy="true" aria-live="polite">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className={view === 'grid' ? 'inv-card inv-skeleton' : 'items-list-row inv-skeleton-row'}>
              <span className="skeleton-block" />
              <span className="skeleton-line" />
              <span className="skeleton-line short" />
            </div>
          ))}
        </div>
      )}

      {!loading && rows.length === 0 && (
        <div className="empty-state items-empty">
          <span className="items-empty-icon" aria-hidden="true">📦</span>
          <b>No items yet</b>
          <span>{isAdmin ? 'Add your first item to start selling, tracking stock and scanning barcodes.' : 'Ask an Admin to add items to the shop.'}</span>
          {isAdmin && <button className="primary" onClick={addItem}>+ Add First Item</button>}
        </div>
      )}

      {!loading && rows.length > 0 && filtered.length === 0 && (
        <div className="empty-state items-empty">
          <span className="items-empty-icon" aria-hidden="true">🔍</span>
          <b>No items match</b>
          <span>Try a different name, barcode or item code, or clear the filters.</span>
          <button className="ghost" onClick={clearFilters}>Clear filters</button>
        </div>
      )}

      {!loading && filtered.length > 0 && view === 'grid' && (
        <div className="items-grid">
          {filtered.map((item) => {
            const stock = stockMap && item.item_id in stockMap ? stockMap[item.item_id] : null;
            const threshold = lowStockThreshold(item);
            const tone = stockTone(stock, threshold);
            const stockTitle = stock === null
              ? 'Stock unavailable'
              : `${stock} unit${stock === 1 ? '' : 's'} in stock · low stock threshold: ${threshold}${stock > 0 && stock <= threshold ? ` · Low stock alert (≤${threshold})` : ''}`;
            const tileStyle = { '--tile-h': String(tileHue(item.category_id)) } as CSSProperties;
            const categoryName = categoryNames.get(item.category_id) ?? 'Uncategorized';
            return (
              <article key={item.item_id} className={`inv-card tone-${tone}${item.is_active ? '' : ' inv-card-inactive'}`}>
                <button type="button" className="inv-card-open" onClick={() => openItem(item)} aria-label={`Open ${item.description}`}>
                  <div className="inv-card-media" style={tileStyle}>
                    <span className="inv-card-initial" aria-hidden="true">{initialOf(item.description)}</span>
                    {!item.is_active && <span className="status-badge status-danger inv-inactive-badge">INACTIVE</span>}
                    <span className={`inv-stock-chip tone-${tone}`} title={stockTitle}>
                      {stockLabel(stock, threshold)}
                    </span>
                    {tone === 'out' && <span className="inv-card-out">Out of stock</span>}
                  </div>
                  <div className="inv-card-body">
                    <b className="inv-card-name" title={item.description}>{item.description}</b>
                    <span className="inv-card-category">{categoryName}</span>
                    <span className="inv-card-price">{item.master_sale_price == null ? 'No price' : `Rs. ${money(item.master_sale_price)}`}</span>
                  </div>
                </button>
                {isAdmin && (
                  item.is_active ? (
                    <button type="button" className="inv-card-edit" onClick={() => openItem(item)} aria-label={`Edit ${item.description}`}>
                      <span aria-hidden="true">✎</span> Edit
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="inv-card-edit inv-card-reactivate"
                      onClick={() => void reactivateItem(item)}
                      disabled={reactivatingId !== null}
                      aria-label={`Reactivate ${item.description}`}
                    >
                      {reactivatingId === item.item_id ? 'Reactivating…' : 'Reactivate'}
                    </button>
                  )
                )}
              </article>
            );
          })}
        </div>
      )}

      {!loading && filtered.length > 0 && view === 'list' && (
        <div className="glass panel items-list">
          {filtered.map((item) => {
            const stock = stockMap && item.item_id in stockMap ? stockMap[item.item_id] : null;
            const threshold = lowStockThreshold(item);
            const tone = stockTone(stock, threshold);
            const stockTitle = stock === null
              ? 'Stock unavailable'
              : `${stock} unit${stock === 1 ? '' : 's'} in stock · low stock threshold: ${threshold}`;
            return (
              <div key={item.item_id} className="items-list-row">
                <button type="button" className="items-list-main" onClick={() => openItem(item)}>
                  <span className="items-list-code">{item.item_code}</span>
                  <span className="items-list-name">{item.description}</span>
                  <span className="items-list-meta">
                    {[item.brand, item.model].filter(Boolean).join(' · ') || 'No brand / model'}
                    {item.barcodes.length > 0 ? ` · ${item.barcodes.join(', ')}` : ' · No barcode'}
                    {!item.is_active ? ' · INACTIVE' : ''}
                  </span>
                </button>
                <span className="items-list-category">{categoryNames.get(item.category_id) ?? 'Uncategorized'}</span>
                <span className={`items-list-stock tone-${tone}`} title={stockTitle}>{stock === null ? '—' : `${stock} in stock`}</span>
                <span className="items-list-price">{item.master_sale_price == null ? 'No price' : `Rs. ${money(item.master_sale_price)}`}</span>
                {isAdmin && (
                  item.is_active ? (
                    <button type="button" className="ghost" onClick={() => openItem(item)}>Edit</button>
                  ) : (
                    <button
                      type="button"
                      className="primary items-reactivate-btn"
                      onClick={() => void reactivateItem(item)}
                      disabled={reactivatingId !== null}
                    >
                      {reactivatingId === item.item_id ? 'Reactivating…' : 'Reactivate'}
                    </button>
                  )
                )}
              </div>
            );
          })}
        </div>
      )}

      {modalItem !== null && (
        <ItemFormModal
          item={modalItem === 'new' ? null : modalItem}
          masters={masters}
          readOnly={!isAdmin}
          onClose={closeModal}
          onSaved={load}
          onRefreshMasters={refreshMasters}
        />
      )}

      {masterManagerOpen && (
        <CategoryTypeManager
          onClose={closeMasterManager}
          onError={onError}
          onChanged={async () => { await refreshMasters(); }}
        />
      )}
    </section>
  );
}

type ItemFormState = {
  description: string;
  category_id: string;
  item_type_id: string;
  brand: string;
  model: string;
  compatible_models: string;
  master_sale_price: string;
  low_stock_threshold: string;
  barcode: string;
  warranty_type: string;
  duration_value: string;
  custom_rule: string;
};

function buildInitialState(item: ItemRow | null): ItemFormState {
  return {
    description: item?.description ?? '',
    category_id: item?.category_id ?? '',
    item_type_id: item?.item_type_id ?? '',
    brand: item?.brand ?? '',
    model: item?.model ?? '',
    compatible_models: item?.compatible_models ?? '',
    master_sale_price: item?.master_sale_price == null ? '' : String(item.master_sale_price),
    low_stock_threshold: String(item?.low_stock_threshold ?? DEFAULT_LOW_STOCK),
    barcode: '',
    warranty_type: item?.warranty_default?.warranty_type ?? 'NONE',
    duration_value: item?.warranty_default?.duration_value == null ? '' : String(item.warranty_default.duration_value),
    custom_rule: item?.warranty_default?.custom_rule ?? '',
  };
}

function typeCodeFromName(name: string): string {
  return name
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 50);
}

function ItemFormModal({
  item,
  masters,
  readOnly,
  onClose,
  onSaved,
  onRefreshMasters,
}: {
  item: ItemRow | null;
  masters: Masters;
  readOnly: boolean;
  onClose: () => void;
  onSaved: () => Promise<void> | void;
  onRefreshMasters: () => Promise<Masters>;
}) {
  const modal = useModal();
  const [form, setForm] = useState<ItemFormState>(() => buildInitialState(item));
  const [initial] = useState<ItemFormState>(() => buildInitialState(item));
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [serverError, setServerError] = useState('');
  const [deactivating, setDeactivating] = useState(false);
  const [reactivating, setReactivating] = useState(false);
  const [nameCheck, setNameCheck] = useState<{ value: string; exists: boolean; checking: boolean }>({ value: '', exists: false, checking: false });
  const nameCheckSeq = useRef(0);
  const [busy, setBusy] = useState(false);
  const [variants, setVariants] = useState<VariantRow[]>([]);
  const [variantsLoading, setVariantsLoading] = useState(false);
  const [variantName, setVariantName] = useState('');
  const [variantValue, setVariantValue] = useState('');
  const [variantBusy, setVariantBusy] = useState(false);
  const [masterModal, setMasterModal] = useState<'category' | 'type' | null>(null);
  const [masterError, setMasterError] = useState('');
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newTypeCode, setNewTypeCode] = useState('');
  const [newTypeCodeTouched, setNewTypeCodeTouched] = useState(false);
  const [newTypeAdvancedOpen, setNewTypeAdvancedOpen] = useState(false);
  const [newTypeName, setNewTypeName] = useState('');
  const [newTypeSerialized, setNewTypeSerialized] = useState(false);
  const [masterBusy, setMasterBusy] = useState(false);
  const masterBackdropDownRef = useRef(false);
  const masterConfirmRef = useRef(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const barcodeRef = useRef<HTMLInputElement>(null);
  const confirmOpenRef = useRef(false);

  const dirty = JSON.stringify(form) !== JSON.stringify(initial) || variantName.trim() !== '' || variantValue.trim() !== '';
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const busyRef = useRef(busy);
  busyRef.current = busy;

  useEffect(() => {
    if (!readOnly) nameRef.current?.focus();
  }, [readOnly]);

  useEffect(() => {
    if (!item) return;
    let live = true;
    setVariantsLoading(true);
    api<VariantRow[]>(`/items/${item.item_id}/variants`)
      .then((rows) => { if (live) setVariants(rows); })
      .catch(() => { if (live) setVariants([]); })
      .finally(() => { if (live) setVariantsLoading(false); });
    return () => { live = false; };
  }, [item]);

  // Debounced duplicate-name probe (also runs on blur). Server 422 remains the final guard.
  useEffect(() => {
    if (readOnly) return;
    const value = form.description.trim();
    if (!value) {
      setNameCheck({ value: '', exists: false, checking: false });
      return;
    }
    if (item && value.toLowerCase() === item.description.trim().toLowerCase()) {
      setNameCheck({ value, exists: false, checking: false });
      return;
    }
    const id = window.setTimeout(() => { void checkName(value); }, 500);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.description, readOnly, item?.item_id]);

  async function checkName(raw: string) {
    const value = raw.trim();
    if (!value || (item && value.toLowerCase() === item.description.trim().toLowerCase())) {
      setNameCheck({ value, exists: false, checking: false });
      return;
    }
    const seq = ++nameCheckSeq.current;
    setNameCheck({ value, exists: false, checking: true });
    try {
      const params = new URLSearchParams({ name: value });
      if (item) params.set('exclude_id', item.item_id);
      const result = await api<{ exists: boolean }>(`/items/check-name?${params.toString()}`);
      if (seq !== nameCheckSeq.current) return;
      setNameCheck({ value, exists: !!result.exists, checking: false });
    } catch {
      if (seq === nameCheckSeq.current) setNameCheck({ value, exists: false, checking: false });
    }
  }

  async function requestClose() {
    if (busyRef.current || confirmOpenRef.current) return;
    if (dirtyRef.current) {
      confirmOpenRef.current = true;
      try {
        const discard = await modal.confirm({
          title: 'Discard changes?',
          message: 'You have unsaved changes. Close this form and lose them?',
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

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      if (masterModal) { void requestCloseMaster(); return; }
      void requestClose();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  // G3 — warn before the whole app window is closed with unsaved edits.
  useEffect(() => {
    function onBeforeUnload(event: BeforeUnloadEvent) {
      if (!dirtyRef.current || busyRef.current) return;
      event.preventDefault();
      event.returnValue = '';
    }
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, []);

  // Keep the page behind the modal from scrolling (mobile / small laptops).
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previous; };
  }, []);

  function patch<K extends keyof ItemFormState>(key: K, value: ItemFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function markTouched(field: string) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  const priceValue = form.master_sale_price.trim();
  const priceNumber = Number(priceValue);
  const errors = {
    description: !form.description.trim()
      ? 'Item name is required'
      : form.description.trim().length > 255
        ? 'Maximum 255 characters'
        : null,
    category_id: form.category_id ? null : 'Category is required',
    item_type_id: form.item_type_id ? null : 'Item type is required',
    master_sale_price: !priceValue
      ? 'Sale price is required'
      : !Number.isFinite(priceNumber)
        ? 'Enter a valid amount'
        : priceNumber < 0
          ? 'Price cannot be negative'
          : priceNumber > 999999999.99
            ? 'Amount is too large'
            : null,
    barcode: form.barcode.trim().length > 100 ? 'Maximum 100 characters' : null,
    low_stock_threshold: !form.low_stock_threshold.trim()
      ? 'Low stock alert is required'
      : !/^\d+$/.test(form.low_stock_threshold.trim())
        ? 'Enter a whole number'
        : Number(form.low_stock_threshold) > 1000000
          ? 'Threshold is too large'
          : null,
    warranty:
      (form.warranty_type === 'DAYS' || form.warranty_type === 'MONTHS') && !form.duration_value.trim()
        ? 'Warranty duration is required'
        : (form.warranty_type === 'DAYS' || form.warranty_type === 'MONTHS') && Number(form.duration_value) < 1
          ? 'Duration must be at least 1'
          : form.warranty_type === 'CUSTOM' && !form.custom_rule.trim()
            ? 'Custom warranty rule is required'
            : null,
  };
  const nameExists = nameCheck.exists && nameCheck.value === form.description.trim();
  const canSave = !readOnly && !nameExists && Object.values(errors).every((value) => !value) && !busy;
  const showError = (field: keyof typeof errors) => !!errors[field] && (touched[field] || submitAttempted);
  const serverDuplicateError = serverError && /name already exists/i.test(serverError) ? 'Item with this name already exists' : '';
  const duplicateNameError = nameExists ? 'Item with this name already exists' : serverDuplicateError;
  const categoryOptions = useMemo(() => {
    const options = masters.categories.slice();
    if (form.category_id && !options.some((category) => category.id === form.category_id)) {
      options.push({ id: form.category_id, name: 'Inactive category', parent_id: null });
    }
    return options;
  }, [masters.categories, form.category_id]);
  const itemTypeOptions = useMemo(() => {
    const options = masters.item_types.slice();
    if (form.item_type_id && !options.some((type) => type.id === form.item_type_id)) {
      options.push({ id: form.item_type_id, code: 'INACTIVE', name: 'Inactive item type', is_serialized: false });
    }
    return options;
  }, [masters.item_types, form.item_type_id]);
  const categoryName = categoryOptions.find((category) => category.id === form.category_id)?.name ?? 'No category';
  const itemTypeName = itemTypeOptions.find((type) => type.id === form.item_type_id)?.name ?? 'No item type';

  async function save() {
    setSubmitAttempted(true);
    setTouched({
      description: true, category_id: true, item_type_id: true,
      master_sale_price: true, barcode: true, warranty: true, low_stock_threshold: true,
    });
    if (!canSave) {
      toast.error('Please fix the highlighted fields');
      return;
    }

    const payload = {
      description: form.description.trim(),
      category_id: form.category_id,
      item_type_id: form.item_type_id,
      brand: form.brand.trim() || null,
      model: form.model.trim() || null,
      compatible_models: form.compatible_models.trim() || null,
      master_sale_price: priceValue.endsWith('.') ? priceValue.slice(0, -1) : priceValue,
      low_stock_threshold: Number(form.low_stock_threshold),
      version: item?.version,
    };

    setBusy(true);
    setServerError('');
    let itemId = item?.item_id ?? '';
    let saved = false;
    try {
      if (item) {
        await api(`/items/${item.item_id}`, { method: 'PUT', body: JSON.stringify(payload) });
        itemId = item.item_id;
      } else {
        const created = await api<{ item_id: string; item_code: string }>('/items', {
          method: 'POST',
          body: JSON.stringify({ ...payload, version: undefined, barcode: form.barcode.trim() || null }),
        });
        itemId = created.item_id;
      }
      saved = true;

      try {
        await api(`/items/${itemId}/warranty-default`, {
          method: 'PUT',
          body: JSON.stringify({
            warranty_type: form.warranty_type,
            duration_value: form.duration_value.trim() ? Number(form.duration_value) : null,
            custom_rule: form.custom_rule.trim() || null,
          }),
        });
      } catch (warrantyErr) {
        toast.error(`Item saved, but the warranty default failed: ${(warrantyErr as Error).message}`);
        await onSaved();
        onClose();
        return;
      }

      if (item && form.barcode.trim()) {
        await api(`/items/${itemId}/barcodes`, {
          method: 'POST',
          body: JSON.stringify({ barcode: form.barcode.trim(), is_primary: item.barcodes.length === 0 }),
        });
      }

      toast.success(item ? 'Item updated' : 'Item created');
      await onSaved();
      onClose();
    } catch (err) {
      if (saved) {
        toast.error(`Item saved, but a follow-up step failed: ${(err as Error).message}`);
        await onSaved();
        onClose();
        return;
      }
      setServerError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function deactivate() {
    if (!item || deactivating || busy) return;
    const confirmed = await modal.confirm({
      title: 'Deactivate item?',
      message: 'The item will be hidden from POS and the item list. Sales, purchases and repair history are preserved.',
      confirmText: 'Deactivate item',
      cancelText: 'Keep item',
    });
    if (!confirmed) return;
    setDeactivating(true);
    try {
      await api(`/items/${item.item_id}`, { method: 'DELETE' });
      toast.success('Item deactivated');
      await onSaved();
      onClose();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setDeactivating(false);
    }
  }

  async function reactivate() {
    if (!item || reactivating || busy) return;
    const confirmed = await modal.confirm({
      title: 'Reactivate item?',
      message: 'The item will return to the item list and POS. Stock and sales history are unchanged.',
      confirmText: 'Reactivate item',
      cancelText: 'Keep inactive',
    });
    if (!confirmed) return;
    setReactivating(true);
    try {
      await api(`/items/${item.item_id}/reactivate`, { method: 'POST' });
      toast.success('Item reactivated');
      await onSaved();
      onClose();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setReactivating(false);
    }
  }

  async function addVariant() {    if (!item || !variantName.trim() || !variantValue.trim() || variantBusy) return;
    setVariantBusy(true);
    try {
      const created = await api<VariantRow>(`/items/${item.item_id}/variants`, {
        method: 'POST',
        body: JSON.stringify({ name: variantName.trim(), value: variantValue.trim() }),
      });
      setVariants((prev) => prev.concat(created));
      setVariantName('');
      setVariantValue('');
      toast.success('Variant added');
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setVariantBusy(false);
    }
  }

  function openMaster(kind: 'category' | 'type') {
    setMasterModal(kind);
    setMasterError('');
    if (kind === 'category') {
      setNewCategoryName('');
    } else {
      setNewTypeCode('');
      setNewTypeCodeTouched(false);
      setNewTypeAdvancedOpen(false);
      setNewTypeName('');
      setNewTypeSerialized(false);
    }
  }

  function closeMaster() {
    if (masterBusy) return;
    setMasterModal(null);
    setMasterError('');
    setNewCategoryName('');
    setNewTypeCode('');
    setNewTypeCodeTouched(false);
    setNewTypeAdvancedOpen(false);
    setNewTypeName('');
    setNewTypeSerialized(false);
  }

  async function requestCloseMaster() {
    if (masterBusy || masterConfirmRef.current) return;
    const hasInput = masterModal === 'category'
      ? newCategoryName.trim() !== ''
      : newTypeName.trim() !== '' || newTypeCode.trim() !== '';
    if (hasInput) {
      masterConfirmRef.current = true;
      try {
        const discard = await modal.confirm({
          title: 'Discard this entry?',
          message: 'The new category/type text will be lost.',
          confirmText: 'Discard',
          cancelText: 'Keep editing',
        });
        if (!discard) return;
      } finally {
        masterConfirmRef.current = false;
      }
    }
    closeMaster();
  }

  async function createCategoryInline() {
    const name = newCategoryName.trim();
    if (!name) { setMasterError('Category name is required.'); return; }
    if (masterBusy) return;
    setMasterBusy(true);
    setMasterError('');
    try {
      const created = await api<{ id: string; name: string }>('/items/categories', {
        method: 'POST',
        body: JSON.stringify({ name }),
      });
      await onRefreshMasters();
      patch('category_id', created.id);
      setNewCategoryName('');
      setMasterModal(null);
      toast.success('Category added');
    } catch (err) {
      setMasterError((err as Error).message);
    } finally {
      setMasterBusy(false);
    }
  }

  async function createTypeInline() {
    const name = newTypeName.trim();
    const typedCode = newTypeCode.trim().replace(/\s+/g, '_');
    const code = (typedCode || typeCodeFromName(name)).slice(0, 50);
    if (!name) { setMasterError('Item type name is required.'); return; }
    if (!code) { setMasterError('Enter an item type code or a name that can generate one.'); return; }
    if (masterBusy) return;
    setMasterBusy(true);
    setMasterError('');
    try {
      const created = await api<{ id: string }>('/items/item-types', {
        method: 'POST',
        body: JSON.stringify({ code, name, is_serialized: newTypeSerialized }),
      });
      await onRefreshMasters();
      patch('item_type_id', created.id);
      setNewTypeCode('');
      setNewTypeCodeTouched(false);
      setNewTypeAdvancedOpen(false);
      setNewTypeName('');
      setNewTypeSerialized(false);
      setMasterModal(null);
      toast.success('Item type added');
    } catch (err) {
      setMasterError((err as Error).message);
    } finally {
      setMasterBusy(false);
    }
  }

  return (
    <>
    <div className="modal-overlay" onClick={(event) => { if (event.target === event.currentTarget) void requestClose(); }}>
      <div className="modal-card item-modal" role="dialog" aria-modal="true" aria-labelledby="item-modal-title" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h3 id="item-modal-title">
            {readOnly ? `Item: ${item?.description ?? ''}` : item ? `Edit Item: ${item.description}` : '+ Add New Item'}
          </h3>
          <button type="button" className="modal-close" onClick={() => void requestClose()} aria-label="Close" disabled={busy}>×</button>
        </div>

        <div className="modal-body item-modal-body">
          {serverError && !serverDuplicateError && (
            <div className="modal-error-banner" role="alert">
              <div className="modal-error-banner-title"><span>⚠</span> Could not save item</div>
              <div>{serverError}</div>
              <button type="button" className="ghost item-error-retry" onClick={() => void save()} disabled={busy}>
                Retry save
              </button>
            </div>
          )}

          <div className="item-form-grid">
            <div className="item-form-col">
              <div className="item-field">
                <label htmlFor="item-name">Item name * {form.description.trim() && !errors.description && <span className="field-ok">✓</span>}</label>
                <input
                  id="item-name"
                  ref={nameRef}
                  value={form.description}
                  onChange={(event) => {
                    const value = event.target.value;
                    patch('description', value);
                    if (serverError) setServerError('');
                    if (nameCheck.exists || nameCheck.checking) {
                      nameCheckSeq.current += 1;
                      setNameCheck({ value: value.trim(), exists: false, checking: false });
                    }
                  }}
                  onBlur={() => { markTouched('description'); void checkName(form.description); }}
                  maxLength={255}
                  disabled={readOnly}
                  placeholder="e.g. iPhone 13 128GB — Midnight"
                  className={showError('description') || duplicateNameError ? 'input-error' : ''}
                  aria-invalid={showError('description') || !!duplicateNameError || undefined}
                  aria-describedby={showError('description') || duplicateNameError ? 'item-name-error' : undefined}
                />
                <small className="item-counter">{form.description.length}/255</small>
                {showError('description') && <span className="item-field-error" id="item-name-error">{errors.description}</span>}
                {!showError('description') && duplicateNameError && <span className="item-field-error" id="item-name-error">{duplicateNameError}</span>}
              </div>

              <div className="item-form-row">
                <div className="item-field">
                  <div className="item-label-row">
                    <label htmlFor="item-category">Category *</label>
                    {!readOnly && <button type="button" className="ghost" onClick={() => openMaster('category')}>+ New</button>}
                  </div>
                  <select
                    id="item-category"
                    value={form.category_id}
                    onChange={(event) => patch('category_id', event.target.value)}
                    onBlur={() => markTouched('category_id')}
                    disabled={readOnly}
                    className={showError('category_id') ? 'input-error' : ''}
                    aria-invalid={showError('category_id') || undefined}
                    aria-describedby={showError('category_id') ? 'item-category-error' : undefined}
                  >
                    <option value="">Select category</option>
                    {categoryOptions.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                  </select>
                  {showError('category_id') && <span className="item-field-error" id="item-category-error">{errors.category_id}</span>}
                </div>

                <div className="item-field">
                  <div className="item-label-row">
                    <label htmlFor="item-type">Item type *</label>
                    {!readOnly && <button type="button" className="ghost" onClick={() => openMaster('type')}>+ New</button>}
                  </div>
                  <select
                    id="item-type"
                    value={form.item_type_id}
                    onChange={(event) => patch('item_type_id', event.target.value)}
                    onBlur={() => markTouched('item_type_id')}
                    disabled={readOnly}
                    className={showError('item_type_id') ? 'input-error' : ''}
                    aria-invalid={showError('item_type_id') || undefined}
                    aria-describedby={showError('item_type_id') ? 'item-type-error' : undefined}
                  >
                    <option value="">Select type</option>
                    {itemTypeOptions.map((type) => <option key={type.id} value={type.id}>{type.name}{type.is_serialized ? ' · IMEI' : ''}</option>)}
                  </select>
                  {showError('item_type_id') && <span className="item-field-error" id="item-type-error">{errors.item_type_id}</span>}
                </div>
              </div>

              <div className="item-form-row">
                <div className="item-field">
                  <label htmlFor="item-price">Sale price (Rs.) *</label>
                  <div className={`item-input-prefix${showError('master_sale_price') ? ' input-error' : ''}`}>
                    <span>Rs.</span>
                    <input
                      id="item-price"
                      {...moneyInputProps(form.master_sale_price, (value) => patch('master_sale_price', value))}
                      onBlur={() => markTouched('master_sale_price')}
                      disabled={readOnly}
                      placeholder="0.00"
                      aria-invalid={showError('master_sale_price') || undefined}
                      aria-describedby={showError('master_sale_price') ? 'item-price-error' : undefined}
                    />
                  </div>
                  {showError('master_sale_price') && <span className="item-field-error" id="item-price-error">{errors.master_sale_price}</span>}
                </div>

                <div className="item-field">
                  <label htmlFor="item-barcode">Barcode {item ? '(add another)' : ''}</label>
                  <div className="item-barcode-row">
                    <input
                      id="item-barcode"
                      ref={barcodeRef}
                      value={form.barcode}
                      onChange={(event) => patch('barcode', event.target.value)}
                      onBlur={() => markTouched('barcode')}
                      maxLength={100}
                      disabled={readOnly}
                      placeholder="Scan or type barcode"
                      className={showError('barcode') ? 'input-error' : ''}
                      aria-invalid={showError('barcode') || undefined}
                      aria-describedby={showError('barcode') ? 'item-barcode-error' : undefined}
                    />
                    <button
                      type="button"
                      className="ghost item-scan-btn"
                      onClick={() => barcodeRef.current?.focus()}
                      disabled={readOnly}
                      title="USB barcode scanners type into this field. Dedicated scanner support arrives in Chunk 23."
                    >
                      Scan
                    </button>
                  </div>
                  {showError('barcode') && <span className="item-field-error" id="item-barcode-error">{errors.barcode}</span>}
                  {item && item.barcodes.length > 0 && (
                    <small className="item-hint">On file: {item.barcodes.join(', ')}</small>
                  )}
                </div>
              </div>

              <div className="item-form-row">
                <div className="item-field">
                  <label htmlFor="item-low-stock">Low stock alert (units)</label>
                  <input
                    id="item-low-stock"
                    type="text"
                    inputMode="numeric"
                    value={form.low_stock_threshold}
                    onChange={(event) => { if (/^\d*$/.test(event.target.value)) patch('low_stock_threshold', event.target.value); }}
                    onBlur={() => markTouched('low_stock_threshold')}
                    maxLength={7}
                    disabled={readOnly}
                    placeholder="5"
                    className={showError('low_stock_threshold') ? 'input-error' : ''}
                    aria-invalid={showError('low_stock_threshold') || undefined}
                    aria-describedby={showError('low_stock_threshold') ? 'item-low-stock-error' : 'item-low-stock-hint'}
                  />
                  {showError('low_stock_threshold')
                    ? <span className="item-field-error" id="item-low-stock-error">{errors.low_stock_threshold}</span>
                    : <small className="item-hint" id="item-low-stock-hint">Stock at or below this number shows a low-stock warning in the grid. Use 0 to disable.</small>}
                </div>
              </div>

              <div className="item-form-row">
                <div className="item-field">
                  <label htmlFor="item-brand">Brand</label>
                  <input
                    id="item-brand"
                    value={form.brand}
                    onChange={(event) => patch('brand', event.target.value)}
                    maxLength={100}
                    disabled={readOnly}
                    placeholder="e.g. Apple"
                  />
                </div>
                <div className="item-field">
                  <label htmlFor="item-model">Model</label>
                  <input
                    id="item-model"
                    value={form.model}
                    onChange={(event) => patch('model', event.target.value)}
                    maxLength={100}
                    disabled={readOnly}
                    placeholder="e.g. iPhone 13"
                  />
                </div>
              </div>

              <div className="item-field">
                <label htmlFor="item-notes">Compatible models / notes</label>
                <textarea
                  id="item-notes"
                  value={form.compatible_models}
                  onChange={(event) => patch('compatible_models', event.target.value)}
                  maxLength={1000}
                  rows={2}
                  disabled={readOnly}
                  placeholder="Other models this part fits, or a short note"
                />
                <small className="item-counter">{form.compatible_models.length}/1000</small>
              </div>

              <div className="item-field">
                <label>Warranty default</label>
                <div className="item-warranty-row">
                  <select
                    value={form.warranty_type}
                    onChange={(event) => patch('warranty_type', event.target.value)}
                    disabled={readOnly}
                    aria-label="Warranty type"
                  >
                    <option value="NONE">None</option>
                    <option value="DAYS">Days</option>
                    <option value="MONTHS">Months</option>
                    <option value="CHECKING ONLY">Checking only</option>
                    <option value="CUSTOM">Custom</option>
                  </select>
                  {(form.warranty_type === 'DAYS' || form.warranty_type === 'MONTHS') && (
                    <input
                      type="text"
                      inputMode="numeric"
                      value={form.duration_value}
                      onChange={(event) => { if (/^\d*$/.test(event.target.value)) patch('duration_value', event.target.value); }}
                      placeholder="Duration"
                      aria-label="Warranty duration"
                      disabled={readOnly}
                    />
                  )}
                  {form.warranty_type === 'CUSTOM' && (
                    <input
                      value={form.custom_rule}
                      onChange={(event) => patch('custom_rule', event.target.value)}
                      placeholder="Custom warranty rule"
                      aria-label="Custom warranty rule"
                      disabled={readOnly}
                    />
                  )}
                </div>
                {showError('warranty') && <span className="item-field-error" id="item-warranty-error">{errors.warranty}</span>}
              </div>
            </div>

            <aside className="item-form-col item-preview-col">
              <div className="item-preview-card">
                <div className="item-preview-media" style={{ '--tile-h': String(tileHue(form.category_id)) } as CSSProperties}>
                  <span aria-hidden="true">{initialOf(form.description) }</span>
                </div>
                <b>{form.description.trim() || 'New item'}</b>
                <span className="item-preview-meta">{categoryName} · {itemTypeName}</span>
                <span className="item-preview-price">{priceValue && Number.isFinite(priceNumber) ? `Rs. ${money(priceNumber)}` : 'No price yet'}</span>
                <span className="item-preview-code">{item ? item.item_code : 'Item code is generated on save'}</span>
              </div>

              <div className="item-variants-box">
                <div className="item-variants-head">
                  <b>Variants</b>
                  {variantsLoading && <span className="muted">Loading…</span>}
                </div>
                <p className="item-hint">Colour, storage or other options. Variants are labels only — price and stock stay on the item.</p>
                {variants.length > 0 ? (
                  <div className="item-variant-list">
                    {variants.map((variant) => (
                      <span key={variant.variant_id} className="item-variant-chip">{variant.name}: {variant.value}</span>
                    ))}
                  </div>
                ) : (
                  <p className="muted item-variant-empty">{item ? 'No variants yet.' : 'Save the item first, then reopen it to add variants.'}</p>
                )}
                {item && !readOnly && (
                  <div className="item-variant-form">
                    <input value={variantName} onChange={(event) => setVariantName(event.target.value)} maxLength={120} placeholder="Name (e.g. Colour)" aria-label="Variant name" />
                    <input value={variantValue} onChange={(event) => setVariantValue(event.target.value)} maxLength={120} placeholder="Value (e.g. Black)" aria-label="Variant value" />
                    <button type="button" className="ghost" onClick={() => void addVariant()} disabled={variantBusy || !variantName.trim() || !variantValue.trim()}>
                      {variantBusy ? 'Adding…' : 'Add'}
                    </button>
                  </div>
                )}
              </div>

              <div className="item-media-note">
                <b>Photos</b>
                <span>Item images arrive in a later update. Cards use a category colour tile for now.</span>
              </div>
            </aside>
          </div>
        </div>

        <div className="modal-actions">
          {item && !readOnly && item.is_active && (
            <button type="button" className="danger-button" onClick={() => void deactivate()} disabled={busy || deactivating}>
              {deactivating ? 'Deactivating…' : 'Deactivate item'}
            </button>
          )}
          {item && !readOnly && !item.is_active && (
            <button type="button" className="primary inv-card-reactivate" onClick={() => void reactivate()} disabled={busy || reactivating}>
              {reactivating ? 'Reactivating…' : 'Reactivate item'}
            </button>
          )}
          <button type="button" className="btn-secondary" onClick={() => void requestClose()} disabled={busy}>
            {readOnly ? 'Close' : 'Cancel'}
          </button>
          {!readOnly && (
            <button type="button" className="primary" onClick={() => void save()} disabled={!canSave}>
              {busy ? <><span className="spinner" aria-hidden="true" /> Saving…</> : item ? 'Save Item' : 'Create Item'}
            </button>
          )}
        </div>
      </div>
    </div>

    {masterModal && (
      <div
        className="modal-overlay"
        style={{ zIndex: 10050 }}
        onMouseDown={(event) => { masterBackdropDownRef.current = event.target === event.currentTarget; }}
        onClick={(event) => {
          if (masterBackdropDownRef.current && event.target === event.currentTarget) void requestCloseMaster();
          masterBackdropDownRef.current = false;
        }}
      >
        <div
          className="modal-card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="item-master-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <h3 id="item-master-title">{masterModal === 'category' ? 'New category' : 'New item type'}</h3>
            <button type="button" className="modal-close" onClick={() => void requestCloseMaster()} aria-label="Close" disabled={masterBusy}>×</button>
          </div>
          <div className="modal-body">
            {masterError && (
              <div className="modal-error-banner" role="alert">
                <div className="modal-error-banner-title"><span>⚠</span> Could not save</div>
                <div>{masterError}</div>
              </div>
            )}

            {masterModal === 'category' ? (
              <label className="wide-field">Category name *
                <input
                  value={newCategoryName}
                  onChange={(event) => { setNewCategoryName(event.target.value); if (masterError) setMasterError(''); }}
                  maxLength={120}
                  placeholder="e.g. Phone Accessories"
                  aria-label="New category name"
                  autoFocus
                />
              </label>
            ) : (
              <>
                <label className="wide-field">Item type name *
                  <input
                    value={newTypeName}
                    onChange={(event) => {
                      const value = event.target.value;
                      setNewTypeName(value);
                      if (!newTypeCodeTouched) setNewTypeCode(typeCodeFromName(value));
                      if (masterError) setMasterError('');
                    }}
                    maxLength={120}
                    placeholder="e.g. Mobile Phone"
                    aria-label="New item type name"
                    autoFocus
                  />
                </label>
                <div className="item-label-row" style={{ marginTop: 'var(--space-2)' }}>
                  <button
                    type="button"
                    className="ghost category-manager-advanced-toggle"
                    aria-expanded={newTypeAdvancedOpen}
                    onClick={() => setNewTypeAdvancedOpen((value) => !value)}
                  >{newTypeAdvancedOpen ? 'Hide code' : 'Advanced: edit code'}</button>
                </div>
                {newTypeAdvancedOpen && (
                  <label className="wide-field">Code (auto from name)
                    <input
                      value={newTypeCode}
                      onChange={(event) => { setNewTypeCode(event.target.value); setNewTypeCodeTouched(true); }}
                      maxLength={50}
                      placeholder="Auto-generated from name"
                      aria-label="New item type code"
                    />
                  </label>
                )}
                <label className="check">
                  <input type="checkbox" checked={newTypeSerialized} onChange={(event) => setNewTypeSerialized(event.target.checked)} />
                  Serialized / IMEI (one unique serial per unit)
                </label>
                <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>The code is generated from the name. Open Advanced only when you need a specific code.</p>
              </>
            )}

            <div className="modal-actions">
              <button type="button" className="ghost" onClick={() => void requestCloseMaster()} disabled={masterBusy}>Cancel</button>
              <button
                type="button"
                className="primary"
                disabled={masterBusy || (masterModal === 'category' ? !newCategoryName.trim() : !newTypeName.trim())}
                onClick={() => void (masterModal === 'category' ? createCategoryInline() : createTypeInline())}
              >
                {masterBusy ? <><span className="spinner" aria-hidden="true" /> Saving…</> : 'Save'}
              </button>
            </div>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
