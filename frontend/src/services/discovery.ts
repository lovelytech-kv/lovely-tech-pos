/** Lovely Tech POS LAN server discovery resolver.

This module implements the client-side discovery + HTTP identity verification flow:
1. Invoke Tauri command `discover_lovely_pos_servers` to find mDNS-advertised servers
2. For each candidate, call GET /discovery/info to verify identity
3. Return a verified base URL or throw a descriptive error
*/

import { invoke } from '@tauri-apps/api/core';

const DISCOVERY_HTTP_TIMEOUT_MS = Number(import.meta.env.VITE_DISCOVERY_TIMEOUT_MS ?? 5000);
const REQUIRED_TXT_FIELDS = ['product', 'instance_id', 'protocol_version', 'api_version', 'app_version', 'branch_code'] as const;

export interface DiscoveredServer {
  service_name: string;
  hostname: string;
  addresses: string[];
  port: number;
  txt_records: Record<string, string>;
}

export interface DiscoveryInfo {
  product: string;
  protocol_version: string;
  api_version: string;
  app_version: string;
  instance_id: string;
  branch_code: string;
}

export interface ResolvedServer {
  baseUrl: string;
  identity: DiscoveryInfo;
}

export interface DiscoveryError extends Error {
  code: 'NO_SERVERS' | 'ALL_UNREACHABLE' | 'IDENTITY_MISMATCH' | 'TIMEOUT' | 'NO_TAURI' | 'INVALID_RESPONSE';
  candidatesTried: number;
}

export function isTauriEnvironment(): boolean {
  return typeof window !== 'undefined' &&
    (window.location.protocol === 'tauri:' || window.location.hostname.endsWith('tauri.localhost'));
}

function getDiscoveryEndpoint(baseUrl: string): string {
  const url = new URL(baseUrl);
  url.pathname = '/discovery/info';
  return url.toString();
}

export function buildBaseUrl(address: string, port: number): string {
  return `http://${address}:${port}/api/v1`;
}

export function identityMatches(txt: Record<string, string>, info: DiscoveryInfo): boolean {
  return (
    txt.product === info.product &&
    txt.instance_id === info.instance_id &&
    txt.protocol_version === info.protocol_version &&
    txt.api_version === info.api_version &&
    txt.app_version === info.app_version &&
    txt.branch_code === info.branch_code
  );
}

export function hasRequiredTxtFields(txt: Record<string, string>): boolean {
  return REQUIRED_TXT_FIELDS.every(field => field in txt && txt[field] !== '');
}

async function fetchDiscoveryInfo(baseUrl: string, timeoutMs: number): Promise<DiscoveryInfo> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(getDiscoveryEndpoint(baseUrl), {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    return {
      product: data.product,
      protocol_version: data.protocol_version,
      api_version: data.api_version,
      app_version: data.app_version,
      instance_id: data.instance_id,
      branch_code: data.branch_code,
    };
  } finally {
    clearTimeout(timer);
  }
}

export async function resolveServer(): Promise<ResolvedServer> {
  if (!isTauriEnvironment()) {
    const error = new Error('Discovery resolver only runs in Tauri environment') as DiscoveryError;
    error.code = 'NO_TAURI';
    error.candidatesTried = 0;
    throw error;
  }

  let discovered: DiscoveredServer[];
  try {
    discovered = await invoke('discover_lovely_pos_servers');
  } catch (err) {
    const error = new Error(`mDNS discovery failed: ${err}`) as DiscoveryError;
    error.code = 'TIMEOUT';
    error.candidatesTried = 0;
    throw error;
  }

  if (discovered.length === 0) {
    const error = new Error('No Lovely Tech POS servers found on the LAN') as DiscoveryError;
    error.code = 'NO_SERVERS';
    error.candidatesTried = 0;
    throw error;
  }

  const candidates = discovered.filter(s => hasRequiredTxtFields(s.txt_records));
  if (candidates.length === 0) {
    const error = new Error('Discovered services missing required identity fields') as DiscoveryError;
    error.code = 'INVALID_RESPONSE';
    error.candidatesTried = discovered.length;
    throw error;
  }

  let lastError: Error | null = null;
  let lastErrorWasIdentityMismatch = false;
  let verified: ResolvedServer | null = null;

  for (const server of candidates) {
    for (const address of server.addresses) {
      const baseUrl = buildBaseUrl(address, server.port);
      try {
        const info = await fetchDiscoveryInfo(baseUrl, DISCOVERY_HTTP_TIMEOUT_MS);
        if (!identityMatches(server.txt_records, info)) {
          lastError = new Error(`Identity mismatch for ${baseUrl}: advertised TXT does not match /discovery/info`);
          lastErrorWasIdentityMismatch = true;
          continue;
        }
        verified = { baseUrl, identity: info };
        break;
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        lastErrorWasIdentityMismatch = false;
      }
    }
    if (verified) break;
  }

  if (!verified) {
    const error = new Error(
      `None of ${candidates.length} discovered server(s) could be verified. ` +
      `Last error: ${lastError?.message ?? 'unknown'}`
    ) as DiscoveryError;
    error.code = lastErrorWasIdentityMismatch ? 'IDENTITY_MISMATCH' : 'ALL_UNREACHABLE';
    error.candidatesTried = candidates.length;
    throw error;
  }

  return verified;
}

export async function getApiBaseUrl(): Promise<string> {
  const apiBase = import.meta.env.VITE_API_BASE;
  if (apiBase && !apiBase.startsWith('/')) {
    return apiBase.replace(/\/$/, '');
  }

  if (!isTauriEnvironment()) {
    return '/api/v1';
  }

  try {
    const resolved = await resolveServer();
    return resolved.baseUrl;
  } catch (err) {
    const error = err as DiscoveryError;
    if (error.code === 'NO_TAURI') throw err;
    console.warn('Automatic LAN discovery failed, falling back to manual configuration:', error.message);
    throw new Error(
      'Automatic server discovery failed. ' +
      'Please ensure the POS server is running on the same LAN, ' +
      'or configure VITE_API_BASE manually during build.'
    );
  }
}

/** localStorage key for the Admin manual server override. */
export const MANUAL_OVERRIDE_KEY = 'ltpos_manual_api_base';

/** Returns the persisted manual server override, or null when none is set. */
export function getManualOverride(): string | null {
  try {
    return localStorage.getItem(MANUAL_OVERRIDE_KEY);
  } catch {
    return null;
  }
}

/** Persists a verified manual server base URL. */
export function setManualOverride(baseUrl: string): void {
  localStorage.setItem(MANUAL_OVERRIDE_KEY, baseUrl);
}

/** Removes the persisted manual server override. */
export function clearManualOverride(): void {
  localStorage.removeItem(MANUAL_OVERRIDE_KEY);
}

const REQUIRED_IDENTITY_FIELDS = [
  'product', 'instance_id', 'protocol_version', 'api_version', 'app_version', 'branch_code',
] as const;

function hasAllIdentityFields(info: Partial<DiscoveryInfo>): info is DiscoveryInfo {
  return REQUIRED_IDENTITY_FIELDS.every(field => typeof info[field] === 'string' && (info[field] as string) !== '');
}

/**
 * Verifies a manually entered server candidate.
 *
 * Accepts either a full URL (http://host:port) or a host[:port] string.
 * The candidate is verified through GET /discovery/info and must expose the
 * same required identity fields used by automatic discovery. A reachable
 * HTTP endpoint that does not identify itself as a Lovely Tech POS server is
 * rejected - we do not accept arbitrary port 8000 responses merely because
 * HTTP answered.
 */
export async function verifyManualServer(input: string): Promise<ResolvedServer> {
  const trimmed = input.trim();
  if (!trimmed) throw new Error('Enter a server address or host:port.');

  let baseUrl: string;
  try {
    if (/^https?:\/\//i.test(trimmed)) {
      const u = new URL(trimmed);
      if (u.protocol !== 'http:' && u.protocol !== 'https:') {
        throw new Error('Only http and https server URLs are allowed.');
      }
      // Keep only origin + /api/v1; ignore any path the user supplied.
      baseUrl = `${u.origin}/api/v1`;
    } else {
      const parts = trimmed.split(':');
      const host = parts[0]?.trim();
      const portRaw = parts.length > 1 ? parts[1].trim() : '';
      if (!host) throw new Error('Enter a valid host or host:port.');
      const port = portRaw ? parseInt(portRaw, 10) : 8000;
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        throw new Error('Port must be a number between 1 and 65535.');
      }
      baseUrl = `http://${host}:${port}/api/v1`;
    }
  } catch (err) {
    if (err instanceof Error && (err.message.startsWith('Only') || err.message.startsWith('Enter') || err.message.startsWith('Port'))) {
      throw err;
    }
    throw new Error('Enter a valid server URL (http://host:8000) or host:port (192.168.1.50:8000).');
  }

  const info = await fetchDiscoveryInfo(baseUrl, DISCOVERY_HTTP_TIMEOUT_MS);
  if (!hasAllIdentityFields(info)) {
    throw new Error(
      `Manual server at ${baseUrl} is not a Lovely Tech POS server: ` +
      'the required identity fields (product, instance_id, protocol_version, api_version, app_version, branch_code) are missing.'
    );
  }

  return { baseUrl, identity: info };
}