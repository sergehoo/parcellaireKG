import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Cible du proxy dev : le Django local (runserver ou gunicorn docker).
const DJANGO = process.env.DJANGO_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],

  // En production le build est servi à la racine par le conteneur Nginx.
  base: '/',

  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },

  server: {
    port: 5173,
    proxy: {
      // API JSON + endpoints d'upload / statut + tuiles + login Django.
      '/api': { target: DJANGO, changeOrigin: false },
      '/orthophotos': { target: DJANGO, changeOrigin: false },
      '/media': { target: DJANGO, changeOrigin: false },
      '/accounts': { target: DJANGO, changeOrigin: false },
      '/admin': { target: DJANGO, changeOrigin: false },
      '/static': { target: DJANGO, changeOrigin: false },
      '/ai': { target: DJANGO, changeOrigin: false },
      '/ajax': { target: DJANGO, changeOrigin: false },
    },
  },
})
