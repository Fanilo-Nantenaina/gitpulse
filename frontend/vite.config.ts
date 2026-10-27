import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig } from 'vite';

// The build is written into the Python package so `pip install` ships the UI
// without needing Node. `npm run dev` proxies the API to a running
// `gitpulse web` (default port 8420).
export default defineConfig({
  plugins: [svelte()],
  base: '/static/',
  build: {
    outDir: '../gitpulse/web/static',
    emptyOutDir: true,
    assetsDir: 'assets',
    target: 'es2022',
  },
  server: {
    proxy: { '/api': { target: 'http://127.0.0.1:8420', changeOrigin: true } },
  },
});
