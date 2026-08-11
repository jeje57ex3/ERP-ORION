import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  base: '/lunea/',
  resolve: {
    alias: {
      '@shared': resolve(__dirname, '../shared'),
    },
  },
  server: {
    port: 5174,
    allowedHosts: ['lunea.elysiums.fr', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': { target: 'http://localhost:9000', changeOrigin: true },
      '/static': { target: 'http://localhost:9000', changeOrigin: true },
    },
  },
  build: {
    outDir: '../../apps/lunea/static/lunea/dist',
    emptyOutDir: true,
  },
})
