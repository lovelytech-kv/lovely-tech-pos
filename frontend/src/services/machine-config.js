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
import { isServerSetupState } from './discovery';
export const CURRENT_CONFIG_VERSION = 1;
const CONFIG_KEY = 'ltpos_machine_config';
/** Generate a v4 UUID without external dependencies. */
export function generateClientId() {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = (Math.random() * 16) | 0;
        const v = c === 'x' ? r : (r & 0x3) | 0x8;
        return v.toString(16);
    });
}
export function createInitialMachineConfig(role) {
    return {
        machine_role: role,
        client_id: role === 'CLIENT' ? generateClientId() : null,
        server_reference: null,
        config_version: CURRENT_CONFIG_VERSION,
        setup_state: 'UNINITIALIZED',
    };
}
function isRecord(value) {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function isMachineRole(value) {
    return value === 'SERVER' || value === 'CLIENT';
}
function isSetupState(value) {
    const validStates = [
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
    return validStates.includes(value);
}
function coerceString(value) {
    if (typeof value === 'string' && value !== '')
        return value;
    return null;
}
/** Validate and migrate a raw parsed config to the current schema. */
export function normalizeMachineConfig(raw) {
    if (!isRecord(raw))
        return null;
    const role = raw.machine_role;
    if (!isMachineRole(role))
        return null;
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
export function loadMachineConfig() {
    if (typeof localStorage === 'undefined')
        return null;
    try {
        const raw = localStorage.getItem(CONFIG_KEY);
        if (!raw)
            return null;
        return normalizeMachineConfig(JSON.parse(raw));
    }
    catch {
        return null;
    }
}
export function saveMachineConfig(config) {
    if (typeof localStorage === 'undefined')
        return;
    localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
}
export function getOrCreateMachineConfig(role) {
    const existing = loadMachineConfig();
    if (existing && existing.machine_role === role)
        return existing;
    const fresh = createInitialMachineConfig(role);
    saveMachineConfig(fresh);
    return fresh;
}
export function setMachineRole(role) {
    const existing = loadMachineConfig();
    const base = existing
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
export function setServerReference(reference) {
    const existing = loadMachineConfig();
    if (!existing)
        return null;
    const updated = { ...existing, server_reference: reference };
    saveMachineConfig(updated);
    return updated;
}
/** Persist a validated setup state. Only durable states are stored. */
export function setSetupState(state) {
    const existing = loadMachineConfig();
    if (!existing)
        return null;
    if (state !== null && !isSetupState(state))
        return null;
    const updated = { ...existing, setup_state: state };
    saveMachineConfig(updated);
    return updated;
}
/** Clear transient discovery state, keeping durable facts. */
export function clearTransientSetupState() {
    const existing = loadMachineConfig();
    if (!existing)
        return null;
    const transientStates = ['DISCOVERING', 'SERVER_DETECTED'];
    if (transientStates.includes(existing.setup_state)) {
        const updated = { ...existing, setup_state: 'UNINITIALIZED' };
        saveMachineConfig(updated);
        return updated;
    }
    return existing;
}
export function clearMachineConfig() {
    if (typeof localStorage === 'undefined')
        return;
    localStorage.removeItem(CONFIG_KEY);
}
/** Returns true if the stored config contains any secrets/credentials. */
export function configHasSecrets(config) {
    const serialized = JSON.stringify(config).toLowerCase();
    const forbidden = ['password', 'passwd', 'secret', 'token', 'api_key', 'apikey', 'database_url', 'db_url', 'postgres'];
    return forbidden.some(term => serialized.includes(term));
}
/** Determine the next setup state for a CLIENT machine based on current state and discovery result.
 *
 * When discovery succeeded and a server was verified through mDNS + HTTP
 * /discovery/info, the server-reported setup_state is authoritative: the client
 * mirrors it. The client never performs server provisioning itself -
 * NEW_SHOP_REQUIRED and EXISTING_SHOP_REQUIRED mean the client must wait for
 * the server Admin to finish bootstrap/recovery.
 */
export function computeClientSetupState(current, discoveryResult, serverSetupState) {
    if (discoveryResult === 'success' && serverSetupState != null && serverSetupState !== '') {
        if (isServerSetupState(serverSetupState)) {
            switch (serverSetupState) {
                case 'READY':
                    return 'READY';
                case 'NEW_SHOP_REQUIRED':
                    return 'NEW_SHOP_REQUIRED';
                case 'EXISTING_SHOP_REQUIRED':
                    return 'EXISTING_SHOP_REQUIRED';
            }
        }
        // The server answered but reported an unknown setup_state: never assume READY.
        return 'SETUP_ERROR';
    }
    // If already in a durable setup-required state, don't regress
    const durableStates = [
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
            return 'SERVER_DETECTED'; // Transient - no verified server identity this boot
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
/**
 * Applies a verified server response to the CLIENT machine configuration.
 *
 * The backend instance_id is persisted as the stable server_reference -
 * hostnames and IP addresses change and are never used as the permanent
 * server identity. The existing client_id is preserved and never regenerated.
 * Returns the updated configuration, or null when no CLIENT config exists.
 */
export function applyVerifiedServerToClient(verified) {
    const existing = loadMachineConfig();
    if (!existing || existing.machine_role !== 'CLIENT')
        return null;
    const serverSetupState = verified && verified.setup_state !== '' ? verified.setup_state : null;
    const nextState = computeClientSetupState(existing.setup_state, 'success', serverSetupState);
    let updated = existing;
    if (verified && typeof verified.instance_id === 'string' && verified.instance_id !== '') {
        const withReference = setServerReference(verified.instance_id);
        if (withReference)
            updated = withReference;
    }
    const withState = setSetupState(nextState);
    if (withState)
        updated = withState;
    return updated;
}
/** Determine the next setup state for a SERVER machine. */
export function computeServerSetupState(current, hasBackendIdentity) {
    const durableStates = [
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
export function isTransientSetupState(state) {
    return state === 'DISCOVERING' || state === 'SERVER_DETECTED';
}
/** Check if a setup state indicates the machine is ready for normal operation. */
export function isReadySetupState(state) {
    return state === 'READY';
}
/** Check if a setup state requires Admin intervention. */
export function requiresAdminSetup(state) {
    return state === 'NEW_SHOP_REQUIRED' ||
        state === 'EXISTING_SHOP_REQUIRED' ||
        state === 'RESTORE_REQUIRED' ||
        state === 'CLIENT_SETUP_REQUIRED';
}
/** Check if a setup state is an error condition. */
export function isSetupErrorState(state) {
    return state === 'SETUP_ERROR';
}
