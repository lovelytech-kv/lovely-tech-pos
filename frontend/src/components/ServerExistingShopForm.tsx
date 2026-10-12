import { useState } from 'react';

export function ServerExistingShopForm() {
  const [branchCode, setBranchCode] = useState('');
  const [branchName, setBranchName] = useState('');
  const [error, setError] = useState('');

  function validateForm(): string | null {
    if (!branchCode.trim()) return 'Branch code is required.';
    if (branchCode.length > 30) return 'Branch code must be 30 characters or less.';
    if (!branchName.trim()) return 'Branch name is required.';
    if (branchName.length > 150) return 'Branch name must be 150 characters or less.';
    return null;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    // No-op: API call will be implemented in a later packet
    console.log('Existing shop form submitted (no-op):', {
      branch_code: branchCode.trim(),
      branch_name: branchName.trim(),
    });
  }

  return (
    <div className="discovery-overlay">
      <div className="discovery-card glass-card admin-manual-panel">
        <div className="discovery-panel-head">
          <div>
            <span className="eyebrow">ADMIN · SERVER SETUP</span>
            <h2>Existing shop setup required</h2>
            <p className="muted">
              This server has an existing or partial shop setup. An Admin must complete the provisioning.
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
          <small className="muted">Unique code for the existing branch (1-30 chars).</small>

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
          <small className="muted">Display name for the existing branch (1-150 chars).</small>

          {error && <div className="error manual-error" role="alert">{error}</div>}

          <div className="manual-actions">
            <button className="primary" type="submit">
              Complete existing shop setup
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function ServerExistingShopWaiting() {
  return (
    <div className="discovery-overlay">
      <div className="discovery-card glass-card">
        <div className="discovery-spinner" aria-hidden="true" />
        <h2>Setup in progress</h2>
        <p className="muted">
          This machine requires Admin setup. An Administrator must complete the existing shop setup on the server.
        </p>
      </div>
    </div>
  );
}