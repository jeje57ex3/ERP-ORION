import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
    allowedHosts: ['ns.elysiums.fr', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://127.0.0.1:9000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // dist/ plutot que static/neostructura-site : ce dernier est dans
    // STATICFILES_DIRS, le build passait donc dans collectstatic et son
    // ManifestStaticFilesStorage, qui echoue des qu'un asset reference une
    // ressource qu'il ne sait pas resoudre. Le deploiement copie dist/ vers
    // /opt/orion/neostructura, servi par Nginx (meme convention que les
    // boutiques SIECLE et LUNEA).
    outDir: 'dist',
    emptyOutDir: true,
  },
})
