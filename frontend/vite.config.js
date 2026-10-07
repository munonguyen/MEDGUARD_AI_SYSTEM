import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';

export default defineConfig({
  plugins: [react()],
  base: '/static/',
  server: {
    port: 5173,
    proxy: {
      // Preserve the browser-facing Host so backend Origin/CSRF checks agree.
      '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: false },
      '/metrics': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    },
  },
  build: {
    outDir: resolve(import.meta.dirname, '../app/static'),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'app.js',
        assetFileNames: (assetInfo) =>
          assetInfo.name?.endsWith('.css') ? 'style.css' : 'assets/[name]-[hash][extname]',
      },
    },
  },
});
