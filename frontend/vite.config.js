import process from 'node:process'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the API is proxied, so no CORS or hard-coded host is needed.
// For a separate production host set VITE_API_URL at build time (see .env.example).
export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', globals: true, setupFiles: './src/test/setup.js' },
  server: {
    proxy: {
      '/api': { target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
    },
  },
})
