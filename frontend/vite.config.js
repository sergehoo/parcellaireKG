import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Cible du proxy dev : le Django local (runserver ou gunicorn docker).
const DJANGO = process.env.DJANGO_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],

  // En production le build est servi par Django/WhiteNoise depuis
  // static/orthophotos-app/ (voir templates/parcelaire/orthophoto/react_app.html).
  base: '/static/orthophotos-app/',

  build: {
    outDir: '../static/orthophotos-app',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Noms fixes (pas de hash) : le template Django référence
        // assets/index.js et assets/index.css. Le cache-busting est
        // assuré par le manifest WhiteNoise au collectstatic.
        entryFileNames: 'assets/index.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },

  server: {
    port: 5173,
    proxy: {
      // API JSON + endpoints d'upload / statut + tuiles + login Django.
      '/api': { target: DJANGO, changeOrigin: false },
      '/orthophotos': { target: DJANGO, changeOrigin: false },
      '/media': { target: DJANGO, changeOrigin: false },
      '/accounts': { target: DJANGO, changeOrigin: false },
      '/static/css': { target: DJANGO, changeOrigin: false },
    },
  },
})
