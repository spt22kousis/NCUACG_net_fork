// frontend/src/config.ts
// 全站共用設定。所有對後端的呼叫一律經過 API_BASE，不要再寫死 http://localhost:8000，
// 否則部署到真實網域時，瀏覽器會去打訪客自己電腦的 8000 port。

// 預設走相對路徑 /api，開發時由 vite.config.ts 的 proxy 轉給 Django。
export const API_BASE: string = import.meta.env.VITE_API_BASE || '/api';

// AI 助理目前在後端是關閉的（assistant app 未掛載，且缺 sentence-transformers
// 與 GROQ_API_KEY）。關閉時前端顯示「維護中」，不會真的去打 API。
// 後端準備好後，在 .env 設 VITE_ASSISTANT_ENABLED=true 即可開啟。
export const ASSISTANT_ENABLED: boolean =
  String(import.meta.env.VITE_ASSISTANT_ENABLED ?? '').toLowerCase() === 'true';

// Django 後台。開發時前端在 5173、後台在 Django 那邊（vite 只轉發 /api 與 /media，所以要直接連過去；
// 位址跟 vite.config.ts 的 proxy 一樣，預設 8000，用 BACKEND_URL 改 port 時這裡也會跟著變）；
// 正式站前後端同網域時就是 /admin/。不同網域請在 .env 設 VITE_ADMIN_URL。
export const ADMIN_URL: string =
  import.meta.env.VITE_ADMIN_URL || (import.meta.env.DEV ? `${__BACKEND_URL__.replace(/\/$/, '')}/admin/` : '/admin/');
