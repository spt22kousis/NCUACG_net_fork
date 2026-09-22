// frontend/src/config.ts
// 全站共用設定。所有對後端的呼叫一律經過 API_BASE，不要再寫死 http://localhost:8000，
// 否則部署到真實網域時，瀏覽器會去打訪客自己電腦的 8000 port。

// 預設走相對路徑 /api，開發時由 vite.config.ts 的 proxy 轉給 Django。
export const API_BASE: string = import.meta.env.VITE_API_BASE || '/api';

