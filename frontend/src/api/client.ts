import { getApiBaseUrl, verifyManualServer, getManualOverride, clearManualOverride } from '../services/discovery';

let _resolvedBaseUrl: string | null = null;
let _initPromise: Promise<string> | null = null;
let _initError: Error | null = null;

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
  _resolvedBaseUrl = baseUrl;
  _initError = null;
  return { baseUrl, identity: verified.identity };
}

function errorText(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (detail == null) return fallback;
  try { return JSON.stringify(detail); } catch { return fallback; }
}

const REQUEST_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 15000);

export type LoginResponse = {
  access_token: string; token_type: string; expires_at: string; user_id: string;
  username: string; display_name: string; role: string; branch_id: string; must_change_password: boolean;
};

export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const baseUrl = await resolveBaseUrl();
  assertServerConfigured(baseUrl);
  const token = localStorage.getItem('ltpos_token');
  const headers = new Headers(options.headers);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const controller = options.signal ? null : new AbortController();
  const timer = controller ? window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS) : null;
  try {
    const res = await fetch(`${baseUrl}${path}`, {...options, headers, signal: options.signal ?? controller?.signal});
    const text = await res.text();
    let body: any = {};
    if (text) {
      try { body = JSON.parse(text); }
      catch {
        if (res.ok) throw new Error(`Unexpected non-JSON reply from ${baseUrl}${path}. Check the server address and that the POS server is running.`);
      }
    }
    if (res.status === 401) {
      localStorage.removeItem('ltpos_token');
      localStorage.removeItem('ltpos_user');
      window.dispatchEvent(new CustomEvent('ltpos:session-expired'));
    }
    if (!res.ok) throw new Error(errorText(body?.detail, `HTTP ${res.status}`));
    return body as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('Request timed out. Please check the LAN connection and try again.');
    if (error instanceof TypeError) throw new Error(`Cannot reach the POS server at ${baseUrl}. Check the server laptop is on, the IP is correct and the firewall allows port 8000.`);
    throw error;
  } finally {
    if (timer !== null) window.clearTimeout(timer);
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
  localStorage.setItem('ltpos_token', result.access_token);
  localStorage.setItem('ltpos_user', JSON.stringify(result));
  return result;
}

export async function serverLogout(): Promise<void> {
  try { await api('/auth/logout', {method:'POST'}); } finally { logout(); }
}

export function logout() { localStorage.removeItem('ltpos_token'); localStorage.removeItem('ltpos_user'); }
export function currentUser(): LoginResponse | null {
  try {
    const raw = localStorage.getItem('ltpos_user');
    if (!raw) return null;
    const u = JSON.parse(raw);
    if (u && typeof u.role === 'string' && typeof u.username === 'string' && localStorage.getItem('ltpos_token')) return u as LoginResponse;
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