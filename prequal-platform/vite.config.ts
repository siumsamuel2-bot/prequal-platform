import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// MID-695: env-driven build knobs so the same codebase builds correctly on
// every static host:
//   - VITE_BASE_PATH: Vite `base` for subpath hosts (GitHub Pages serves the
//     project site under /prequal-platform/). Defaults to '/' so root hosts
//     (Vercel, Render static) are unaffected.
//   - VITE_API_URL: absolute API origin for hosts with no /api proxy
//     (GitHub Pages). Injected at build time as the unique identifier
//     __API_URL__ (see src/api/client.ts); empty string keeps the SPA on the
//     same-origin '/api' default.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react()],
    base: env.VITE_BASE_PATH || '/',
    define: {
      __API_URL__: JSON.stringify(env.VITE_API_URL || ''),
    },
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
    },
  };
});
