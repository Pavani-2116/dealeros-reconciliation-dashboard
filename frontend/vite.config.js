import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development, requests to /api are forwarded to the Django server,
// so the browser only ever talks to one origin (no CORS headaches).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
