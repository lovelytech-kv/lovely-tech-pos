import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '../test-utils';
import { waitFor } from '@testing-library/react';
import { SetupRequired } from './SetupRequired';

describe('SetupRequired component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const mockCallbacks = {
    onRetryDiscovery: vi.fn(),
    onConfigureManual: vi.fn(),
    onBackToDiscovery: vi.fn(),
  };

  it('returns null for READY state', () => {
    const { container } = render(
      <SetupRequired state="READY" isAdmin={true} {...mockCallbacks} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('shows loading state for UNINITIALIZED', () => {
    render(<SetupRequired state="UNINITIALIZED" isAdmin={true} {...mockCallbacks} />);
    expect(screen.getByText('Welcome to Lovely Tech POS')).toBeInTheDocument();
    expect(screen.getByText(/This machine has not been set up yet/)).toBeInTheDocument();
    expect(screen.queryByText('Retry Discovery')).not.toBeInTheDocument();
    expect(screen.queryByText('Configure server manually')).not.toBeInTheDocument();
  });

  it('shows loading state for DISCOVERING', () => {
    render(<SetupRequired state="DISCOVERING" isAdmin={true} {...mockCallbacks} />);
    expect(screen.getByText('Discovering POS server')).toBeInTheDocument();
    expect(screen.getByText(/Looking for the Lovely Tech POS server on the LAN/)).toBeInTheDocument();
  });

  it('shows server detected state for SERVER_DETECTED', () => {
    render(<SetupRequired state="SERVER_DETECTED" isAdmin={true} {...mockCallbacks} />);
    expect(screen.getByText('Server found')).toBeInTheDocument();
    expect(screen.getByText(/A Lovely Tech POS server was detected/)).toBeInTheDocument();
  });

  it('shows CLIENT_SETUP_REQUIRED with retry and manual buttons for Admin', () => {
    render(<SetupRequired state="CLIENT_SETUP_REQUIRED" isAdmin={true} {...mockCallbacks} />);
    expect(screen.getByText('Setup required')).toBeInTheDocument();
    expect(screen.getByText(/No server was found automatically/)).toBeInTheDocument();
    expect(screen.getByText('Retry Discovery')).toBeInTheDocument();
    expect(screen.getByText('Configure server manually')).toBeInTheDocument();
  });

  it('shows CLIENT_SETUP_REQUIRED with waiting message for Cashier', () => {
    render(<SetupRequired state="CLIENT_SETUP_REQUIRED" isAdmin={false} {...mockCallbacks} />);
    expect(screen.getByText('Setup in progress')).toBeInTheDocument();
    expect(screen.getByText(/This machine requires Admin setup/)).toBeInTheDocument();
    expect(screen.queryByText('Retry Discovery')).not.toBeInTheDocument();
    expect(screen.queryByText('Configure server manually')).not.toBeInTheDocument();
  });

  it('shows NEW_SHOP_REQUIRED for Admin', () => {
    render(<SetupRequired state="NEW_SHOP_REQUIRED" isAdmin={true} {...mockCallbacks} />);
    expect(screen.getByText('New shop setup required')).toBeInTheDocument();
    expect(screen.getByText(/An Admin must provision a new shop/)).toBeInTheDocument();
  });

  it('shows waiting message for Cashier on NEW_SHOP_REQUIRED', () => {
    render(<SetupRequired state="NEW_SHOP_REQUIRED" isAdmin={false} {...mockCallbacks} />);
    expect(screen.getByText('Setup in progress')).toBeInTheDocument();
    expect(screen.getByText(/This machine requires Admin setup/)).toBeInTheDocument();
  });

  it('shows EXISTING_SHOP_REQUIRED for Admin', () => {
    render(<SetupRequired state="EXISTING_SHOP_REQUIRED" isAdmin={true} {...mockCallbacks} />);
    expect(screen.getByText('Existing shop setup required')).toBeInTheDocument();
    expect(screen.getByText(/An Admin must select the shop/)).toBeInTheDocument();
  });

  it('shows RESTORE_REQUIRED for Admin', () => {
    render(<SetupRequired state="RESTORE_REQUIRED" isAdmin={true} {...mockCallbacks} />);
    expect(screen.getByText('Restore required')).toBeInTheDocument();
    expect(screen.getByText(/An Admin must select the backup/)).toBeInTheDocument();
  });

  it('shows SETUP_ERROR with retry, manual, and back buttons for Admin', () => {
    render(<SetupRequired state="SETUP_ERROR" isAdmin={true} {...mockCallbacks} />);
    expect(screen.getByText('Setup error')).toBeInTheDocument();
    expect(screen.getByText(/An error occurred during setup/)).toBeInTheDocument();
    expect(screen.getByText('Retry Discovery')).toBeInTheDocument();
    expect(screen.getByText('Configure server manually')).toBeInTheDocument();
    expect(screen.getByText('Back to discovery')).toBeInTheDocument();
  });

  it('shows waiting message for Cashier on SETUP_ERROR', () => {
    render(<SetupRequired state="SETUP_ERROR" isAdmin={false} {...mockCallbacks} />);
    expect(screen.getByText('Setup in progress')).toBeInTheDocument();
    expect(screen.getByText(/This machine requires Admin setup/)).toBeInTheDocument();
  });

  it('calls onRetryDiscovery when Retry Discovery is clicked', () => {
    render(<SetupRequired state="CLIENT_SETUP_REQUIRED" isAdmin={true} {...mockCallbacks} />);
    fireEvent.click(screen.getByText('Retry Discovery'));
    expect(mockCallbacks.onRetryDiscovery).toHaveBeenCalled();
  });

  it('shows AdminManualServerPanel after clicking Configure server manually', async () => {
    render(<SetupRequired state="CLIENT_SETUP_REQUIRED" isAdmin={true} {...mockCallbacks} />);
    fireEvent.click(screen.getByText('Configure server manually'));
    await waitFor(() => {
      expect(screen.getByText('Manual server configuration')).toBeInTheDocument();
    });
  });

  it('calls onBackToDiscovery when Back to discovery is clicked on SETUP_ERROR', () => {
    render(<SetupRequired state="SETUP_ERROR" isAdmin={true} {...mockCallbacks} />);
    fireEvent.click(screen.getByText('Back to discovery'));
    expect(mockCallbacks.onBackToDiscovery).toHaveBeenCalled();
  });
});