import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  cacheDir: 'node_modules/.vite',
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
  },
})
