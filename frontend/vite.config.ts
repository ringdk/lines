import { createHmac, randomBytes } from 'node:crypto'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In production Lines runs inside Serafina, at /api/apps/lines/, so
// every URL in the app is relative (base './', fetch('api/…')).
//
// For frontend work, `npm run dev` serves on :5174 and stands in for
// Serafina's app proxy: it forwards api/ to the app's /ui/ on :8795 and signs
// each request the way she does. Give it the app's LINES_APP_KEY and a
// LINES_USERS email:
//   LINES_DEV_APP_KEY=… LINES_DEV_USER=you@example.com npm run dev
const backend = process.env.LINES_BACKEND ?? 'http://127.0.0.1:8795'
const devKey = process.env.LINES_DEV_APP_KEY
const devUser = (process.env.LINES_DEV_USER ?? '').toLowerCase()

const signed = {
  target: backend,
  changeOrigin: true,
  rewrite: (path: string) => `/ui${path}`,
  configure: (proxy: { on: (event: string, cb: (proxyReq: any, req: any) => void) => void }) => {
    proxy.on('proxyReq', (proxyReq, req) => {
      if (!devKey || !devUser) return
      const time = String(Math.floor(Date.now() / 1000))
      const nonce = randomBytes(16).toString('hex')
      const message = ['serafina-app-v1', time, nonce, String(req.method).toUpperCase(), proxyReq.path, devUser].join('\n')
      proxyReq.setHeader('X-Serafina-User', devUser)
      proxyReq.setHeader('X-Serafina-Time', time)
      proxyReq.setHeader('X-Serafina-Nonce', nonce)
      proxyReq.setHeader('X-Serafina-Signature', createHmac('sha256', devKey).update(message).digest('hex'))
    })
  },
}

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    port: 5174,
    host: '127.0.0.1',
    proxy: {
      '/api': signed,
      // this app's own: anything else its pages fetch, such as '/media'
      // end of this app's own
    },
  },
})
