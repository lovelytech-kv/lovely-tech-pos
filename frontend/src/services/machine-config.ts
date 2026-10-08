/** Lovely Tech POS durable machine configuration.

Defines the machine-role contract (SERVER / CLIENT) and a pure-logic
local configuration manager. No Tauri plugin dependency is required:
the config is stored in localStorage under a namespaced key, which is
the same mechanism already used by the frontend for tokens, themes,
and the Admin manual server override.

Machine role is deliberately distinct from:
- authenticated user role (ADMIN / CASHIER)
- branch / shop identity (branches table)
- server instance_id (backend durable identity)

SERVER machines continue to use the existing backend instance_id.
CLIENT machines receive their own persistent client_id UUID.
*/

export type MachineRole = 'SERVER' | 'CLIENT';

/** Explicit finite setup state machine. */
export type SetupState =
  | 'UNINITIALIZED'
  | 'DISCOVERING'
  | 'SERVER_DETECTED'
  | 'CLIENT_SETUP_REQUIRED'
  | 'NEW_SHOP_REQUIRED'
  | 'EXISTING_SHOP_REQUIRED'
  | 'RESTORE_REQUIRED'
  | 'READY'
  | 'SETUP_ERROR';

export interface MachineConfig {
  machine_role: MachineRole;
  client_id: string | null;
  server_reference: string | null;
  config_version: number;
  setup_state: SetupState | null;
}

export const CURRENT_CONFIG_VERSION = 1;

const CONFIG_KEY = 'ltpos_machine_config';

/** Generate a v4 UUID without external dependencies. */
export function generateClientId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function createInitialMachineConfig(role: MachineRole): MachineConfig {
  return {
    machine_role: role,
    client_id: role === 'CLIENT' ? generateClientId() : null,
    server_reference: null,
    config_version: CURRENT_CONFIG_VERSION,
    setup_state: 'UNINITIALIZED',
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isMachineRole(value: unknown): value is MachineRole {
  return value === 'SERVER' || value === 'CLIENT';
}

function isSetupState(value: unknown): value is SetupState {
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
  return validStates.includes(value as SetupState);
}

function coerceString(value: unknown): string | null {
  if (typeof value === 'string' && value !== '') return value;
  return null;
}

/** Validate and migrate a raw parsed config to the current schema. */
export function normalizeMachineConfig(raw: unknown): MachineConfig | null {
  if (!isRecord(raw)) return null;

  const role = raw.machine_role;
  if (!isMachineRole(role)) return null;

  const version = typeof raw.config_version === 'number' && Number.isFinite(raw.config_version)
    ? Math.max(1, Math.floor(raw.config_version))
    : CURRENT_CONFIG_VERSION;

  const clientId = coerceString(raw.client_id);
  const serverRef = coerceString(raw.server_reference);
  const setupStateRaw = coerceString(raw.setup_state);
  const setupState = setupStateRaw && isSetupState(setupStateRaw) ? setupStateRaw : null;

  if (role === 'SERVER') {
    return {
      machine_role: 'SERVER',
      client_id: null,
      server_reference: serverRef,
      config_version: version,
      setup_state: setupState,
    };
  }

  return {
    machine_role: 'CLIENT',
    client_id: clientId ?? generateClientId(),
    server_reference: serverRef,
    config_version: version,
    setup_state: setupState,
  };
}

export function loadMachineConfig(): MachineConfig | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(CONFIG_KEY);
    if (!raw) return null;
    return normalizeMachineConfig(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function saveMachineConfig(config: MachineConfig): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
}

export function getOrCreateMachineConfig(role: MachineRole): MachineConfig {
  const existing = loadMachineConfig();
  if (existing && existing.machine_role === role) return existing;
  const fresh = createInitialMachineConfig(role);
  saveMachineConfig(fresh);
  return fresh;
}

export function setMachineRole(role: MachineRole): MachineConfig {
  const existing = loadMachineConfig();
  const base: MachineConfig = existing
    ? {
        machine_role: role,
        client_id: role === 'CLIENT' ? (existing.client_id ?? generateClientId()) : null,
        server_reference: existing.server_reference,
        config_version: existing.config_version ?? CURRENT_CONFIG_VERSION,
        setup_state: existing.setup_state,
      }
    : createInitialMachineConfig(role);
  saveMachineConfig(base);
  return base;
}

export function setServerReference(reference: string | null): MachineConfig | null {
  const existing = loadMachineConfig();
  if (!existing) return null;
  const updated: MachineConfig = { ...existing, server_reference: reference };
  saveMachineConfig(updated);
  return updated;
}

/** Persist a validated setup state. Only durable states are stored. */
export function setSetupState(state: SetupState | null): MachineConfig | null {
  const existing = loadMachineConfig();
  if (!existing) return null;
  if (state !== null && !isSetupState(state)) return null;
  const updated: MachineConfig = { ...existing, setup_state: state };
  saveMachineConfig(updated);
  return updated;
}

/** Clear transient discovery state, keeping durable facts. */
export function clearTransientSetupState(): MachineConfig | null {
  const existing = loadMachineConfig();
  if (!existing) return null;
  const transientStates: SetupState[] = ['DISCOVERING', 'SERVER_DETECTED'];
  if (transientStates.includes(existing.setup_state as SetupState)) {
    const updated: MachineConfig = { ...existing, setup_state: 'UNINITIALIZED' };
    saveMachineConfig(updated);
    return updated;
  }
  return existing;
}

export function clearMachineConfig(): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(CONFIG_KEY);
}

/** Returns true if the stored config contains any secrets/credentials. */
export function configHasSecrets(config: MachineConfig): boolean {
  const serialized = JSON.stringify(config).toLowerCase();
  const forbidden = ['password', 'passwd', 'secret', 'token', 'api_key', 'apikey', 'database_url', 'db_url', 'postgres'];
  return forbidden.some(term => serialized.includes(term));
}

/** Determine the next setup state for a CLIENT machine based on current state and discovery result. */
export function computeClientSetupState(
  current: SetupState | null,
  discoveryResult: 'success' | 'identity_mismatch' | 'no_servers' | 'all_unreachable' | 'error'
): SetupState {
  // If already in a durable setup-required state, don't regress
  const durableStates: SetupState[] = [
    'CLIENT_SETUP_REQUIRED',
    'NEW_SHOP_REQUIRED',
    'EXISTING_SHOP_REQUIRED',
    'RESTORE_REQUIRED',
    'READY',
    'SETUP_ERROR',
  ];
  if (current && durableStates.includes(current)) {
    return current;
  }

  switch (discoveryResult) {
    case 'success':
      return 'SERVER_DETECTED'; // Transient - will transition to CLIENT_SETUP_REQUIRED after verification
    case 'identity_mismatch':
      return 'SETUP_ERROR';
    case 'no_servers':
    case 'all_unreachable':
      return 'CLIENT_SETUP_REQUIRED'; // No server found - needs manual Admin config
    case 'error':
    default:
      return 'SETUP_ERROR';
  }
}

/** Determine the next setup state for a SERVER machine. */
export function computeServerSetupState(
  current: SetupState | null,
  hasBackendIdentity: boolean
): SetupState {
  const durableStates: SetupState[] = [
    'NEW_SHOP_REQUIRED',
    'EXISTING_SHOP_REQUIRED',
    'RESTORE_REQUIRED',
    'READY',
    'SETUP_ERROR',
  ];
  if (current && durableStates.includes(current)) {
    return current;
  }

  if (hasBackendIdentity) {
    return 'READY';
  }
  return 'NEW_SHOP_REQUIRED';
}

/** Check if a setup state is transient (should not be permanently persisted without explicit action). */
export function isTransientSetupState(state: SetupState | null): boolean {
  return state === 'DISCOVERING' || state === 'SERVER_DETECTED';
}

/** Check if a setup state indicates the machine is ready for normal operation. */
export function isReadySetupState(state: SetupState | null): boolean {
  return state === 'READY';
}

/** Check if a setup state requires Admin intervention. */
export function requiresAdminSetup(state: SetupState | null): boolean {
  return state === 'NEW_SHOP_REQUIRED' ||
         state === 'EXISTING_SHOP_REQUIRED' ||
         state === 'RESTORE_REQUIRED' ||
         state === 'CLIENT_SETUP_REQUIRED';
}

/** Check if a setup state is an error condition. */
export function isSetupErrorState(state: SetupState | null): boolean {
  return state === 'SETUP_ERROR';
}