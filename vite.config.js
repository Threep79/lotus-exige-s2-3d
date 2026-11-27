import { defineConfig } from 'vite';

export default defineConfig({
  base: '/lotus-exige-s2-3d/',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    chunkSizeWarningLimit: 1200,
  },
});
