import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

// Django 的位址。Windows 有時會把 8000 附近的 port 保留給系統（netsh 查得到），
// 這時改用別的 port 跑 runserver，再用 BACKEND_URL=http://localhost:8100 npm run dev 啟動。
const backend = process.env.BACKEND_URL || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // 給 src/config.ts 組開發時的後台網址（ADMIN_URL）用，跟 proxy 指向同一個 Django
  define: {
    __BACKEND_URL__: JSON.stringify(backend),
  },
  server: {
    proxy: {
      // ① Key = 前端要攔截的 path (可用正則 ^/api/.*)
      '/api': {
        target: backend, // ② 後端真實位址
        configure(proxy) {
          proxy.on('proxyReq', (_, req) =>
            console.log('[proxy] ', req.method, req.url)
          );
        },
      },
      // 成果牆上傳的影片/圖片由 Django 提供（settings.MEDIA_URL）
      '/media': {
        target: backend,
      },
    }
  }
})
