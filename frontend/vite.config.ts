import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev server only: VITE_API_BASE defaults to the relative /api/v1, so forward API and discovery
// calls to the local POS backend (override the target with VITE_PROXY_TARGET).
const target = process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': target, '/discovery': target, '/health': target } },
});
