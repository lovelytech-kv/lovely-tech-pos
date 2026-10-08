/** Focused tests for the LAN discovery resolver. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { resolveServer, getApiBaseUrl, isTauriEnvironment, hasRequiredTxtFields, identityMatches, buildBaseUrl, verifyManualServer, isServerSetupState, resolveApiBase } from './discovery';
// Mock Tauri invoke
vi.mock('@tauri-apps/api/core', () => ({
    invoke: vi.fn(),
}));
import { invoke } from '@tauri-apps/api/core';
const mockDiscoveredServers = [
    {
        service_name: 'Lovely Tech POS Server._lovely-tech-pos._tcp.local.',
        hostname: 'server.local.',
        addresses: ['192.168.1.100', 'fe80::1'],
        port: 8000,
        txt_records: {
            product: 'Lovely Tech POS System',
            instance_id: 'abcdef01-2345-6789-abcd-ef0123456789',
            protocol_version: '1.0.0',
            api_version: '1',
            app_version: '0.4.0',
            branch_code: 'SHOP-A',
            port: '8000',
        },
    },
];
const mockDiscoveryInfo = {
    product: 'Lovely Tech POS System',
    protocol_version: '1.0.0',
    api_version: '1',
    app_version: '0.4.0',
    instance_id: 'abcdef01-2345-6789-abcd-ef0123456789',
    branch_code: 'SHOP-A',
    setup_state: 'READY',
};
describe('discovery resolver', () => {
    let originalLocation;
    let originalFetch;
    let originalEnv;
    // Capture the real fetch once before any tests run
    const realFetch = globalThis.fetch;
    beforeEach(() => {
        vi.clearAllMocks();
        originalLocation = window.location;
        originalFetch = realFetch;
        originalEnv = { ...import.meta.env };
        // Reset window location
        Object.defineProperty(window, 'location', {
            value: { protocol: 'https:', hostname: 'localhost' },
            writable: true,
            configurable: true,
        });
        // Ensure fetch is restored to real implementation before each test
        globalThis.fetch = realFetch;
    });
    afterEach(() => {
        Object.defineProperty(window, 'location', { value: originalLocation, writable: true, configurable: true });
        globalThis.fetch = realFetch;
        Object.keys(import.meta.env).forEach(key => delete import.meta.env[key]);
        Object.assign(import.meta.env, originalEnv);
    });
    describe('isTauriEnvironment', () => {
        it('returns true for tauri: protocol', () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            expect(isTauriEnvironment()).toBe(true);
        });
        it('returns true for tauri.localhost hostname', () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'http:', hostname: 'app.tauri.localhost' }, writable: true, configurable: true });
            expect(isTauriEnvironment()).toBe(true);
        });
        it('returns false for regular http', () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'http:', hostname: 'localhost' }, writable: true, configurable: true });
            expect(isTauriEnvironment()).toBe(false);
        });
    });
    describe('hasRequiredTxtFields', () => {
        it('returns true when all required fields present', () => {
            const txt = {
                product: 'Lovely Tech POS System',
                instance_id: 'abc123',
                protocol_version: '1.0.0',
                api_version: '1',
                app_version: '0.4.0',
                branch_code: 'MAIN',
            };
            expect(hasRequiredTxtFields(txt)).toBe(true);
        });
        it('returns false when instance_id missing', () => {
            const txt = { product: 'test', protocol_version: '1', api_version: '1', app_version: '1', branch_code: 'A' };
            expect(hasRequiredTxtFields(txt)).toBe(false);
        });
        it('returns false when fields empty', () => {
            const txt = {
                product: 'Lovely Tech POS System',
                instance_id: '',
                protocol_version: '1.0.0',
                api_version: '1',
                app_version: '0.4.0',
                branch_code: 'MAIN',
            };
            expect(hasRequiredTxtFields(txt)).toBe(false);
        });
    });
    describe('identityMatches', () => {
        it('returns true when all fields match', () => {
            const txt = { ...mockDiscoveredServers[0].txt_records };
            expect(identityMatches(txt, mockDiscoveryInfo)).toBe(true);
        });
        it('returns false when instance_id mismatches', () => {
            const txt = { ...mockDiscoveredServers[0].txt_records, instance_id: 'different-id' };
            expect(identityMatches(txt, mockDiscoveryInfo)).toBe(false);
        });
        it('returns false when product mismatches', () => {
            const txt = { ...mockDiscoveredServers[0].txt_records, product: 'Different Product' };
            expect(identityMatches(txt, mockDiscoveryInfo)).toBe(false);
        });
        it('returns false when branch_code mismatches', () => {
            const txt = { ...mockDiscoveredServers[0].txt_records, branch_code: 'SHOP-B' };
            expect(identityMatches(txt, mockDiscoveryInfo)).toBe(false);
        });
    });
    describe('isServerSetupState', () => {
        it('accepts the backend setup_state values', () => {
            expect(isServerSetupState('READY')).toBe(true);
            expect(isServerSetupState('NEW_SHOP_REQUIRED')).toBe(true);
            expect(isServerSetupState('EXISTING_SHOP_REQUIRED')).toBe(true);
        });
        it('rejects unknown or missing setup_state values', () => {
            expect(isServerSetupState('GARBAGE')).toBe(false);
            expect(isServerSetupState('')).toBe(false);
            expect(isServerSetupState(null)).toBe(false);
            expect(isServerSetupState(undefined)).toBe(false);
        });
    });
    describe('setup_state in discovery response', () => {
        it('accepts setup_state from a verified discovery response', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            vi.mocked(invoke).mockResolvedValue(mockDiscoveredServers);
            globalThis.fetch = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockDiscoveryInfo),
            });
            const result = await resolveServer();
            expect(result.identity.setup_state).toBe('READY');
        });
        it('propagates NEW_SHOP_REQUIRED and EXISTING_SHOP_REQUIRED from the discovery response', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            vi.mocked(invoke).mockResolvedValue(mockDiscoveredServers);
            for (const setupState of ['NEW_SHOP_REQUIRED', 'EXISTING_SHOP_REQUIRED']) {
                globalThis.fetch = vi.fn().mockResolvedValue({
                    ok: true,
                    json: () => Promise.resolve({ ...mockDiscoveryInfo, setup_state: setupState }),
                });
                const result = await resolveServer();
                expect(result.identity.setup_state).toBe(setupState);
            }
        });
        it('resolveApiBase returns the verified identity including setup_state', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            vi.mocked(invoke).mockResolvedValue(mockDiscoveredServers);
            globalThis.fetch = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockDiscoveryInfo),
            });
            const resolution = await resolveApiBase();
            expect(resolution.baseUrl).toBe('http://192.168.1.100:8000/api/v1');
            expect(resolution.identity).not.toBeNull();
            expect(resolution.identity.setup_state).toBe('READY');
            expect(resolution.identity.instance_id).toBe('abcdef01-2345-6789-abcd-ef0123456789');
        });
        it('resolveApiBase returns no identity for a build-configured base URL', async () => {
            vi.stubEnv('VITE_API_BASE', 'http://configured-server:8000/api/v1');
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            const resolution = await resolveApiBase();
            expect(resolution.baseUrl).toBe('http://configured-server:8000/api/v1');
            expect(resolution.identity).toBeNull();
        });
    });
    describe('verifyManualServer setup_state validation', () => {
        it('accepts a manually entered server and returns its setup_state', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            globalThis.fetch = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ ...mockDiscoveryInfo, setup_state: 'NEW_SHOP_REQUIRED' }),
            });
            const result = await verifyManualServer('192.168.1.50:8000');
            expect(result.baseUrl).toBe('http://192.168.1.50:8000/api/v1');
            expect(result.identity.setup_state).toBe('NEW_SHOP_REQUIRED');
        });
        it('rejects a manual server whose /discovery/info lacks setup_state', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            const { setup_state: _omit, ...infoWithoutSetupState } = mockDiscoveryInfo;
            globalThis.fetch = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(infoWithoutSetupState),
            });
            await expect(verifyManualServer('http://192.168.1.50:8000'))
                .rejects.toThrow(/setup_state/);
        });
        it('rejects a manual server with an empty setup_state', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            globalThis.fetch = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve({ ...mockDiscoveryInfo, setup_state: '' }),
            });
            await expect(verifyManualServer('http://192.168.1.50:8000'))
                .rejects.toThrow(/not a Lovely Tech POS server/);
        });
    });
    describe('buildBaseUrl', () => {
        it('constructs correct base URL from address and port', () => {
            expect(buildBaseUrl('192.168.1.100', 8000)).toBe('http://192.168.1.100:8000/api/v1');
            expect(buildBaseUrl('10.0.0.5', 9443)).toBe('http://10.0.0.5:9443/api/v1');
        });
    });
    describe('resolveServer', () => {
        it('throws NO_TAURI in non-Tauri environment', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'http:', hostname: 'localhost' }, writable: true, configurable: true });
            const promise = resolveServer();
            await expect(promise).rejects.toMatchObject({ code: 'NO_TAURI', candidatesTried: 0 });
        });
        it('returns verified server when discovery succeeds and identity matches', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            vi.mocked(invoke).mockResolvedValue(mockDiscoveredServers);
            globalThis.fetch = vi.fn().mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(mockDiscoveryInfo),
            });
            const result = await resolveServer();
            expect(result).toEqual({
                baseUrl: 'http://192.168.1.100:8000/api/v1',
                identity: mockDiscoveryInfo,
            });
            expect(invoke).toHaveBeenCalledWith('discover_lovely_pos_servers');
        });
        it('throws NO_SERVERS when no services discovered', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            vi.mocked(invoke).mockResolvedValue([]);
            const promise = resolveServer();
            await expect(promise).rejects.toMatchObject({ code: 'NO_SERVERS', candidatesTried: 0 });
        });
        it('throws INVALID_RESPONSE when discovered services lack required TXT fields', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            vi.mocked(invoke).mockResolvedValue([
                { ...mockDiscoveredServers[0], txt_records: { product: 'test' } },
            ]);
            const promise = resolveServer();
            await expect(promise).rejects.toMatchObject({ code: 'INVALID_RESPONSE', candidatesTried: 1 });
        });
        it('throws IDENTITY_MISMATCH when TXT does not match /discovery/info', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            vi.mocked(invoke).mockResolvedValue(mockDiscoveredServers);
            const mismatchedInfo = { ...mockDiscoveryInfo, instance_id: 'different-instance-id' };
            const responseMock = {
                ok: true,
                json: () => Promise.resolve(mismatchedInfo),
            };
            const fetchMock = vi.fn().mockResolvedValue(responseMock);
            globalThis.fetch = fetchMock;
            const promise = resolveServer();
            await expect(promise).rejects.toMatchObject({ code: 'IDENTITY_MISMATCH', candidatesTried: 1 });
        });
        it('skips unreachable candidates and tries next address', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            const serverWithTwoAddresses = {
                ...mockDiscoveredServers[0],
                addresses: ['192.168.1.100', '192.168.1.101'],
            };
            vi.mocked(invoke).mockResolvedValue([serverWithTwoAddresses]);
            let callCount = 0;
            globalThis.fetch = vi.fn().mockImplementation(() => {
                callCount++;
                if (callCount === 1) {
                    return Promise.reject(new Error('Network error'));
                }
                return Promise.resolve({ ok: true, json: () => Promise.resolve(mockDiscoveryInfo) });
            });
            const result = await resolveServer();
            expect(result.baseUrl).toBe('http://192.168.1.101:8000/api/v1');
            expect(callCount).toBe(2);
        });
        it('throws ALL_UNREACHABLE when all candidates fail HTTP', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            vi.mocked(invoke).mockResolvedValue(mockDiscoveredServers);
            globalThis.fetch = vi.fn().mockRejectedValue(new Error('Connection refused'));
            const promise = resolveServer();
            await expect(promise).rejects.toMatchObject({ code: 'ALL_UNREACHABLE', candidatesTried: 1 });
        });
        it('prefers first verified server when multiple genuine servers exist', async () => {
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            const server1 = { ...mockDiscoveredServers[0], addresses: ['192.168.1.100'], txt_records: { ...mockDiscoveredServers[0].txt_records, instance_id: 'server-1' } };
            const server2 = { ...mockDiscoveredServers[0], addresses: ['192.168.1.101'], txt_records: { ...mockDiscoveredServers[0].txt_records, instance_id: 'server-2' } };
            const info1 = { ...mockDiscoveryInfo, instance_id: 'server-1' };
            const info2 = { ...mockDiscoveryInfo, instance_id: 'server-2' };
            vi.mocked(invoke).mockResolvedValue([server1, server2]);
            globalThis.fetch = vi.fn()
                .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(info1) })
                .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(info2) });
            const result = await resolveServer();
            expect(result.baseUrl).toBe('http://192.168.1.100:8000/api/v1');
            expect(result.identity.instance_id).toBe('server-1');
        });
    });
    describe('getApiBaseUrl', () => {
        it('returns VITE_API_BASE when set and absolute', async () => {
            vi.stubEnv('VITE_API_BASE', 'http://configured-server:8000/api/v1');
            Object.defineProperty(window, 'location', { value: { protocol: 'http:', hostname: 'localhost' }, writable: true, configurable: true });
            const base = await getApiBaseUrl();
            expect(base).toBe('http://configured-server:8000/api/v1');
        });
        it('returns relative path for non-Tauri dev', async () => {
            vi.stubEnv('VITE_API_BASE', '/api/v1');
            Object.defineProperty(window, 'location', { value: { protocol: 'http:', hostname: 'localhost' }, writable: true, configurable: true });
            const base = await getApiBaseUrl();
            expect(base).toBe('/api/v1');
        });
        it('throws when Tauri discovery fails and no manual base', async () => {
            vi.stubEnv('VITE_API_BASE', '/api/v1');
            Object.defineProperty(window, 'location', { value: { protocol: 'tauri:', hostname: 'localhost' }, writable: true, configurable: true });
            vi.mocked(invoke).mockResolvedValue([]);
            const promise = getApiBaseUrl();
            await expect(promise).rejects.toThrow('Automatic server discovery failed');
        });
    });
});
