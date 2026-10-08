import { jsx as _jsx } from "react/jsx-runtime";
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from './test-utils';
import { waitFor } from '@testing-library/dom';
import { AdminManualServerPanel } from './components/AdminManualServerPanel';
import { DiscoveryStatus } from './components/DiscoveryStatus';
import { SettingsPanel } from './features/settings/SettingsPanel';
vi.mock('./api/client', () => ({
    ensureApiBaseResolved: vi.fn(),
    resetApiBaseResolution: vi.fn(),
    configureManualServer: vi.fn(),
}));
import { ensureApiBaseResolved, resetApiBaseResolution, configureManualServer } from './api/client';
const mockDiscoveryInfo = {
    product: 'Lovely Tech POS System',
    protocol_version: '1.0.0',
    api_version: '1',
    app_version: '0.4.0',
    instance_id: 'abcdef01-2345-6789-abcd-ef0123456789',
    branch_code: 'SHOP-A',
};
describe('startup discovery UX', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });
    it('shows loading then continues after discovery success', async () => {
        const mockEnsure = vi.mocked(ensureApiBaseResolved);
        mockEnsure.mockResolvedValue('http://192.168.1.100:8000/api/v1');
        const onReady = vi.fn();
        render(_jsx(DiscoveryStatus, { onReady: onReady, onConfigureManual: vi.fn() }));
        expect(screen.getByText('Discovering POS server')).toBeInTheDocument();
        await waitFor(() => expect(onReady).toHaveBeenCalled());
    });
    it('shows server-not-found state on discovery failure', async () => {
        const mockEnsure = vi.mocked(ensureApiBaseResolved);
        mockEnsure.mockRejectedValue(new Error('No servers found'));
        render(_jsx(DiscoveryStatus, { onReady: vi.fn(), onConfigureManual: vi.fn() }));
        await waitFor(() => expect(screen.getByText('POS server not found')).toBeInTheDocument());
        expect(screen.getByText('Retry Discovery')).toBeInTheDocument();
    });
    it('retry resets resolution and retries', async () => {
        const mockEnsure = vi.mocked(ensureApiBaseResolved);
        const mockReset = vi.mocked(resetApiBaseResolution);
        mockEnsure.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce('http://server:8000/api/v1');
        mockReset.mockResolvedValue(undefined);
        const onReady = vi.fn();
        render(_jsx(DiscoveryStatus, { onReady: onReady, onConfigureManual: vi.fn() }));
        await waitFor(() => expect(screen.getByText('POS server not found')).toBeInTheDocument());
        fireEvent.click(screen.getByText('Retry Discovery'));
        await waitFor(() => expect(onReady).toHaveBeenCalled());
        expect(mockReset).toHaveBeenCalled();
    });
});
describe('Admin manual fallback', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });
    it('allows Admin to access manual fallback from Settings', async () => {
        render(_jsx(SettingsPanel, { isAdmin: true }));
        fireEvent.click(screen.getByText('Configure server manually'));
        await waitFor(() => expect(screen.getByText('Manual server configuration')).toBeInTheDocument());
    });
    it('does not expose manual fallback to Cashier', () => {
        render(_jsx(SettingsPanel, { isAdmin: false }));
        expect(screen.queryByText('Configure server manually')).not.toBeInTheDocument();
    });
    it('rejects manual candidate with identity mismatch', async () => {
        const mockConfigure = vi.mocked(configureManualServer);
        mockConfigure.mockRejectedValue(new Error('Manual server at http://x:8000/api/v1 is not a Lovely Tech POS server: the required identity fields (product, instance_id, protocol_version, api_version, app_version, branch_code) are missing.'));
        render(_jsx(AdminManualServerPanel, { onConfigured: vi.fn(), onBack: vi.fn(), onRetry: async () => { } }));
        const input = screen.getByPlaceholderText(/http:\/\/192.168.1.50:8000/);
        fireEvent.change(input, { target: { value: 'http://192.168.1.50:8000' } });
        fireEvent.click(screen.getByText('Connect to server'));
        await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/not a Lovely Tech POS server/));
    });
    it('accepts a valid manually configured server', async () => {
        const mockConfigure = vi.mocked(configureManualServer);
        mockConfigure.mockResolvedValue({ baseUrl: 'http://192.168.1.50:8000/api/v1', identity: mockDiscoveryInfo });
        const onConfigured = vi.fn();
        render(_jsx(AdminManualServerPanel, { onConfigured: onConfigured, onBack: vi.fn(), onRetry: async () => { } }));
        const input = screen.getByPlaceholderText(/http:\/\/192.168.1.50:8000/);
        fireEvent.change(input, { target: { value: 'http://192.168.1.50:8000' } });
        fireEvent.click(screen.getByText('Connect to server'));
        await waitFor(() => expect(onConfigured).toHaveBeenCalled());
    });
});
