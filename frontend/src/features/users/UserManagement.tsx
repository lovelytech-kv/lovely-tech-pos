import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { UserCreateModal } from './UserCreateModal';
import { UserEditModal } from './UserEditModal';
import { UserResetPasswordModal } from './UserResetPasswordModal';

type Props = {
  isAdmin: boolean;
  onError: (msg: string) => void;
};

export type UserRow = {
  user_id: string;
  username: string;
  display_name: string;
  role: string;
  role_id: string;
  branch_id: string;
  is_active: boolean;
  must_change_password: boolean;
  discount_limit_percent: string | number;
  version: number;
  created_at: string | null;
  last_login_at: string | null;
  failed_login_count: number;
  locked_until: string | null;
};

const LIMIT = 50;

function formatRelative(iso: string | null): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days} d ago`;
  return new Date(iso).toLocaleDateString();
}

function statusLabel(u: UserRow): { label: string; cls: string } {
  if (!u.is_active) return { label: 'Inactive', cls: 'sh-status-void' };
  if (u.locked_until && new Date(u.locked_until) > new Date()) return { label: 'Locked', cls: 'sh-status-void' };
  return { label: 'Active', cls: 'sh-status-ok' };
}

export function UserManagement({ isAdmin, onError }: Props) {
  const [q, setQ] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [items, setItems] = useState<UserRow[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [editUser, setEditUser] = useState<UserRow | null>(null);
  const [resetUser, setResetUser] = useState<UserRow | null>(null);
  const debounceRef = useRef<number | null>(null);

  const load = useCallback(async (newOffset = 0) => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (q.trim()) params.set('q', q.trim());
      if (roleFilter) params.set('role', roleFilter);
      if (statusFilter) params.set('is_active', statusFilter === 'active' ? 'true' : 'false');
      params.set('limit', String(LIMIT));
      params.set('offset', String(newOffset));
      const result = await api<{ items: UserRow[]; total: number }>(`/admin/users/managed?${params.toString()}`);
      setItems(result.items);
      setTotal(result.total);
      setOffset(newOffset);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [q, roleFilter, statusFilter, onError]);

  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => { void load(0); }, q !== '' ? 300 : 0);
    return () => { if (debounceRef.current) window.clearTimeout(debounceRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, roleFilter, statusFilter]);

  if (!isAdmin) return null;

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = offset + items.length;

  return (
    <section className="glass panel">
      <div className="section-head">
        <div>
          <span className="eyebrow">ADMIN</span>
          <h2>Users</h2>
          <p className="muted">Create and manage cashier and admin accounts.</p>
        </div>
        <button className="primary" onClick={() => setShowCreate(true)}>+ Create User</button>
      </div>

      <div className="form-grid compact" style={{ marginBottom: '0.75rem' }}>
        <label>Search
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Username or display name" />
        </label>
        <label>Role
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="">All roles</option>
            <option value="ADMIN">Admin</option>
            <option value="CASHIER">Cashier</option>
          </select>
        </label>
        <label>Status
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </label>
      </div>

      {loading && items.length === 0 ? (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <span className="spinner spinner-lg" />
          <p className="muted" style={{ marginTop: '0.5rem' }}>Loading users…</p>
        </div>
      ) : items.length === 0 ? (
        <div className="empty-state" style={{ padding: '2rem', textAlign: 'center' }}>
          <b>No users found</b>
          <span className="muted">Try adjusting the filters or click Create User.</span>
        </div>
      ) : (
        <>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Display Name</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last Login</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((u) => {
                  const st = statusLabel(u);
                  return (
                    <tr key={u.user_id}>
                      <td><b>{u.username}</b></td>
                      <td>{u.display_name}</td>
                      <td>
                        <span className="sh-status" style={{ background: 'var(--surface-2)', color: 'var(--text)' }}>
                          {u.role}
                        </span>
                      </td>
                      <td><span className={`sh-status ${st.cls}`}>{st.label}</span></td>
                      <td>{formatRelative(u.last_login_at)}</td>
                      <td>
                        <div className="button-row">
                          <button onClick={() => setEditUser(u)}>Edit</button>
                          <button onClick={() => setResetUser(u)}>Reset Pwd</button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0.75rem', borderTop: '1px solid var(--line)' }}>
            <span className="muted" style={{ fontSize: '0.75rem' }}>
              Showing {pageStart}-{pageEnd} of {total}
            </span>
            <div className="button-row">
              <button className="ghost" disabled={offset === 0 || loading} onClick={() => void load(Math.max(0, offset - LIMIT))}>← Prev</button>
              <button className="ghost" disabled={offset + LIMIT >= total || loading} onClick={() => void load(offset + LIMIT)}>Next →</button>
            </div>
          </div>
        </>
      )}

      {showCreate && (
        <UserCreateModal
          onClose={() => setShowCreate(false)}
          onSuccess={() => { setShowCreate(false); void load(0); }}
        />
      )}
      {editUser && (
        <UserEditModal
          user={editUser}
          onClose={() => setEditUser(null)}
          onSuccess={() => { setEditUser(null); void load(offset); }}
        />
      )}
      {resetUser && (
        <UserResetPasswordModal
          user={resetUser}
          onClose={() => setResetUser(null)}
          onSuccess={() => { setResetUser(null); void load(offset); }}
        />
      )}
    </section>
  );
}