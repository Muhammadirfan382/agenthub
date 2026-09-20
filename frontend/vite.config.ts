import { fileURLToPath, URL } from 'node:url';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { loadEnv, type Plugin } from 'vite';
import { defineConfig } from 'vitest/config';
import { contentSecurityPolicy } from './src/config/contentSecurityPolicy.ts';

// Development services bind to the loopback interface only. The backend is
// reached through the dev proxy, so the API needs no CORS configuration.
const BACKEND_DEV_URL = 'http://127.0.0.1:8000';

/** Adds the Content-Security-Policy to the built index.html. Build only: see the policy's notes. */
function cspMetaTag(apiBaseUrl: string | undefined): Plugin {
  return {
    name: 'agenthub-content-security-policy',
    apply: 'build',
    transformIndexHtml: {
      order: 'post',
      handler: (html) =>
        html.replace(
          '<meta charset="UTF-8" />',
          `<meta charset="UTF-8" />
    <meta http-equiv="Content-Security-Policy" content="${contentSecurityPolicy(apiBaseUrl)}" />`,
        ),
    },
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), cspMetaTag(loadEnv(mode, process.cwd(), 'VITE_').VITE_API_BASE_URL)],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: BACKEND_DEV_URL },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rolldownOptions: {
      output: {
        // Stable vendor chunks cache well across deploys and keep the entry small.
        codeSplitting: {
          groups: [
            { name: 'vendor-react', test: /node_modules[\\/](react|react-dom|scheduler|react-router)[\\/]/ },
            { name: 'vendor-data', test: /node_modules[\\/](@tanstack|zustand)[\\/]/ },
            { name: 'vendor-forms', test: /node_modules[\\/](react-hook-form|@hookform|zod)[\\/]/ },
            { name: 'vendor-icons', test: /node_modules[\\/]lucide-react[\\/]/ },
          ],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    testTimeout: 30000,
    // Each file gets its own jsdom; spawning one per core made slow machines
    // flake on timing rather than on behaviour.
    maxWorkers: 4,
  },
}));
