import { useState } from 'react';
import { bootstrapShop, type BootstrapShopResponse } from '../api/client';

type ServerBootstrapFormProps = {
  onSuccess?: (result: BootstrapShopResponse) => void;
};

export function ServerBootstrapForm({ onSuccess }: ServerBootstrapFormProps = {}) {
  const [branchCode, setBranchCode] = useState('');
  const [branchName, setBranchName] = useState('');
  const [adminUsername, setAdminUsername] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [adminDisplayName, setAdminDisplayName] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<BootstrapShopResponse | null>(null);

  function validateForm(): string | null {
    if (!branchCode.trim()) return 'Branch code is required.';
    if (branchCode.length > 30) return 'Branch code must be 30 characters or less.';
    if (!branchName.trim()) return 'Branch name is required.';
    if (branchName.length > 150) return 'Branch name must be 150 characters or less.';
    if (!adminUsername.trim()) return 'Admin username is required.';
    if (adminUsername.length > 80) return 'Admin username must be 80 characters or less.';
    if (!adminPassword) return 'Admin password is required.';
    if (adminPassword.length < 10 || adminPassword.length > 200) return 'Admin password must be 10-200 characters.';
    if (!adminDisplayName.trim()) return 'Admin display name is required.';
    if (adminDisplayName.length > 150) return 'Admin display name must be 150 characters or less.';
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const res = await bootstrapShop({
        branch_code: branchCode.trim(),
        branch_name: branchName.trim(),
        admin_username: adminUsername.trim(),
        admin_display_name: adminDisplayName.trim(),
        admin_password: adminPassword,
      });
      setResult(res);
      onSuccess?.(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bootstrap failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="discovery-overlay">
        <div className="discovery-card glass-card admin-manual-panel">
          <div className="discovery-panel-head">
            <div>
              <span className="eyebrow">ADMIN · SERVER SETUP</span>
              <div className="status-good" style={{ fontSize: '28px' }}>●</div>
              <h2>Shop provisioned</h2>
              <p className="muted">
                The new shop and the initial Admin account have been created on this server.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="discovery-overlay">
      <div className="discovery-card glass-card admin-manual-panel">
        <div className="discovery-panel-head">
          <div>
            <span className="eyebrow">ADMIN · SERVER SETUP</span>
            <h2>New shop bootstrap</h2>
            <p className="muted">
              This server has no shop configured. Provision the first shop and create the initial Admin account.
            </p>
          </div>
        </div>

        <form className="manual-form" onSubmit={handleSubmit}>
          <label>
            Branch code
            <input
              autoFocus
              placeholder="e.g. MAIN"
              value={branchCode}
              onChange={e => setBranchCode(e.target.value)}
              maxLength={30}
              spellCheck={false}
            />
          </label>
          <small className="muted">Unique code for this branch (1-30 chars).</small>

          <label>
            Branch name
            <input
              placeholder="e.g. Main Street Store"
              value={branchName}
              onChange={e => setBranchName(e.target.value)}
              maxLength={150}
              spellCheck={false}
            />
          </label>
          <small className="muted">Display name for this branch (1-150 chars).</small>

          <label>
            Admin username
            <input
              placeholder="e.g. admin"
              value={adminUsername}
              onChange={e => setAdminUsername(e.target.value)}
              maxLength={80}
              spellCheck={false}
              autoComplete="username"
            />
          </label>
          <small className="muted">Username for the initial Admin account (1-80 chars).</small>

          <label>
            Admin password
            <input
              type="password"
              placeholder="Enter password"
              value={adminPassword}
              onChange={e => setAdminPassword(e.target.value)}
              maxLength={200}
              autoComplete="new-password"
            />
          </label>
          <small className="muted">Password for the initial Admin account (10-200 chars).</small>

          <label>
            Admin display name
            <input
              placeholder="e.g. Store Manager"
              value={adminDisplayName}
              onChange={e => setAdminDisplayName(e.target.value)}
              maxLength={150}
              spellCheck={false}
              autoComplete="name"
            />
          </label>
          <small className="muted">Display name for the initial Admin account (1-150 chars).</small>

          {error && <div className="error manual-error" role="alert">{error}</div>}

          <div className="manual-actions">
            <button className="primary" type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Provisioning…' : 'Provision shop and create Admin'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}