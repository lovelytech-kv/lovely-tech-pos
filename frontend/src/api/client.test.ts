import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const discoveryMocks = vi.hoisted(() => ({
  resolveApiBase: vi.fn(),
  fetchAndValidateDiscoveryInfo: vi.fn(),
}));

vi.mock('../services/discovery', async importOriginal => {
  const actual = await importOriginal<typeof import('../services/discovery')>();
  return {
    ...actual,
    resolveApiBase: discoveryMocks.resolveApiBase,
    fetchAndValidateDiscoveryInfo: discoveryMocks.fetchAndValidateDiscoveryInfo,
  };
});

const originalIdentity = {
  product: 'Lovely Tech POS System',
  protocol_version: '1.0.0',
  api_version: '1',
  app_version: '0.4.0',
  instance_id: 'aaaaaaa1-2222-3333-4444-555555555555',
  branch_code: 'SHOP-A',
  setup_state: 'NEW_SHOP_REQUIRED',
};

const readyIdentity = { ...originalIdentity, setup_state: 'READY' };

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

describe('API client bootstrap verification', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    localStorage.clear();
    discoveryMocks.resolveApiBase.mockResolvedValue({
      baseUrl: 'http://192.168.1.100:8000/api/v1',
      identity: originalIdentity,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it('persists the bootstrap session through the shared authentication mechanism', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify(bootstrapResponse)),
    }));
    const client = await import('./client.js');

    await client.bootstrapShop({
      branch_code: 'SHOP-A',
      branch_name: 'Main Shop',
      admin_username: 'admin',
      admin_password: 'secure-password-123',
      admin_display_name: 'Shop Admin',
    });

    expect(localStorage.getItem('ltpos_token')).toBe(bootstrapResponse.access_token);
    expect(client.currentUser()?.username).toBe('admin');
    expect(JSON.parse(localStorage.getItem('ltpos_user') ?? '{}')).toMatchObject({
      username: 'admin',
      role: 'ADMIN',
      branch_id: 'main-branch',
    });
  });

  it('accepts refreshed READY discovery only when the verified server identity matches', async () => {
    discoveryMocks.fetchAndValidateDiscoveryInfo.mockResolvedValue(readyIdentity);
    const client = await import('./client.js');
    await client.ensureApiBaseResolved();

    await expect(client.refreshServerSetupState()).resolves.toMatchObject({
      instance_id: originalIdentity.instance_id,
      setup_state: 'READY',
    });
  });

  it('rejects refreshed discovery with a mismatched server identity', async () => {
    discoveryMocks.fetchAndValidateDiscoveryInfo.mockResolvedValue({
      ...readyIdentity,
      instance_id: 'bbbbbbb1-2222-3333-4444-555555555555',
    });
    const client = await import('./client.js');
    await client.ensureApiBaseResolved();

    await expect(client.refreshServerSetupState()).rejects.toThrow(/identity changed/i);
  });

  it('rejects refreshed discovery when setup_state is not READY', async () => {
    discoveryMocks.fetchAndValidateDiscoveryInfo.mockResolvedValue({
      ...originalIdentity,
      setup_state: 'NEW_SHOP_REQUIRED',
    });
    const client = await import('./client.js');
    await client.ensureApiBaseResolved();

    await expect(client.refreshServerSetupState()).rejects.toThrow(/not READY/);
  });

  it('does not verify setup state when no previously verified identity exists', async () => {
    discoveryMocks.resolveApiBase.mockResolvedValue({
      baseUrl: 'http://192.168.1.100:8000/api/v1',
      identity: null,
    });
    discoveryMocks.fetchAndValidateDiscoveryInfo.mockResolvedValue(readyIdentity);
    const client = await import('./client.js');
    await client.ensureApiBaseResolved();

    await expect(client.refreshServerSetupState()).rejects.toThrow(/previously verified server identity/);
    expect(discoveryMocks.fetchAndValidateDiscoveryInfo).not.toHaveBeenCalled();
  });
});
