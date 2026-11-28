import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev server only: VITE_API_BASE defaults to the relative /api/v1, so forward API and discovery
// calls to the local POS backend (override the target with VITE_PROXY_TARGET).
const target = process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': target, '/discovery': target, '/health': target } },
  build: {
    // Rollup 4.64.0's tree-shaker does not terminate on react-dom 19.1.1 here:
    // the build sticks at "transforming..." with unbounded memory growth. A
    // two-line entry importing only `react-dom/client` reproduces it, so it is
    // a toolchain issue rather than app code. Disabling tree-shaking costs
    // ~9 kB (+1.4%) on this bundle and keeps `npm run build` deterministic.
    // Revisit after bumping Rollup (fixed after 4.64.0 upstream).
    rollupOptions: { treeshake: false },
  },
});
