import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Paths the FastAPI backend serves. During development the Vite server forwards
// them to it, so the browser sees a single origin and the API needs no CORS setup.
const apiPaths = ['/auth', '/resources', '/metrics', '/users', '/audit', '/health']

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(apiPaths.map((path) => [path, 'http://127.0.0.1:8000'])),
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
