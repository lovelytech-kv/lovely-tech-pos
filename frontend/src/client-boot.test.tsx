/** Boot-flow tests for Packet 15-I.3-B.
 *
 * The CLIENT machine state must be driven by the setup_state of a
 * server verified through mDNS + HTTP /discovery/info (or the Admin
 * manual server flow, which uses the same verification). A successful
 * discovery alone must not mark the client READY.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent, cleanup } from './test-utils';

const appRoots = vi.hoisted(() => ({
  roots: [] as { unmount: () => void }[],
}));

vi.mock('react-dom/client', async importOriginal => {
  const actual = await importOriginal<typeof import('react-dom/client')>();
  return {
    ...actual,
    createRoot: (...args: Parameters<typeof actual.createRoot>) => {
      const root = actual.createRoot(...args);
      appRoots.roots.push(root);
      return root;
    },
  };
});

const discoveryMocks = vi.hoisted(() => ({
  resolveApiBase: vi.fn(),
  resolveServer: vi.fn(),
  verifyManualServer: vi.fn(),
  fetchAndValidateDiscoveryInfo: vi.fn(),
}));

vi.mock('./services/discovery', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./services/discovery')>();
  return {
    ...actual,
    isTauriEnvironment: () => true,
    resolveApiBase: discoveryMocks.resolveApiBase,
    resolveServer: discoveryMocks.resolveServer,
    verifyManualServer: discoveryMocks.verifyManualServer,
    fetchAndValidateDiscoveryInfo: discoveryMocks.fetchAndValidateDiscoveryInfo,
  };
});

const apiMocks = vi.hoisted(() => ({
  bootstrapShop: vi.fn(),
  refreshServerSetupState: vi.fn(),
  identity: null as ReturnType<typeof makeIdentity> | null,
}));

vi.mock('./api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api/client')>();
  return {
    ...actual,
    ensureApiBaseResolved: async () => {
      const resolution = await discoveryMocks.resolveApiBase();
      apiMocks.identity = resolution.identity;
      return resolution.baseUrl;
    },
    resetApiBaseResolution: async () => {
      apiMocks.identity = null;
      const resolution = await discoveryMocks.resolveApiBase();
      apiMocks.identity = resolution.identity;
      return resolution.baseUrl;
    },
    getResolvedServerIdentity: () => apiMocks.identity,
    configureManualServer: async (input: string) => {
      const result = await actual.configureManualServer(input);
      apiMocks.identity = result.identity;
      return result;
    },
    bootstrapShop: apiMocks.bootstrapShop,
    refreshServerSetupState: apiMocks.refreshServerSetupState,
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
  const loadMain = import.meta.glob('./main.tsx')['./main.tsx'];
  if (!loadMain) throw new Error('Could not load the TypeScript app entry point.');
  await loadMain();
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

const bootstrapResponse = {
  access_token: 'bootstrap-session-token',
  token_type: 'bearer',
  expires_at: '2099-01-01T00:00:00Z',
  user_id: 'admin-user',
  username: 'admin',
  display_name: 'Shop Admin',
  role: 'ADMIN',
  branch_id: 'main-branch',
  setup_state: 'READY',
};

function prepareServerBootstrap() {
  localStorage.setItem(CONFIG_KEY, JSON.stringify({
    machine_role: 'SERVER',
    client_id: null,
    server_reference: null,
    config_version: 1,
    setup_state: 'NEW_SHOP_REQUIRED',
  }));
  localStorage.setItem('ltpos_token', 'existing-session-token');
  localStorage.setItem('ltpos_user', JSON.stringify({
    username: 'admin',
    role: 'ADMIN',
    display_name: 'Shop Admin',
    branch_id: 'main-branch',
  }));
  discoveryMocks.resolveApiBase.mockResolvedValue(verifiedResolution('NEW_SHOP_REQUIRED'));
  apiMocks.bootstrapShop.mockResolvedValue(bootstrapResponse);
}

function setAdminSession() {
  localStorage.setItem('ltpos_token', 'test-session-token');
  localStorage.setItem('ltpos_user', JSON.stringify({
    username: 'admin',
    role: 'ADMIN',
    display_name: 'Shop Admin',
    branch_id: 'main-branch',
  }));
}

async function submitServerBootstrap() {
  fireEvent.click(await screen.findByText('Provision new shop'));
  await screen.findByText('New shop bootstrap');

  fireEvent.change(screen.getByLabelText('Branch code'), { target: { value: 'SHOP-A' } });
  fireEvent.change(screen.getByLabelText('Branch name'), { target: { value: 'Main Shop' } });
  fireEvent.change(screen.getByLabelText('Admin username'), { target: { value: 'admin' } });
  fireEvent.change(screen.getByLabelText('Admin password'), { target: { value: 'secure-password-123' } });
  fireEvent.change(screen.getByLabelText('Admin display name'), { target: { value: 'Shop Admin' } });
  fireEvent.click(screen.getByText('Provision shop and create Admin'));
}

describe('client boot flow (Packet 15-I.3-B)', () => {
  let originalLocation: Location;

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    localStorage.clear();
    localStorage.setItem(CONFIG_KEY, JSON.stringify({
      machine_role: 'CLIENT',
      client_id: 'test-client-id',
      server_reference: null,
      config_version: 1,
      setup_state: 'UNINITIALIZED',
    }));
    apiMocks.identity = null;
    originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      value: { protocol: 'tauri:', hostname: 'localhost' },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    cleanup();
    appRoots.roots.splice(0).forEach(root => root.unmount());
    document.body.innerHTML = '';
    vi.unstubAllGlobals();
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

  it('fresh machines probe only localhost and select SERVER with the discovered setup state', async () => {
    localStorage.removeItem(CONFIG_KEY);
    discoveryMocks.resolveApiBase.mockResolvedValue(verifiedResolution('NEW_SHOP_REQUIRED'));
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => makeIdentity('NEW_SHOP_REQUIRED'),
    });
    vi.stubGlobal('fetch', fetchMock);

    await bootApp();

    expect(await screen.findByText('Provision new shop')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalled();
    expect(fetchMock.mock.calls.every(([url]) => url === 'http://127.0.0.1:8000/discovery/info')).toBe(true);
    expect(readConfig()).toMatchObject({
      machine_role: 'SERVER',
      setup_state: 'NEW_SHOP_REQUIRED',
    });
  });

  it('preserves the saved machine role on later launches without probing localhost', async () => {
    localStorage.setItem(CONFIG_KEY, JSON.stringify({
      machine_role: 'SERVER',
      client_id: null,
      server_reference: null,
      config_version: 1,
      setup_state: 'READY',
    }));
    discoveryMocks.resolveApiBase.mockResolvedValue(verifiedResolution('READY'));
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    await bootApp();

    expect(await screen.findByText('Welcome back')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(readConfig().machine_role).toBe('SERVER');
  });

  it('does not retain CLIENT READY when discovery has no verified identity', async () => {
    setAdminSession();
    localStorage.setItem(CONFIG_KEY, JSON.stringify({
      machine_role: 'CLIENT',
      client_id: 'saved-client',
      server_reference: 'saved-server',
      config_version: 1,
      setup_state: 'READY',
    }));
    discoveryMocks.resolveApiBase.mockResolvedValue({
      baseUrl: 'http://configured-server:8000/api/v1',
      identity: null,
    });

    await bootApp();

    expect(await screen.findByText('Setup error')).toBeInTheDocument();
    expect(screen.queryByText('Welcome back')).not.toBeInTheDocument();
    expect(readConfig().setup_state).toBe('SETUP_ERROR');
  });

  it('manual server configuration rejects an invalid setup_state instead of becoming READY', async () => {
    setAdminSession();
    discoveryMocks.resolveApiBase.mockRejectedValue(
      discoveryError('NO_SERVERS', 'No Lovely Tech POS servers found on the LAN')
    );
    discoveryMocks.verifyManualServer.mockResolvedValue({
      baseUrl: 'http://192.168.1.50:8000/api/v1',
      identity: makeIdentity('INVALID_STATE'),
    });

    await bootApp();
    expect(await screen.findByText('Manual server configuration')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/http:\/\/192.168.1.50:8000/), {
      target: { value: 'http://192.168.1.50:8000' },
    });
    fireEvent.click(screen.getByText('Connect to server'));

    expect(await screen.findByText('Setup error')).toBeInTheDocument();
    expect(readConfig().setup_state).toBe('SETUP_ERROR');
    expect(readConfig().setup_state).not.toBe('READY');
  });

  it('successful bootstrap followed by verified READY discovery enters READY', async () => {
    prepareServerBootstrap();
    apiMocks.refreshServerSetupState.mockResolvedValue(makeIdentity('READY'));
    await bootApp();

    await submitServerBootstrap();
    await screen.findByText('Good day. Your shop at a glance.');

    expect(apiMocks.bootstrapShop).toHaveBeenCalledTimes(1);
    expect(apiMocks.refreshServerSetupState).toHaveBeenCalledTimes(1);
    expect(readConfig().setup_state).toBe('READY');
  });

  it('discovery refresh failure after bootstrap persists SETUP_ERROR, not READY', async () => {
    prepareServerBootstrap();
    apiMocks.refreshServerSetupState.mockRejectedValue(new Error('Discovery refresh failed'));
    await bootApp();

    await submitServerBootstrap();
    expect(await screen.findByText('Setup error')).toBeInTheDocument();

    expect(apiMocks.bootstrapShop).toHaveBeenCalledTimes(1);
    expect(readConfig().setup_state).toBe('SETUP_ERROR');
    expect(readConfig().setup_state).not.toBe('READY');
  });

  it.each([
    ['identity mismatch', new Error('Refreshed identity mismatch')],
    ['non-READY setup state', new Error('Refreshed server is not READY')],
  ])('does not enter READY after bootstrap when refresh reports %s', async (_condition, error) => {
    prepareServerBootstrap();
    apiMocks.refreshServerSetupState.mockRejectedValue(error);
    await bootApp();

    await submitServerBootstrap();
    expect(await screen.findByText('Setup error')).toBeInTheDocument();

    expect(readConfig().setup_state).toBe('SETUP_ERROR');
    expect(readConfig().setup_state).not.toBe('READY');
  });

  it('retries discovery verification without submitting bootstrap again', async () => {
    prepareServerBootstrap();
    apiMocks.refreshServerSetupState
      .mockRejectedValueOnce(new Error('Temporary discovery failure'))
      .mockResolvedValueOnce(makeIdentity('READY'));
    await bootApp();

    await submitServerBootstrap();
    expect(await screen.findByText('Setup error')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Retry Discovery'));

    await screen.findByText('Good day. Your shop at a glance.');
    expect(apiMocks.bootstrapShop).toHaveBeenCalledTimes(1);
    expect(apiMocks.refreshServerSetupState).toHaveBeenCalledTimes(2);
    expect(readConfig().setup_state).toBe('READY');
  });
});
