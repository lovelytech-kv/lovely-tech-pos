import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { toast } from '../../ui/toast';
import { useShopProfile } from './ShopContext';

type FullProfile = {
  branch_id: string;
  code: string;
  name: string;
  address: string | null;
  phone: string | null;
  email: string | null;
  logo_base64: string | null;
  logo_mime: string | null;
  logo_base64_light: string | null;
  logo_mime_light: string | null;
  logo_base64_dark: string | null;
  logo_mime_dark: string | null;
  invoice_prefix: string;
};

type ShopIdentity = {
  shop_uuid: string;
  shop_name: string | null;
  schema_version: number;
  created_at: string;
};

type LogoState = { base64: string; mime: string } | null;

const MAX_LOGO_BYTES = 500 * 1024;
const ALLOWED_MIMES = ['image/png', 'image/jpeg', 'image/svg+xml'];

const inputStyle: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  border: '1px solid var(--line)',
  borderRadius: 8,
  background: 'var(--surface)',
  color: 'var(--text)',
  fontSize: '0.875rem',
};

const labelStyle: React.CSSProperties = {
  display: 'grid',
  gap: '0.25rem',
  fontSize: '0.8rem',
  color: 'var(--muted)',
};

function readFileAsLogo(file: File): Promise<LogoState> {
  return new Promise((resolve, reject) => {
    if (!ALLOWED_MIMES.includes(file.type)) {
      reject(new Error('Logo must be PNG, JPEG, or SVG'));
      return;
    }
    if (file.size > MAX_LOGO_BYTES) {
      reject(new Error(`Logo must be under 500KB (this file is ${Math.round(file.size / 1024)}KB)`));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const idx = result.indexOf(',');
      if (idx < 0) { reject(new Error('Failed to read image')); return; }
      resolve({ base64: result.slice(idx + 1), mime: file.type });
    };
    reader.onerror = () => reject(new Error('Failed to read image'));
    reader.readAsDataURL(file);
  });
}

export function ShopProfile({ isAdmin }: { isAdmin: boolean }) {
  const { refetch: refetchPublic } = useShopProfile();
  const [profile, setProfile] = useState<FullProfile | null>(null);
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [invoicePrefix, setInvoicePrefix] = useState('INV');
  const [logoLight, setLogoLight] = useState<LogoState>(null);
  const [logoDark, setLogoDark] = useState<LogoState>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const fileLightRef = useRef<HTMLInputElement>(null);
  const fileDarkRef = useRef<HTMLInputElement>(null);

  // Shop identity (Chunk 12b)
  const [shopIdentity, setShopIdentity] = useState<ShopIdentity | null>(null);
  const [shopIdError, setShopIdError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState(false);

  async function loadShopIdentity() {
    try {
      setShopIdError(null);
      const id = await api<ShopIdentity>('/shop/identity');
      setShopIdentity(id);
    } catch (e) {
      setShopIdError((e as Error).message || 'Could not load shop ID');
      setShopIdentity(null);
    }
  }

  async function load() {
    try {
      setLoading(true);
      const [result] = await Promise.all([
        api<FullProfile>('/branch/profile'),
        loadShopIdentity(),
      ]);
      setProfile(result);
      setName(result.name || '');
      setAddress(result.address || '');
      setPhone(result.phone || '');
      setEmail(result.email || '');
      setInvoicePrefix(result.invoice_prefix || 'INV');
      const lightB64 = result.logo_base64_light || result.logo_base64;
      const lightMime = result.logo_mime_light || result.logo_mime;
      setLogoLight(lightB64 && lightMime ? { base64: lightB64, mime: lightMime } : null);
      setLogoDark(result.logo_base64_dark && result.logo_mime_dark ? { base64: result.logo_base64_dark, mime: result.logo_mime_dark } : null);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function copyShopId() {
    if (!shopIdentity?.shop_uuid) return;
    try {
      await navigator.clipboard.writeText(shopIdentity.shop_uuid);
      setCopiedId(true);
      window.setTimeout(() => setCopiedId(false), 2000);
    } catch {
      // fallback
      const ta = document.createElement('textarea');
      ta.value = shopIdentity.shop_uuid;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopiedId(true);
      window.setTimeout(() => setCopiedId(false), 2000);
    }
  }

  async function onPickLight(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const parsed = await readFileAsLogo(file);
      setLogoLight(parsed);
    } catch (err) {
      toast.error((err as Error).message);
      if (fileLightRef.current) fileLightRef.current.value = '';
    }
  }

  async function onPickDark(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const parsed = await readFileAsLogo(file);
      setLogoDark(parsed);
    } catch (err) {
      toast.error((err as Error).message);
      if (fileDarkRef.current) fileDarkRef.current.value = '';
    }
  }

  function removeLight() { setLogoLight(null); if (fileLightRef.current) fileLightRef.current.value = ''; }
  function removeDark() { setLogoDark(null); if (fileDarkRef.current) fileDarkRef.current.value = ''; }

  async function save() {
    if (!name.trim()) { toast.error('Shop name is required'); return; }
    try {
      setBusy(true);
      await api('/branch/profile', {
        method: 'PUT',
        body: JSON.stringify({
          name: name.trim(),
          address: address.trim() || null,
          phone: phone.trim() || null,
          email: email.trim() || null,
          logo_base64_light: logoLight ? logoLight.base64 : '',
          logo_mime_light: logoLight ? logoLight.mime : null,
          logo_base64_dark: logoDark ? logoDark.base64 : '',
          logo_mime_dark: logoDark ? logoDark.mime : null,
          invoice_prefix: invoicePrefix.trim() || 'INV',
        }),
      });
      toast.success('Shop profile saved');
      await load();
      await refetchPublic();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function LogoBox({ logo, onPick, onRemove, fileRef, mode }: {
    logo: LogoState;
    onPick: (e: React.ChangeEvent<HTMLInputElement>) => void;
    onRemove: () => void;
    fileRef: React.RefObject<HTMLInputElement | null>;
    mode: 'light' | 'dark';
  }) {
    const src = logo ? `data:${logo.mime};base64,${logo.base64}` : null;
    const bg = mode === 'light' ? '#ffffff' : '#15171b';
    const fg = mode === 'light' ? '#999' : '#666';
    return (
      <div style={{ display: 'grid', gap: '0.35rem' }}>
        <div style={{ width: 120, height: 120, border: '1px solid var(--line)', borderRadius: 12, background: bg, display: 'grid', placeItems: 'center', overflow: 'hidden', padding: src ? 6 : 0 }}>
          {src ? <img src={src} alt={`${mode} logo`} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} /> : <span style={{ color: fg, fontSize: '0.7rem', textAlign: 'center', padding: '0.5rem' }}>No {mode} logo</span>}
        </div>
        {isAdmin && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/svg+xml" onChange={onPick} style={{ display: 'none' }} />
            <button type="button" className="btn-secondary" onClick={() => fileRef.current?.click()} style={{ fontSize: '0.7rem', padding: '0.3rem 0.5rem' }}>Upload</button>
            {src && <button type="button" className="btn-secondary" onClick={onRemove} style={{ fontSize: '0.7rem', padding: '0.3rem 0.5rem', color: '#dc2626' }}>Remove</button>}
          </div>
        )}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
        <div className="settings-card-title">
          <div><h3>Shop Profile</h3><p className="muted">Loading…</p></div>
          <span className="settings-symbol">🏪</span>
        </div>
        <div style={{ textAlign: 'center', padding: '1rem' }}><span className="spinner" /></div>
      </div>
    );
  }

  return (
    <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
      <div className="settings-card-title">
        <div>
          <h3>Shop Profile</h3>
          <p className="muted">Name, contact and branding shown on receipts, login and header. Only admin can edit.</p>
        </div>
        <span className="settings-symbol">🏪</span>
      </div>

      <div style={{ display: 'grid', gap: '1rem' }}>
        {/* Shop ID (Chunk 12b) */}
        <div style={{ padding: '0.75rem', background: 'var(--surface-2)', borderRadius: 10, border: '1px solid var(--line)' }}>
          {shopIdentity ? (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <div>
                <small className="muted" style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.03em' }}>Shop ID</small>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text)', marginTop: '0.15rem' }} title={`Full UUID: ${shopIdentity.shop_uuid}`}>
                  {shopIdentity.shop_uuid.slice(0, 8)}…
                </div>
                <small className="muted" style={{ fontSize: '0.7rem' }}>This unique ID identifies your shop. It survives backups and hardware changes.</small>
              </div>
              <button type="button" className="btn-secondary" onClick={() => void copyShopId()} style={{ fontSize: '0.75rem' }}>
                {copiedId ? '✓ Copied' : 'Copy ID'}
              </button>
            </div>
          ) : shopIdError ? (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <small className="muted" style={{ fontSize: '0.75rem' }}>Shop ID unavailable</small>
              <button type="button" className="btn-secondary" onClick={() => void loadShopIdentity()} style={{ fontSize: '0.7rem' }}>Retry</button>
            </div>
          ) : (
            <small className="muted" style={{ fontSize: '0.75rem' }}>Loading Shop ID…</small>
          )}
        </div>

        <div>
          <div style={{ fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '0.5rem', fontWeight: 600 }}>Logos</div>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'grid', gap: '0.35rem' }}>
              <small className="muted" style={{ fontSize: '0.7rem', textAlign: 'center', fontWeight: 600 }}>☀ Light mode</small>
              <LogoBox logo={logoLight} onPick={onPickLight} onRemove={removeLight} fileRef={fileLightRef} mode="light" />
            </div>
            <div style={{ display: 'grid', gap: '0.35rem' }}>
              <small className="muted" style={{ fontSize: '0.7rem', textAlign: 'center', fontWeight: 600 }}>☾ Dark mode</small>
              <LogoBox logo={logoDark} onPick={onPickDark} onRemove={removeDark} fileRef={fileDarkRef} mode="dark" />
            </div>
            <div style={{ flex: 1, minWidth: 200, fontSize: '0.7rem', color: 'var(--muted)', alignSelf: 'center' }}>
              <p style={{ margin: '0 0 0.35rem' }}>Upload separate logos for light and dark themes. The app automatically shows the matching logo.</p>
              <p style={{ margin: 0 }}>PNG, JPEG or SVG — max 500KB each.</p>
            </div>
          </div>
        </div>

        <label style={labelStyle}>
          Shop Name *
          {isAdmin ? (
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={150} placeholder="Lovely Tech" style={inputStyle} />
          ) : (
            <b style={{ color: 'var(--text)', fontSize: '0.9rem' }}>{profile?.name || '—'}</b>
          )}
          {isAdmin && <small className="muted" style={{ fontSize: '0.7rem' }}>{name.length}/150</small>}
        </label>

        <label style={labelStyle}>
          Address
          {isAdmin ? (
            <textarea value={address} onChange={(e) => setAddress(e.target.value)} maxLength={255} rows={3} placeholder="Shop address" style={{ ...inputStyle, resize: 'vertical' }} />
          ) : (
            <b style={{ color: 'var(--text)', fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>{profile?.address || '—'}</b>
          )}
          {isAdmin && <small className="muted" style={{ fontSize: '0.7rem' }}>{address.length}/255</small>}
        </label>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <label style={labelStyle}>
            Phone
            {isAdmin ? <input value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={50} placeholder="Phone" style={inputStyle} /> : <b style={{ color: 'var(--text)', fontSize: '0.9rem' }}>{profile?.phone || '—'}</b>}
            {isAdmin && <small className="muted" style={{ fontSize: '0.7rem' }}>{phone.length}/50</small>}
          </label>
          <label style={labelStyle}>
            Email
            {isAdmin ? <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={120} placeholder="Email" style={inputStyle} /> : <b style={{ color: 'var(--text)', fontSize: '0.9rem' }}>{profile?.email || '—'}</b>}
            {isAdmin && <small className="muted" style={{ fontSize: '0.7rem' }}>{email.length}/120</small>}
          </label>
        </div>

        <label style={labelStyle}>
          Invoice Prefix
          {isAdmin ? (
            <>
              <input value={invoicePrefix} onChange={(e) => setInvoicePrefix(e.target.value)} maxLength={20} placeholder="INV" style={inputStyle} />
              <small className="muted" style={{ fontSize: '0.65rem' }}>Used as the display prefix for new invoices (e.g. INV-000123 → LT-000123)</small>
            </>
          ) : (
            <b style={{ color: 'var(--text)', fontSize: '0.9rem' }}>{profile?.invoice_prefix || 'INV'}</b>
          )}
        </label>

        {!isAdmin && <p className="muted" style={{ margin: 0, fontSize: '0.75rem' }}>Only admin can edit shop profile.</p>}

        {isAdmin && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.25rem' }}>
            <button type="button" className="primary" onClick={() => void save()} disabled={busy}>
              {busy ? 'Saving…' : 'Save Shop Profile'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}