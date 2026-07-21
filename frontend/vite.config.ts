import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/health': 'http://localhost:8000',
      '/recordings': 'http://localhost:8000',
      '/storage': 'http://localhost:8000',
      '/settings': 'http://localhost:8000',
      '/logs': 'http://localhost:8000',
      '/snapshot': 'http://localhost:8000',
      '/camera': 'http://localhost:8000',
      '/recording': 'http://localhost:8000',
      '/stream.mjpeg': 'http://localhost:8000'
    }
  }
})
