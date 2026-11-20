import { getApiBaseUrl, verifyManualServer, getManualOverride, setManualOverride, clearManualOverride } from '../services/discovery';

let _resolvedBaseUrl: string | null = null;
let _initPromise: Promise<string> | null = null;
let _initError: Error | null = null;

// H16 — keep the bearer token in memory; sessionStorage is only a page-reload fallback.
let _token: string | null = null;

function readStoredToken(): string | null {
  if (_token !== null) return _token;
  try {
    const stored = sessionStorage.getItem('ltpos_token');
    if (stored) _token = stored;
  } catch { /* storage unavailable */ }
  return _token;
}

function clearStoredToken(): void {
  _token = null;
  try { sessionStorage.removeItem('ltpos_token'); } catch { /* storage unavailable */ }
  localStorage.removeItem('ltpos_token');
}

// Chunk 13b — CLIENT mode: business APIs must go to remote server
let _machineInfoCache: { role: string; serverUrl: string | null } | null = null;
// M15 — cache the in-flight lookup so concurrent callers share one request.
let _machineInfoPromise: Promise<{ role: string; serverUrl: string | null }> | null = null;

export function invalidateMachineInfoCache() {
  _machineInfoCache = null;
  _machineInfoPromise = null;
}

// M14 — identity lookup must not hang business API calls on a stalled LAN.
const MACHINE_IDENTITY_TIMEOUT_MS = Number(import.meta.env.VITE_IDENTITY_TIMEOUT_MS ?? 3000);

async function loadLocalMachineInfo(): Promise<{ role: string; serverUrl: string | null }> {
  const localBase = await resolveBaseUrl();
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), MACHINE_IDENTITY_TIMEOUT_MS);
  try {
    let res: Response;
    try {
      res = await fetch(`${localBase}/machine/identity`, { cache: 'no-store', signal: controller.signal });
    } catch (err) {
      if (controller.signal.aborted) {
        throw new Error('Cannot reach server — machine identity check timed out. Check LAN');
      }
      // H14 — never assume SERVER on a failed identity lookup: a CLIENT laptop
      // would silently write to its own local database.
      throw new Error('Cannot reach server — check LAN');
    }
    if (!res.ok) {
      throw new Error(`Cannot reach server — machine identity check failed (HTTP ${res.status})`);
    }
    let data: any;
    try {
      data = await res.json();
    } catch {
      if (controller.signal.aborted) {
        throw new Error('Cannot reach server — machine identity check timed out. Check LAN');
      }
      throw new Error('Cannot reach server — machine identity reply was not valid JSON');
    }
    const role = String(data.machine_role || data.role || '').toUpperCase();
    if (role !== 'SERVER' && role !== 'CLIENT') {
      throw new Error('Cannot reach server — machine identity reply was invalid');
    }
    const serverUrl = data.server_url ? String(data.server_url).replace(/\/$/, '') : null;
    if (role === 'CLIENT' && !serverUrl) {
      throw new Error('Cannot reach server — this CLIENT machine has no server URL configured');
    }
    // Only a confirmed 200 with a valid role is cached (by the caller).
    return { role, serverUrl };
  } finally {
    window.clearTimeout(timer);
  }
}

async function getLocalMachineInfo(): Promise<{ role: string; serverUrl: string | null }> {
  if (_machineInfoCache) return _machineInfoCache;
  if (_machineInfoPromise) return _machineInfoPromise;
  const promise = loadLocalMachineInfo()
    .then((info) => {
      if (_machineInfoPromise === promise) _machineInfoCache = info;
      return info;
    })
    .finally(() => {
      if (_machineInfoPromise === promise) _machineInfoPromise = null;
    });
  _machineInfoPromise = promise;
  return promise;
}

function assertServerConfigured(baseUrl: string) {
  const relative = baseUrl.startsWith('/');
  const desktopShell = typeof window !== 'undefined' &&
    (window.location.protocol === 'tauri:' || window.location.hostname.endsWith('tauri.localhost'));
  if (relative && desktopShell) {
    throw new Error('This app was built without a server address. Automatic discovery failed or no server found on LAN.');
  }
}

async function resolveBaseUrl(): Promise<string> {
  if (_resolvedBaseUrl) return _resolvedBaseUrl;
  if (_initPromise) return _initPromise;

  _initPromise = (async () => {
    try {
      const baseUrl = await getApiBaseUrl();
      _resolvedBaseUrl = baseUrl.replace(/\/$/, '');
      _initError = null;
      return _resolvedBaseUrl;
    } catch (err) {
      _initError = err instanceof Error ? err : new Error(String(err));
      // Fall back to a persisted Admin manual override when automatic discovery fails.
      const override = getManualOverride();
      if (override) {
        _resolvedBaseUrl = override.replace(/\/$/, '');
        _initError = null;
        return _resolvedBaseUrl;
      }
      throw _initError;
    } finally {
      _initPromise = null;
    }
  })();

  return _initPromise;
}

// Chunk 13b — route business APIs to remote server when this machine is CLIENT
async function resolveBaseUrlForPath(path: string): Promise<string> {
  const localBase = await resolveBaseUrl();

  // Local-only endpoints (must hit the local backend)
  const isLocalOnly =
    path.startsWith('/setup/') ||
    path.startsWith('/machine/');

  if (isLocalOnly) return localBase;

  // All other paths → if CLIENT, send to remote server URL.
  // H14 — identity failures propagate: never fall back to the local backend.
  const info = await getLocalMachineInfo();
  if (info.role === 'CLIENT' && info.serverUrl) {
    const remote = info.serverUrl.replace(/\/$/, '');
    // DB stores server_url WITHOUT /api/v1 (e.g. http://host:8001)
    // Local base uses /api/v1 (dev proxy or http://host:8000/api/v1)
    // So we must append it for the remote path too.
    return remote.endsWith('/api/v1') ? remote : `${remote}/api/v1`;
  }

  return localBase;
}

export function getApiBaseUrlSync(): string | null {
  return _resolvedBaseUrl;
}

export function getApiBaseUrlOrThrow(): string {
  if (_resolvedBaseUrl) return _resolvedBaseUrl;
  if (_initError) throw _initError;
  throw new Error('API base URL not yet resolved. Call ensureApiBaseResolved() first.');
}

export async function ensureApiBaseResolved(): Promise<string> {
  return resolveBaseUrl();
}

export async function resetApiBaseResolution(): Promise<void> {
  _resolvedBaseUrl = null;
  _initError = null;
  invalidateMachineInfoCache();
  if (_initPromise) {
    await _initPromise.catch(() => {});
  }
  await resolveBaseUrl();
}
/**
 * Verifies a manually entered server candidate through /discovery/info and
 * persists it as the Admin manual override. The candidate must expose the
 * required identity fields; a reachable HTTP endpoint alone is not enough.
 */
export async function configureManualServer(input: string): Promise<{ baseUrl: string; identity: any }> {
  const verified = await verifyManualServer(input);
  const baseUrl = verified.baseUrl.replace(/\/$/, '');
  // M8 — persist the verified override so it survives an app restart.
  setManualOverride(baseUrl);
  _resolvedBaseUrl = baseUrl;
  _initError = null;
  // The manual server may have a different machine role; re-read identity.
  invalidateMachineInfoCache();
  return { baseUrl, identity: verified.identity };
}

function errorText(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (detail == null) return fallback;
  // FastAPI/Pydantic 422: detail is an array of { loc, msg, type }.
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { loc?: unknown; msg?: unknown };
    if (first && typeof first.msg === 'string') {
      const loc = Array.isArray(first.loc) ? first.loc.slice(1).join('.') : '';
      return loc ? `${loc}: ${first.msg}` : first.msg;
    }
  }
  try { return JSON.stringify(detail); } catch { return fallback; }
}

const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 15000);

export type LoginResponse = {
  access_token: string; token_type: string; expires_at: string; user_id: string;
  username: string; display_name: string; role: string; branch_id: string; must_change_password: boolean;
};

export type ApiOptions = RequestInit & { timeoutMs?: number; skipAuthLogout?: boolean };

export async function api<T = any>(path: string, options: ApiOptions = {}): Promise<T> {
  const { timeoutMs = REQUEST_TIMEOUT_MS, skipAuthLogout = false, ...fetchOptions } = options;
  const baseUrl = await resolveBaseUrlForPath(path);
  assertServerConfigured(baseUrl);
  const token = readStoredToken();
  const headers = new Headers(fetchOptions.headers);
  const isFormData = fetchOptions.body instanceof FormData;
  if (fetchOptions.body && !isFormData && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  // H17 — the timeout is always armed, even when the caller supplies a signal.
  const timeoutController = new AbortController();
  const timer = window.setTimeout(() => timeoutController.abort(), timeoutMs);
  const callerSignal = fetchOptions.signal;
  let signal: AbortSignal = timeoutController.signal;
  let detachAbortListeners: (() => void) | null = null;
  if (callerSignal) {
    if (typeof AbortSignal.any === 'function') {
      signal = AbortSignal.any([callerSignal, timeoutController.signal]);
    } else {
      const merged = new AbortController();
      const abortMerged = () => merged.abort();
      if (callerSignal.aborted || timeoutController.signal.aborted) {
        merged.abort();
      } else {
        callerSignal.addEventListener('abort', abortMerged, { once: true });
        timeoutController.signal.addEventListener('abort', abortMerged, { once: true });
        detachAbortListeners = () => {
          callerSignal.removeEventListener('abort', abortMerged);
          timeoutController.signal.removeEventListener('abort', abortMerged);
        };
      }
      signal = merged.signal;
    }
  }
  try {
    const res = await fetch(`${baseUrl}${path}`, {...fetchOptions, headers, signal});
    const text = await res.text();
    let body: any = {};
    if (text) {
      try { body = JSON.parse(text); }
      catch {
        if (res.ok) throw new Error(`Unexpected non-JSON reply from ${baseUrl}${path}. Check the server address and that the POS server is running.`);
      }
    }
    if (res.status === 401 && !skipAuthLogout) {
      clearStoredToken();
      localStorage.removeItem('ltpos_user');
      window.dispatchEvent(new CustomEvent('ltpos:session-expired'));
    }
    if (!res.ok) throw new Error(errorText(body?.detail, `HTTP ${res.status}`));
    return body as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      // Distinguish our timeout from a caller-initiated abort.
      if (timeoutController.signal.aborted) throw new Error('Request timed out. Please check the LAN connection and try again.');
      throw error;
    }
    if (error instanceof TypeError) throw new Error(`Cannot reach the POS server at ${baseUrl}. Check the server laptop is on, the IP is correct and the firewall allows port 8000.`);
    throw error;
  } finally {
    window.clearTimeout(timer);
    detachAbortListeners?.();
  }
}

export async function checkServerHealth(): Promise<{ status: string; service?: string; version?: string }> {
  const baseUrl = await resolveBaseUrl();
  assertServerConfigured(baseUrl);
  const res = await fetch(`${baseUrl}/health`, { method: 'GET', cache: 'no-store' });
  if (!res.ok) throw new Error(`Health check failed (HTTP ${res.status})`);
  const body = await res.json();
  if (body?.status !== 'ok') throw new Error('POS server health check returned an unexpected status.');
  return body;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const result = await api<LoginResponse>('/auth/login', {method:'POST', body:JSON.stringify({username,password})});
  if (!result || !result.access_token || typeof result.role !== 'string') {
    throw new Error('Login reply was incomplete. Check the server address and that client/server versions match.');
  }
  _token = result.access_token;
  sessionStorage.setItem('ltpos_token', result.access_token);
  localStorage.removeItem('ltpos_token');
  // L2: never duplicate the bearer token inside the cached user object.
  localStorage.setItem('ltpos_user', JSON.stringify({ ...result, access_token: '' }));
  return result;
}

export async function serverLogout(): Promise<void> {
  try { await api('/auth/logout', {method:'POST'}); } finally { logout(); }
}

export function logout() {
  clearStoredToken();
  localStorage.removeItem('ltpos_user');
}
export function currentUser(): LoginResponse | null {
  try {
    const raw = localStorage.getItem('ltpos_user');
    if (!raw) return null;
    const u = JSON.parse(raw);
    if (u && typeof u.role === 'string' && typeof u.username === 'string' && readStoredToken()) return u as LoginResponse;
  } catch { /* corrupt session */ }
  logout();
  return null;
}

// For backward compatibility with Login.tsx display - returns resolved URL or the configured/relative base
export const API_BASE_URL = ((): string => {
  const envBase = import.meta.env.VITE_API_BASE;
  if (envBase && !envBase.startsWith('/')) return envBase.replace(/\/$/, '');
  return '/api/v1';
})();