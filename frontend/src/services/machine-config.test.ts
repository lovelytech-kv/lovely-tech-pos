/** Focused tests for durable machine configuration (Packet 15-G, 15-H). */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  MachineRole,
  MachineConfig,
  SetupState,
  CURRENT_CONFIG_VERSION,
  generateClientId,
  createInitialMachineConfig,
  normalizeMachineConfig,
  loadMachineConfig,
  saveMachineConfig,
  getOrCreateMachineConfig,
  setMachineRole,
  setServerReference,
  setSetupState,
  clearMachineConfig,
  clearTransientSetupState,
  configHasSecrets,
  computeClientSetupState,
  computeServerSetupState,
  applyVerifiedServerToClient,
  isTransientSetupState,
  isReadySetupState,
  requiresAdminSetup,
  isSetupErrorState,
} from './machine-config';

const CONFIG_KEY = 'ltpos_machine_config';

describe('machine configuration', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('creates a new config for SERVER role', () => {
    const config = createInitialMachineConfig('SERVER');
    expect(config.machine_role).toBe('SERVER');
    expect(config.client_id).toBeNull();
    expect(config.config_version).toBe(CURRENT_CONFIG_VERSION);
    expect(config.server_reference).toBeNull();
    expect(config.setup_state).toBe('UNINITIALIZED');
  });

  it('creates a new config for CLIENT role with a client_id', () => {
    const config = createInitialMachineConfig('CLIENT');
    expect(config.machine_role).toBe('CLIENT');
    expect(config.client_id).not.toBeNull();
    expect(config.client_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    expect(config.setup_state).toBe('UNINITIALIZED');
  });

  it('persists SERVER role across restarts', () => {
    const config = createInitialMachineConfig('SERVER');
    saveMachineConfig(config);
    const loaded = loadMachineConfig();
    expect(loaded).not.toBeNull();
    expect(loaded!.machine_role).toBe('SERVER');
    expect(loaded!.client_id).toBeNull();
  });

  it('persists CLIENT role across restarts', () => {
    const config = createInitialMachineConfig('CLIENT');
    saveMachineConfig(config);
    const loaded = loadMachineConfig();
    expect(loaded).not.toBeNull();
    expect(loaded!.machine_role).toBe('CLIENT');
    expect(loaded!.client_id).not.toBeNull();
  });

  it('generates client_id once and remains stable', () => {
    const first = createInitialMachineConfig('CLIENT');
    saveMachineConfig(first);
    const loaded = loadMachineConfig();
    expect(loaded!.client_id).toBe(first.client_id);
  });

  it('client_id differs from server instance_id', () => {
    const serverConfig = createInitialMachineConfig('SERVER');
    const clientConfig = createInitialMachineConfig('CLIENT');
    // SERVER has no client_id; CLIENT has its own UUID.
    expect(serverConfig.client_id).toBeNull();
    expect(clientConfig.client_id).not.toBeNull();
    // client_id must not look like a server instance_id (different namespace).
    expect(clientConfig.client_id).not.toBe(serverConfig.client_id);
  });

  it('recovers from malformed/missing config', () => {
    localStorage.setItem(CONFIG_KEY, 'not-json');
    expect(loadMachineConfig()).toBeNull();

    localStorage.setItem(CONFIG_KEY, JSON.stringify({ foo: 'bar' }));
    expect(loadMachineConfig()).toBeNull();

    localStorage.setItem(CONFIG_KEY, JSON.stringify({ machine_role: 'BOGUS' }));
    expect(loadMachineConfig()).toBeNull();

    // Valid config still loads.
    localStorage.setItem(CONFIG_KEY, JSON.stringify({ machine_role: 'CLIENT', client_id: 'abc' }));
    const loaded = loadMachineConfig();
    expect(loaded).not.toBeNull();
    expect(loaded!.machine_role).toBe('CLIENT');
  });

  it('does not store secrets or database credentials', () => {
    const config = createInitialMachineConfig('CLIENT');
    expect(configHasSecrets(config)).toBe(false);

    const withSecrets: MachineConfig = {
      ...config,
      server_reference: 'http://user:password@192.168.1.5:8000/api/v1',
    };
    // server_reference is a URL reference, not a credential store.
    // The check is on the whole config object.
    expect(configHasSecrets(withSecrets)).toBe(true);

    const safe: MachineConfig = { ...config, server_reference: 'http://192.168.1.5:8000/api/v1' };
    expect(configHasSecrets(safe)).toBe(false);
  });

  it('getOrCreateMachineConfig returns existing config when present', () => {
    const created = createInitialMachineConfig('CLIENT');
    saveMachineConfig(created);
    const existing = getOrCreateMachineConfig('CLIENT');
    expect(existing.client_id).toBe(created.client_id);
  });

  it('setMachineRole switches role and clears client_id for SERVER', () => {
    const client = createInitialMachineConfig('CLIENT');
    saveMachineConfig(client);
    const switched = setMachineRole('SERVER');
    expect(switched.machine_role).toBe('SERVER');
    expect(switched.client_id).toBeNull();
  });

  it('setServerReference and setSetupState persist', () => {
    const client = createInitialMachineConfig('CLIENT');
    saveMachineConfig(client);
    setServerReference('http://192.168.1.5:8000/api/v1');
    let loaded = loadMachineConfig();
    expect(loaded!.server_reference).toBe('http://192.168.1.5:8000/api/v1');

    setSetupState('NEW_SHOP_REQUIRED');
    loaded = loadMachineConfig();
    expect(loaded!.setup_state).toBe('NEW_SHOP_REQUIRED');
  });

  it('clearMachineConfig removes the stored config', () => {
    saveMachineConfig(createInitialMachineConfig('CLIENT'));
    clearMachineConfig();
    expect(loadMachineConfig()).toBeNull();
  });
});

describe('setup state machine (Packet 15-H)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('normalizeMachineConfig handles setup_state', () => {
    it('accepts valid setup_state values', () => {
      const validStates: SetupState[] = [
        'UNINITIALIZED',
        'DISCOVERING',
        'SERVER_DETECTED',
        'CLIENT_SETUP_REQUIRED',
        'NEW_SHOP_REQUIRED',
        'EXISTING_SHOP_REQUIRED',
        'RESTORE_REQUIRED',
        'READY',
        'SETUP_ERROR',
      ];
      for (const state of validStates) {
        const raw = { machine_role: 'CLIENT', client_id: 'test-id', setup_state: state, config_version: 1 };
        const normalized = normalizeMachineConfig(raw);
        expect(normalized).not.toBeNull();
        expect(normalized!.setup_state).toBe(state);
      }
    });

    it('rejects invalid setup_state and normalizes to null', () => {
      const raw = { machine_role: 'CLIENT', client_id: 'test-id', setup_state: 'INVALID_STATE', config_version: 1 };
      const normalized = normalizeMachineConfig(raw);
      expect(normalized).not.toBeNull();
      expect(normalized!.setup_state).toBeNull();
    });

    it('SERVER config ignores client_id from raw and sets null', () => {
      const raw = { machine_role: 'SERVER', client_id: 'should-be-null', setup_state: 'READY', config_version: 1 };
      const normalized = normalizeMachineConfig(raw);
      expect(normalized).not.toBeNull();
      expect(normalized!.machine_role).toBe('SERVER');
      expect(normalized!.client_id).toBeNull();
      expect(normalized!.setup_state).toBe('READY');
    });

    it('CLIENT config generates client_id if missing', () => {
      const raw = { machine_role: 'CLIENT', setup_state: 'UNINITIALIZED', config_version: 1 };
      const normalized = normalizeMachineConfig(raw);
      expect(normalized).not.toBeNull();
      expect(normalized!.machine_role).toBe('CLIENT');
      expect(normalized!.client_id).not.toBeNull();
    });
  });

  describe('computeClientSetupState', () => {
    it('fresh CLIENT → discovery/setup-required state on no_servers', () => {
      const next = computeClientSetupState('UNINITIALIZED', 'no_servers');
      expect(next).toBe('CLIENT_SETUP_REQUIRED');
    });

    it('fresh CLIENT → discovery/setup-required state on all_unreachable', () => {
      const next = computeClientSetupState('UNINITIALIZED', 'all_unreachable');
      expect(next).toBe('CLIENT_SETUP_REQUIRED');
    });

    it('verified server → SERVER_DETECTED (transient)', () => {
      const next = computeClientSetupState('UNINITIALIZED', 'success');
      expect(next).toBe('SERVER_DETECTED');
    });

    it('identity mismatch → SETUP_ERROR', () => {
      const next = computeClientSetupState('UNINITIALIZED', 'identity_mismatch');
      expect(next).toBe('SETUP_ERROR');
    });

    it('error → SETUP_ERROR', () => {
      const next = computeClientSetupState('UNINITIALIZED', 'error');
      expect(next).toBe('SETUP_ERROR');
    });

    it('does not regress from durable CLIENT_SETUP_REQUIRED', () => {
      const next = computeClientSetupState('CLIENT_SETUP_REQUIRED', 'success');
      expect(next).toBe('CLIENT_SETUP_REQUIRED');
    });

    it('does not regress from durable NEW_SHOP_REQUIRED', () => {
      const next = computeClientSetupState('NEW_SHOP_REQUIRED', 'success');
      expect(next).toBe('NEW_SHOP_REQUIRED');
    });

    it('does not regress from READY', () => {
      const next = computeClientSetupState('READY', 'no_servers');
      expect(next).toBe('READY');
    });

    it('does not regress from SETUP_ERROR', () => {
      const next = computeClientSetupState('SETUP_ERROR', 'success');
      expect(next).toBe('SETUP_ERROR');
    });
  });

  describe('computeClientSetupState with verified server setup_state (Packet 15-I.3-B)', () => {
    it('verified READY server → client READY', () => {
      const next = computeClientSetupState('UNINITIALIZED', 'success', 'READY');
      expect(next).toBe('READY');
    });

    it('verified NEW_SHOP_REQUIRED server → client waits (no client-side provisioning)', () => {
      const next = computeClientSetupState('UNINITIALIZED', 'success', 'NEW_SHOP_REQUIRED');
      expect(next).toBe('NEW_SHOP_REQUIRED');
    });

    it('verified EXISTING_SHOP_REQUIRED server → client waits (no client-side provisioning)', () => {
      const next = computeClientSetupState('UNINITIALIZED', 'success', 'EXISTING_SHOP_REQUIRED');
      expect(next).toBe('EXISTING_SHOP_REQUIRED');
    });

    it('waiting client transitions to READY once the server reports READY', () => {
      expect(computeClientSetupState('NEW_SHOP_REQUIRED', 'success', 'READY')).toBe('READY');
      expect(computeClientSetupState('EXISTING_SHOP_REQUIRED', 'success', 'READY')).toBe('READY');
      expect(computeClientSetupState('CLIENT_SETUP_REQUIRED', 'success', 'READY')).toBe('READY');
    });

    it('READY client mirrors a server that reports NEW_SHOP_REQUIRED again', () => {
      const next = computeClientSetupState('READY', 'success', 'NEW_SHOP_REQUIRED');
      expect(next).toBe('NEW_SHOP_REQUIRED');
      expect(next).not.toBe('READY');
    });

    it('unknown setup_state from a verified server never becomes READY', () => {
      const next = computeClientSetupState('UNINITIALIZED', 'success', 'SOME_FUTURE_STATE');
      expect(next).toBe('SETUP_ERROR');
      expect(next).not.toBe('READY');
    });

    it('failed discovery never becomes READY', () => {
      expect(computeClientSetupState('UNINITIALIZED', 'no_servers')).toBe('CLIENT_SETUP_REQUIRED');
      expect(computeClientSetupState('UNINITIALIZED', 'all_unreachable')).toBe('CLIENT_SETUP_REQUIRED');
      expect(computeClientSetupState('UNINITIALIZED', 'identity_mismatch')).toBe('SETUP_ERROR');
      expect(computeClientSetupState('UNINITIALIZED', 'error')).toBe('SETUP_ERROR');
      expect(computeClientSetupState('UNINITIALIZED', 'all_unreachable')).not.toBe('READY');
      expect(computeClientSetupState('CLIENT_SETUP_REQUIRED', 'all_unreachable')).toBe('CLIENT_SETUP_REQUIRED');
    });
  });

  describe('applyVerifiedServerToClient (Packet 15-I.3-B)', () => {
    it('persists the backend instance_id as the stable server_reference', () => {
      saveMachineConfig(createInitialMachineConfig('CLIENT'));
      const updated = applyVerifiedServerToClient({
        instance_id: '11111111-2222-3333-4444-555555555555',
        setup_state: 'READY',
      });
      expect(updated).not.toBeNull();
      expect(updated!.server_reference).toBe('11111111-2222-3333-4444-555555555555');
      expect(updated!.setup_state).toBe('READY');
      // Hostname/IP is never the persisted identity.
      expect(updated!.server_reference).not.toMatch(/^http/);
      expect(updated!.server_reference).not.toMatch(/\d+\.\d+\.\d+\.\d+/);
    });

    it('client waits when the verified server reports NEW_SHOP_REQUIRED', () => {
      saveMachineConfig(createInitialMachineConfig('CLIENT'));
      const updated = applyVerifiedServerToClient({
        instance_id: '22222222-2222-3333-4444-555555555555',
        setup_state: 'NEW_SHOP_REQUIRED',
      });
      expect(updated!.setup_state).toBe('NEW_SHOP_REQUIRED');
      expect(updated!.server_reference).toBe('22222222-2222-3333-4444-555555555555');
    });

    it('client waits when the verified server reports EXISTING_SHOP_REQUIRED', () => {
      saveMachineConfig(createInitialMachineConfig('CLIENT'));
      const updated = applyVerifiedServerToClient({
        instance_id: '33333333-3333-3333-4444-555555555555',
        setup_state: 'EXISTING_SHOP_REQUIRED',
      });
      expect(updated!.setup_state).toBe('EXISTING_SHOP_REQUIRED');
    });

    it('preserves the existing client_id across verified applications and retries', () => {
      const created = createInitialMachineConfig('CLIENT');
      saveMachineConfig(created);
      applyVerifiedServerToClient({ instance_id: 'aaa', setup_state: 'NEW_SHOP_REQUIRED' });
      applyVerifiedServerToClient({ instance_id: 'aaa', setup_state: 'READY' });
      const loaded = loadMachineConfig();
      expect(loaded!.client_id).toBe(created.client_id);
      expect(loaded!.setup_state).toBe('READY');
    });

    it('null verified response does not move the client to READY', () => {
      saveMachineConfig(createInitialMachineConfig('CLIENT'));
      const updated = applyVerifiedServerToClient(null);
      expect(updated!.setup_state).toBe('SERVER_DETECTED');
      expect(updated!.setup_state).not.toBe('READY');
    });

    it('returns null when no machine config exists', () => {
      expect(applyVerifiedServerToClient({ instance_id: 'x', setup_state: 'READY' })).toBeNull();
    });

    it('returns null for SERVER role configs', () => {
      saveMachineConfig(createInitialMachineConfig('SERVER'));
      expect(applyVerifiedServerToClient({ instance_id: 'x', setup_state: 'READY' })).toBeNull();
    });
  });

  describe('computeServerSetupState', () => {
    it('fresh SERVER with no backend identity → NEW_SHOP_REQUIRED', () => {
      const next = computeServerSetupState('UNINITIALIZED', false);
      expect(next).toBe('NEW_SHOP_REQUIRED');
    });

    it('fresh SERVER with backend identity → READY', () => {
      const next = computeServerSetupState('UNINITIALIZED', true);
      expect(next).toBe('READY');
    });

    it('does not regress from durable NEW_SHOP_REQUIRED', () => {
      const next = computeServerSetupState('NEW_SHOP_REQUIRED', true);
      expect(next).toBe('NEW_SHOP_REQUIRED');
    });

    it('does not regress from READY', () => {
      const next = computeServerSetupState('READY', false);
      expect(next).toBe('READY');
    });
  });

  describe('state classification helpers', () => {
    it('isTransientSetupState identifies DISCOVERING and SERVER_DETECTED', () => {
      expect(isTransientSetupState('DISCOVERING')).toBe(true);
      expect(isTransientSetupState('SERVER_DETECTED')).toBe(true);
      expect(isTransientSetupState('UNINITIALIZED')).toBe(false);
      expect(isTransientSetupState('CLIENT_SETUP_REQUIRED')).toBe(false);
      expect(isTransientSetupState('READY')).toBe(false);
    });

    it('isReadySetupState identifies only READY', () => {
      expect(isReadySetupState('READY')).toBe(true);
      expect(isReadySetupState('UNINITIALIZED')).toBe(false);
      expect(isReadySetupState('SERVER_DETECTED')).toBe(false);
      expect(isReadySetupState('CLIENT_SETUP_REQUIRED')).toBe(false);
    });

    it('requiresAdminSetup identifies Admin-only states', () => {
      expect(requiresAdminSetup('NEW_SHOP_REQUIRED')).toBe(true);
      expect(requiresAdminSetup('EXISTING_SHOP_REQUIRED')).toBe(true);
      expect(requiresAdminSetup('RESTORE_REQUIRED')).toBe(true);
      expect(requiresAdminSetup('CLIENT_SETUP_REQUIRED')).toBe(true);
      expect(requiresAdminSetup('READY')).toBe(false);
      expect(requiresAdminSetup('UNINITIALIZED')).toBe(false);
      expect(requiresAdminSetup('DISCOVERING')).toBe(false);
    });

    it('isSetupErrorState identifies SETUP_ERROR', () => {
      expect(isSetupErrorState('SETUP_ERROR')).toBe(true);
      expect(isSetupErrorState('CLIENT_SETUP_REQUIRED')).toBe(false);
      expect(isSetupErrorState('READY')).toBe(false);
    });
  });

  describe('clearTransientSetupState', () => {
    it('clears DISCOVERING to UNINITIALIZED', () => {
      const config = createInitialMachineConfig('CLIENT');
      config.setup_state = 'DISCOVERING';
      saveMachineConfig(config);
      const cleared = clearTransientSetupState();
      expect(cleared).not.toBeNull();
      expect(cleared!.setup_state).toBe('UNINITIALIZED');
    });

    it('clears SERVER_DETECTED to UNINITIALIZED', () => {
      const config = createInitialMachineConfig('CLIENT');
      config.setup_state = 'SERVER_DETECTED';
      saveMachineConfig(config);
      const cleared = clearTransientSetupState();
      expect(cleared).not.toBeNull();
      expect(cleared!.setup_state).toBe('UNINITIALIZED');
    });

    it('does not modify durable states', () => {
      const config = createInitialMachineConfig('CLIENT');
      config.setup_state = 'CLIENT_SETUP_REQUIRED';
      saveMachineConfig(config);
      const cleared = clearTransientSetupState();
      expect(cleared).not.toBeNull();
      expect(cleared!.setup_state).toBe('CLIENT_SETUP_REQUIRED');
    });

    it('does not modify READY', () => {
      const config = createInitialMachineConfig('CLIENT');
      config.setup_state = 'READY';
      saveMachineConfig(config);
      const cleared = clearTransientSetupState();
      expect(cleared).not.toBeNull();
      expect(cleared!.setup_state).toBe('READY');
    });
  });

  describe('setSetupState validation', () => {
    it('rejects invalid setup state', () => {
      const config = createInitialMachineConfig('CLIENT');
      saveMachineConfig(config);
      const result = setSetupState('INVALID' as SetupState);
      expect(result).toBeNull();
      const loaded = loadMachineConfig();
      expect(loaded!.setup_state).toBe('UNINITIALIZED');
    });

    it('accepts null to clear', () => {
      const config = createInitialMachineConfig('CLIENT');
      config.setup_state = 'READY';
      saveMachineConfig(config);
      const result = setSetupState(null);
      expect(result).not.toBeNull();
      expect(result!.setup_state).toBeNull();
    });
  });

  describe('config version compatibility', () => {
    it('preserves config_version across migrations', () => {
      const config = createInitialMachineConfig('CLIENT');
      config.config_version = 2;
      saveMachineConfig(config);
      const loaded = loadMachineConfig();
      expect(loaded!.config_version).toBe(2);
    });

    it('defaults to CURRENT_CONFIG_VERSION when missing', () => {
      localStorage.setItem(CONFIG_KEY, JSON.stringify({ machine_role: 'CLIENT', client_id: 'test' }));
      const loaded = loadMachineConfig();
      expect(loaded!.config_version).toBe(CURRENT_CONFIG_VERSION);
    });

    it('normalizes invalid version to CURRENT_CONFIG_VERSION', () => {
      localStorage.setItem(CONFIG_KEY, JSON.stringify({ machine_role: 'CLIENT', client_id: 'test', config_version: -5 }));
      const loaded = loadMachineConfig();
      expect(loaded!.config_version).toBe(CURRENT_CONFIG_VERSION);
    });
  });
});