/** Boot-flow tests for Packet 15-I.3-B.
 *
 * The CLIENT machine state must be driven by the setup_state of a
 * server verified through mDNS + HTTP /discovery/info (or the Admin
 * manual server flow, which uses the same verification). A successful
 * discovery alone must not mark the client READY.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent, cleanup } from './test-utils';

const discoveryMocks = vi.hoisted(() => ({
  resolveApiBase: vi.fn(),
  resolveServer: vi.fn(),
  verifyManualServer: vi.fn(),
}));

vi.mock('./services/discovery', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./services/discovery')>();
  return {
    ...actual,
    isTauriEnvironment: () => true,
    resolveApiBase: discoveryMocks.resolveApiBase,
    resolveServer: discoveryMocks.resolveServer,
    verifyManualServer: discoveryMocks.verifyManualServer,
  };
});

const CONFIG_KEY = 'ltpos_machine_config';

function readConfig() {
  const raw = localStorage.getItem(CONFIG_KEY);
  return raw ? JSON.parse(raw) : null;
}

async function bootApp() {
  const root = document.createElement('div');
  root.id = 'root';
  document.body.appendChild(root);
  await import('./main');
}

function makeIdentity(setup_state: string, instance_id = 'aaaaaaa1-2222-3333-4444-555555555555') {
  return {
    product: 'Lovely Tech POS System',
    protocol_version: '1.0.0',
    api_version: '1',
    app_version: '0.4.0',
    instance_id,
    branch_code: 'SHOP-A',
    setup_state,
  };
}

const verifiedResolution = (setup_state: string, instance_id?: string) => ({
  baseUrl: 'http://192.168.1.100:8000/api/v1',
  identity: makeIdentity(setup_state, instance_id),
});

const discoveryError = (code: string, message: string) =>
  Object.assign(new Error(message), { code });

describe('client boot flow (Packet 15-I.3-B)', () => {
  let originalLocation: Location;

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    localStorage.clear();
    originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      value: { protocol: 'tauri:', hostname: 'localhost' },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    cleanup();
    document.body.innerHTML = '';
    Object.defineProperty(window, 'location', { value: originalLocation, writable: true, configurable: true });
    localStorage.clear();
  });

  it('verified READY server → client READY (normal boot to login)', async () => {
    discoveryMocks.resolveApiBase.mockResolvedValue(verifiedResolution('READY'));
    await bootApp();

    expect(await screen.findByText('Welcome back')).toBeInTheDocument();
    expect(screen.queryByText('Setup in progress')).not.toBeInTheDocument();

    const config = readConfig();
    expect(config.machine_role).toBe('CLIENT');
    expect(config.setup_state).toBe('READY');
    expect(config.server_reference).toBe('aaaaaaa1-2222-3333-4444-555555555555');
    expect(config.client_id).not.toBeNull();
  });

  it('verified NEW_SHOP_REQUIRED server → client waits, no provisioning controls', async () => {
    discoveryMocks.resolveApiBase.mockResolvedValue(
      verifiedResolution('NEW_SHOP_REQUIRED', 'bbbbbbb1-2222-3333-4444-555555555555')
    );
    await bootApp();

    expect(await screen.findByText('Setup in progress')).toBeInTheDocument();
    expect(screen.queryByText('Welcome back')).not.toBeInTheDocument();
    expect(screen.queryByText('Retry Discovery')).not.toBeInTheDocument();
    expect(screen.queryByText('Configure server manually')).not.toBeInTheDocument();
    expect(screen.queryByText('Provision shop')).not.toBeInTheDocument();

    const config = readConfig();
    expect(config.setup_state).toBe('NEW_SHOP_REQUIRED');
    expect(config.server_reference).toBe('bbbbbbb1-2222-3333-4444-555555555555');
  });

  it('verified EXISTING_SHOP_REQUIRED server → client waits, no provisioning controls', async () => {
    discoveryMocks.resolveApiBase.mockResolvedValue(
      verifiedResolution('EXISTING_SHOP_REQUIRED', 'ccccccc1-2222-3333-4444-555555555555')
    );
    await bootApp();

    expect(await screen.findByText('Setup in progress')).toBeInTheDocument();
    expect(screen.queryByText('Welcome back')).not.toBeInTheDocument();
    expect(screen.queryByText('Retry Discovery')).not.toBeInTheDocument();
    expect(screen.queryByText('Configure server manually')).not.toBeInTheDocument();

    const config = readConfig();
    expect(config.setup_state).toBe('EXISTING_SHOP_REQUIRED');
    expect(config.server_reference).toBe('ccccccc1-2222-3333-4444-555555555555');
  });

  it('failed discovery (no servers) does not become READY', async () => {
    discoveryMocks.resolveApiBase.mockRejectedValue(
      discoveryError('NO_SERVERS', 'No Lovely Tech POS servers found on the LAN')
    );
    await bootApp();

    expect(await screen.findByText('Manual server configuration')).toBeInTheDocument();
    expect(screen.queryByText('Welcome back')).not.toBeInTheDocument();

    const config = readConfig();
    expect(config.setup_state).toBe('CLIENT_SETUP_REQUIRED');
    expect(config.setup_state).not.toBe('READY');
  });

  it('unreachable server does not become READY', async () => {
    discoveryMocks.resolveApiBase.mockRejectedValue(
      discoveryError('ALL_UNREACHABLE', 'None of 1 discovered server(s) could be verified')
    );
    await bootApp();

    expect(await screen.findByText('Manual server configuration')).toBeInTheDocument();

    const config = readConfig();
    expect(config.setup_state).toBe('CLIENT_SETUP_REQUIRED');
    expect(config.setup_state).not.toBe('READY');
  });

  it('identity mismatch during discovery does not become READY', async () => {
    discoveryMocks.resolveApiBase.mockRejectedValue(
      discoveryError('IDENTITY_MISMATCH', 'Identity mismatch: advertised TXT does not match /discovery/info')
    );
    await bootApp();

    expect(await screen.findByText('Manual server configuration')).toBeInTheDocument();

    const config = readConfig();
    expect(config.setup_state).toBe('SETUP_ERROR');
    expect(config.setup_state).not.toBe('READY');
  });

  it('manual server verification drives the client state from setup_state (waits)', async () => {
    discoveryMocks.resolveApiBase.mockRejectedValue(
      discoveryError('NO_SERVERS', 'No Lovely Tech POS servers found on the LAN')
    );
    discoveryMocks.verifyManualServer.mockResolvedValue({
      baseUrl: 'http://192.168.1.50:8000/api/v1',
      identity: makeIdentity('EXISTING_SHOP_REQUIRED', 'ddddddd1-2222-3333-4444-555555555555'),
    });
    await bootApp();

    expect(await screen.findByText('Manual server configuration')).toBeInTheDocument();
    const input = screen.getByPlaceholderText(/http:\/\/192.168.1.50:8000/);
    fireEvent.change(input, { target: { value: 'http://192.168.1.50:8000' } });
    fireEvent.click(screen.getByText('Connect to server'));

    expect(await screen.findByText('Setup in progress')).toBeInTheDocument();
    expect(screen.queryByText('Welcome back')).not.toBeInTheDocument();

    const config = readConfig();
    expect(config.setup_state).toBe('EXISTING_SHOP_REQUIRED');
    expect(config.server_reference).toBe('ddddddd1-2222-3333-4444-555555555555');
  });

  it('manual server verification drives the client state from setup_state (ready)', async () => {
    discoveryMocks.resolveApiBase.mockRejectedValue(
      discoveryError('NO_SERVERS', 'No Lovely Tech POS servers found on the LAN')
    );
    discoveryMocks.verifyManualServer.mockResolvedValue({
      baseUrl: 'http://192.168.1.50:8000/api/v1',
      identity: makeIdentity('READY', 'eeeeeee1-2222-3333-4444-555555555555'),
    });
    await bootApp();

    expect(await screen.findByText('Manual server configuration')).toBeInTheDocument();
    const input = screen.getByPlaceholderText(/http:\/\/192.168.1.50:8000/);
    fireEvent.change(input, { target: { value: 'http://192.168.1.50:8000' } });
    fireEvent.click(screen.getByText('Connect to server'));

    expect(await screen.findByText('Welcome back')).toBeInTheDocument();

    const config = readConfig();
    expect(config.setup_state).toBe('READY');
    expect(config.server_reference).toBe('eeeeeee1-2222-3333-4444-555555555555');
  });

  it('preserves client_id across restarts and discovery retries', async () => {
    discoveryMocks.resolveApiBase.mockResolvedValue(verifiedResolution('READY'));
    await bootApp();
    expect(await screen.findByText('Welcome back')).toBeInTheDocument();
    const firstClientId = readConfig().client_id;

    // Simulate an app restart: fresh module evaluation, same localStorage.
    cleanup();
    document.body.innerHTML = '';
    vi.resetModules();
    await bootApp();
    expect(await screen.findByText('Welcome back')).toBeInTheDocument();

    const config = readConfig();
    expect(config.client_id).toBe(firstClientId);
    expect(config.setup_state).toBe('READY');
    expect(config.server_reference).toBe('aaaaaaa1-2222-3333-4444-555555555555');
  });
});
