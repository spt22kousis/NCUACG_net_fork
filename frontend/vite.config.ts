import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // ① Key = 前端要攔截的 path (可用正則 ^/api/.*)
      '/api': {
        target: 'http://localhost:8000', // ② 後端真實位址
        configure(proxy) {
          proxy.on('proxyReq', (_, req) =>
            console.log('[proxy] ', req.method, req.path)
          );
        },
      },
      // 成果牆上傳的影片/圖片由 Django 提供（settings.MEDIA_URL）
      '/media': {
        target: 'http://localhost:8000',
      },
    }
  }
})
