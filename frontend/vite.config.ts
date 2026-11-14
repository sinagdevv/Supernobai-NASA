import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { chunkSizeWarningLimit: 1200 },
  // MapLibre 6 resolves its ESM worker via import.meta.url, which pre-bundling breaks.
  // The Layer 2/3 geoprocessing service (backend/geoprocessing) is reached at /api; override with VITE_TERRAWINDOW_API.
  server: { proxy: { '/api': { target: 'http://localhost:8000', rewrite: (p) => p.replace(/^\/api/, '') } } },
  preview: { proxy: { '/api': { target: 'http://localhost:8000', rewrite: (p) => p.replace(/^\/api/, '') } } },
  optimizeDeps: { exclude: ['maplibre-gl'] },
})
