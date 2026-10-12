import { useState } from 'react';
import { AdminManualServerPanel } from '../components/AdminManualServerPanel';
import { ServerBootstrapForm } from '../components/ServerBootstrapForm';
import { ServerExistingShopForm, ServerExistingShopWaiting } from '../components/ServerExistingShopForm';
import type { SetupState } from '../services/machine-config';
import type { BootstrapShopResponse } from '../api/client';

type Props = {
  state: SetupState;
  isAdmin: boolean;
  machineRole: 'SERVER' | 'CLIENT';
  onRetryDiscovery: () => Promise<void>;
  onConfigureManual: () => void;
  onBackToDiscovery: () => void;
  onBootstrapSuccess?: (result: BootstrapShopResponse) => void;
};

const stateMessages: Record<SetupState, { title: string; description: string; showRetry: boolean; showManual: boolean; adminOnly: boolean }> = {
  UNINITIALIZED: {
    title: 'Welcome to Lovely Tech POS',
    description: 'This machine has not been set up yet. Starting automatic server discovery…',
    showRetry: false,
    showManual: false,
    adminOnly: false,
  },
  DISCOVERING: {
    title: 'Discovering POS server',
    description: 'Looking for the Lovely Tech POS server on the LAN…',
    showRetry: false,
    showManual: false,
    adminOnly: false,
  },
  SERVER_DETECTED: {
    title: 'Server found',
    description: 'A Lovely Tech POS server was detected. Verifying identity…',
    showRetry: false,
    showManual: false,
    adminOnly: false,
  },
  CLIENT_SETUP_REQUIRED: {
    title: 'Setup required',
    description: 'This client machine needs to be connected to a POS server. No server was found automatically.',
    showRetry: true,
    showManual: true,
    adminOnly: true,
  },
  NEW_SHOP_REQUIRED: {
    title: 'New shop setup required',
    description: 'The POS server has no shop configured yet. An Admin must provision a new shop on the server before this machine can continue.',
    showRetry: false,
    showManual: false,
    adminOnly: true,
  },
  EXISTING_SHOP_REQUIRED: {
    title: 'Existing shop setup required',
    description: 'The POS server must be linked to an existing shop. An Admin must select the shop on the server before this machine can continue.',
    showRetry: false,
    showManual: false,
    adminOnly: true,
  },
  IDENTITY_ENROLLMENT_REQUIRED: {
    title: 'Shop identity enrollment required',
    description: 'This database contains existing shop data without canonical shop identity metadata. Do not bootstrap or rebind this server. Keep writes blocked and contact the authorized administrator for an approved enrollment procedure.',
    showRetry: false,
    showManual: false,
    adminOnly: true,
  },
  RESTORE_REQUIRED: {
    title: 'Restore required',
    description: 'This server machine needs to be restored from a verified backup. An Admin must select the backup.',
    showRetry: false,
    showManual: false,
    adminOnly: true,
  },
  READY: {
    title: 'Ready',
    description: 'Machine is configured and ready.',
    showRetry: false,
    showManual: false,
    adminOnly: false,
  },
  SETUP_ERROR: {
    title: 'Setup error',
    description: 'An error occurred during setup. Please retry discovery or contact support.',
    showRetry: true,
    showManual: true,
    adminOnly: true,
  },
};

export function SetupRequired({
  state,
  isAdmin,
  machineRole,
  onRetryDiscovery,
  onConfigureManual,
  onBackToDiscovery,
  onBootstrapSuccess,
}: Props) {
  const [showManualConfig, setShowManualConfig] = useState(false);
  const [showServerBootstrap, setShowServerBootstrap] = useState(false);
  const [showServerExistingShop, setShowServerExistingShop] = useState(false);
  const info = stateMessages[state];

  if (state === 'READY') return null;

  // Non-admin users see waiting message for admin-only states
  if (info.adminOnly && !isAdmin) {
    return (
      <div className="discovery-overlay">
        <div className="discovery-card glass-card">
          <div className="discovery-spinner" aria-hidden="true" />
          <h2>Setup in progress</h2>
          <p className="muted">
            This machine requires Admin setup. Please wait for an Administrator to complete the configuration.
          </p>
        </div>
      </div>
    );
  }

  // Transient discovery states
  if (state === 'DISCOVERING' || state === 'UNINITIALIZED' || state === 'SERVER_DETECTED') {
    return (
      <div className="discovery-overlay">
        <div className="discovery-card glass-card">
          {state === 'DISCOVERING' || state === 'UNINITIALIZED' ? (
            <div className="discovery-spinner" aria-hidden="true" />
          ) : (
            <div className="status-good" style={{ fontSize: '28px' }}>●</div>
          )}
          <h2>{info.title}</h2>
          <p className="muted">{info.description}</p>
        </div>
      </div>
    );
  }

  // SERVER-specific setup flows
  if (machineRole === 'SERVER') {
    if (state === 'IDENTITY_ENROLLMENT_REQUIRED') {
      return (
        <div className="discovery-overlay">
          <div className="discovery-card glass-card">
            <div className="discovery-error-icon" aria-hidden="true">!</div>
            <h2>{info.title}</h2>
            <p className="muted">{info.description}</p>
          </div>
        </div>
      );
    }

    // NEW_SHOP_REQUIRED: Show bootstrap form
    if (state === 'NEW_SHOP_REQUIRED') {
      if (showServerBootstrap) {
        return <ServerBootstrapForm onSuccess={onBootstrapSuccess} />;
      }
      return (
        <div className="discovery-overlay">
          <div className="discovery-card glass-card admin-manual-panel">
            <div className="discovery-panel-head">
              <div>
                <span className="eyebrow">ADMIN · SERVER SETUP</span>
                <h2>{info.title}</h2>
                <p className="muted">{info.description}</p>
              </div>
            </div>
            <div className="manual-actions">
              <button className="primary" onClick={() => setShowServerBootstrap(true)}>
                Provision new shop
              </button>
            </div>
          </div>
        </div>
      );
    }

    // EXISTING_SHOP_REQUIRED: Show existing shop provisioning form
    if (state === 'EXISTING_SHOP_REQUIRED') {
      if (showServerExistingShop) {
        return <ServerExistingShopForm />;
      }
      return (
        <div className="discovery-overlay">
          <div className="discovery-card glass-card admin-manual-panel">
            <div className="discovery-panel-head">
              <div>
                <span className="eyebrow">ADMIN · SERVER SETUP</span>
                <h2>{info.title}</h2>
                <p className="muted">{info.description}</p>
              </div>
            </div>
            <div className="manual-actions">
              <button className="primary" onClick={() => setShowServerExistingShop(true)}>
                Complete existing shop setup
              </button>
            </div>
          </div>
        </div>
      );
    }

    // RESTORE_REQUIRED: Not implemented in this packet - show waiting state
    if (state === 'RESTORE_REQUIRED') {
      return (
        <div className="discovery-overlay">
          <div className="discovery-card glass-card">
            <div className="discovery-error-icon" aria-hidden="true">!</div>
            <h2>{info.title}</h2>
            <p className="muted">{info.description}</p>
            <div className="discovery-actions">
              <button className="primary" onClick={onRetryDiscovery}>
                Retry Discovery
              </button>
            </div>
          </div>
        </div>
      );
    }

    // SETUP_ERROR for SERVER
    if (state === 'SETUP_ERROR') {
      return (
        <div className="discovery-overlay">
          <div className="discovery-card glass-card">
            <div className="discovery-error-icon" aria-hidden="true">!</div>
            <h2>{info.title}</h2>
            <p className="muted">{info.description}</p>
            <div className="discovery-actions">
              {info.showRetry && (
                <button className="primary" onClick={onRetryDiscovery}>
                  Retry Discovery
                </button>
              )}
              {info.showManual && (
                <button className="ghost" onClick={() => setShowManualConfig(true)}>
                  Configure server manually
                </button>
              )}
              <button className="ghost" onClick={onBackToDiscovery}>
                Back to discovery
              </button>
            </div>
          </div>
        </div>
      );
    }
  }

  // CLIENT-specific existing states (existing behavior)
  if (showManualConfig) {
    return (
      <AdminManualServerPanel
        onConfigured={onRetryDiscovery}
        onBack={() => setShowManualConfig(false)}
        onRetry={onRetryDiscovery}
      />
    );
  }

  return (
    <div className="discovery-overlay">
      <div className="discovery-card glass-card">
        <div className="discovery-error-icon" aria-hidden="true">!</div>
        <h2>{info.title}</h2>
        <p className="muted">{info.description}</p>
        <div className="discovery-actions">
          {info.showRetry && (
            <button className="primary" onClick={onRetryDiscovery}>
              Retry Discovery
            </button>
          )}
          {info.showManual && (
            <button className="ghost" onClick={() => setShowManualConfig(true)}>
              Configure server manually
            </button>
          )}
          {state === 'SETUP_ERROR' && (
            <button className="ghost" onClick={onBackToDiscovery}>
              Back to discovery
            </button>
          )}
        </div>
      </div>
    </div>
  );
}