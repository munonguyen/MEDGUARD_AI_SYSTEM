import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';

// AudioWorklet and its browser-native modules must retain relative imports.
// Vite's public-file ?import transformation otherwise rejects this dev path.
const audioModules = new Set(['headaudio.mjs', 'headworklet.mjs', 'parameters.mjs', 'training.mjs',
  'processor.mjs', 'ringbuffer.mjs', 'mfcc.mjs', 'vadgate.mjs', 'classifier.mjs']);
const nativeAudioModules = {
  name: 'medguard-native-audio-modules',
  configureServer(server) {
    server.middlewares.use((request, response, next) => {
      const path = (request.url || '').split('?')[0];
      const prefix = '/static/vendor/headaudio/';
      if (!path.startsWith(prefix) || !audioModules.has(path.slice(prefix.length))) return next();
      response.setHeader('Content-Type', 'text/javascript');
      response.end(readFileSync(resolve(import.meta.dirname, 'public/vendor/headaudio', path.slice(prefix.length))));
    });
  },
};

export default defineConfig({
  plugins: [nativeAudioModules, react()],
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
