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
  invoice_prefix: string;
};

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

export function ShopProfile({ isAdmin }: { isAdmin: boolean }) {
  const { refetch: refetchPublic } = useShopProfile();
  const [profile, setProfile] = useState<FullProfile | null>(null);
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [invoicePrefix, setInvoicePrefix] = useState('INV');
  const [logoBase64, setLogoBase64] = useState<string | null>(null);
  const [logoMime, setLogoMime] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    try {
      setLoading(true);
      const result = await api<FullProfile>('/branch/profile');
      setProfile(result);
      setName(result.name || '');
      setAddress(result.address || '');
      setPhone(result.phone || '');
      setEmail(result.email || '');
      setInvoicePrefix(result.invoice_prefix || 'INV');
      setLogoBase64(result.logo_base64);
      setLogoMime(result.logo_mime);
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

  function onFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!ALLOWED_MIMES.includes(file.type)) {
      toast.error('Logo must be PNG, JPEG, or SVG');
      if (fileRef.current) fileRef.current.value = '';
      return;
    }
    if (file.size > MAX_LOGO_BYTES) {
      toast.error(`Logo must be under 500KB (this file is ${Math.round(file.size / 1024)}KB)`);
      if (fileRef.current) fileRef.current.value = '';
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const commaIdx = result.indexOf(',');
      if (commaIdx < 0) {
        toast.error('Failed to read image');
        return;
      }
      setLogoBase64(result.slice(commaIdx + 1));
      setLogoMime(file.type);
    };
    reader.onerror = () => toast.error('Failed to read image');
    reader.readAsDataURL(file);
  }

  function removeLogo() {
    setLogoBase64(null);
    setLogoMime(null);
    if (fileRef.current) fileRef.current.value = '';
  }

  async function save() {
    if (!name.trim()) {
      toast.error('Shop name is required');
      return;
    }
    try {
      setBusy(true);
      await api('/branch/profile', {
        method: 'PUT',
        body: JSON.stringify({
          name: name.trim(),
          address: address.trim() || null,
          phone: phone.trim() || null,
          email: email.trim() || null,
          logo_base64: logoBase64,        // null keeps current; '' removes
          logo_mime: logoMime,
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

  const logoDataUrl = logoBase64 && logoMime ? `data:${logoMime};base64,${logoBase64}` : null;

  if (loading) {
    return (
      <div className="glass-panel settings-card" style={{ gridColumn: '1 / -1' }}>
        <div className="settings-card-title">
          <div><h3>Shop Profile</h3><p className="muted">Loading…</p></div>
          <span className="settings-symbol">🏪</span>
        </div>
        <div style={{ textAlign: 'center', padding: '1rem' }}>
          <span className="spinner" />
        </div>
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

      <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '1rem', alignItems: 'start' }}>
        <div>
          <div
            className="shop-logo-preview"
            style={{
              width: 120, height: 120,
              border: '1px solid var(--line)',
              borderRadius: 12,
              background: 'var(--surface-2)',
              display: 'grid',
              placeItems: 'center',
              overflow: 'hidden',
            }}
          >
            {logoDataUrl ? (
              <img src={logoDataUrl} alt="Logo preview" style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
            ) : (
              <span style={{ color: 'var(--muted)', fontSize: '0.75rem', textAlign: 'center', padding: '0.5rem' }}>No logo</span>
            )}
          </div>
          {isAdmin && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.5rem' }}>
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/svg+xml"
                onChange={onFileSelect}
                style={{ display: 'none' }}
              />
              <button type="button" className="btn-secondary" onClick={() => fileRef.current?.click()} style={{ fontSize: '0.75rem', padding: '0.35rem 0.5rem' }}>
                Upload
              </button>
              {logoDataUrl && (
                <button type="button" className="btn-secondary" onClick={removeLogo} style={{ fontSize: '0.75rem', padding: '0.35rem 0.5rem', color: '#dc2626' }}>
                  Remove
                </button>
              )}
              <small className="muted" style={{ fontSize: '0.65rem', textAlign: 'center' }}>PNG/JPEG/SVG · max 500KB</small>
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gap: '0.75rem' }}>
          <label style={labelStyle}>
            Shop Name *
            {isAdmin ? (
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={150}
                placeholder="Lovely Tech"
                style={inputStyle}
              />
            ) : (
              <b style={{ color: 'var(--text)', fontSize: '0.9rem' }}>{profile?.name || '—'}</b>
            )}
          </label>

          <label style={labelStyle}>
            Address
            {isAdmin ? (
              <textarea
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                maxLength={255}
                rows={3}
                placeholder="Shop address"
                style={{ ...inputStyle, resize: 'vertical' }}
              />
            ) : (
              <b style={{ color: 'var(--text)', fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>{profile?.address || '—'}</b>
            )}
          </label>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <label style={labelStyle}>
              Phone
              {isAdmin ? (
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  maxLength={50}
                  placeholder="Phone"
                  style={inputStyle}
                />
              ) : (
                <b style={{ color: 'var(--text)', fontSize: '0.9rem' }}>{profile?.phone || '—'}</b>
              )}
            </label>

            <label style={labelStyle}>
              Email
              {isAdmin ? (
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  maxLength={120}
                  placeholder="Email"
                  style={inputStyle}
                />
              ) : (
                <b style={{ color: 'var(--text)', fontSize: '0.9rem' }}>{profile?.email || '—'}</b>
              )}
            </label>
          </div>

          <label style={labelStyle}>
            Invoice Prefix
            {isAdmin ? (
              <>
                <input
                  value={invoicePrefix}
                  onChange={(e) => setInvoicePrefix(e.target.value)}
                  maxLength={20}
                  placeholder="INV"
                  style={inputStyle}
                />
                <small className="muted" style={{ fontSize: '0.65rem' }}>
                  Reserved for future invoice formatting (currently not applied to invoice numbers)
                </small>
              </>
            ) : (
              <b style={{ color: 'var(--text)', fontSize: '0.9rem' }}>{profile?.invoice_prefix || 'INV'}</b>
            )}
          </label>

          {!isAdmin && (
            <p className="muted" style={{ margin: 0, fontSize: '0.75rem' }}>
              Only admin can edit shop profile.
            </p>
          )}

          {isAdmin && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.25rem' }}>
              <button type="button" className="primary" onClick={() => void save()} disabled={busy}>
                {busy ? 'Saving…' : 'Save Shop Profile'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}