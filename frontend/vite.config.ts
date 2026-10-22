import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The API has no CORS middleware (it's an internal tool served same-origin
// in production), so dev requests go through this proxy instead: the app
// always calls /api/... and Vite forwards to the FastAPI server.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.API_URL ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
