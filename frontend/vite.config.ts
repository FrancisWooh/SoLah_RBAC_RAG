import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  preview: {
    allowedHosts: ['aspire.5gbulab.tech', 'admin.aspire.5gbulab.tech'],
  },
})
