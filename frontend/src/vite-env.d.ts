/// <reference types="vite/client" />

// 前端會讀到的環境變數（說明見專案根目錄的 .envExample.md）
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_ASSISTANT_ENABLED?: string;
  readonly VITE_DEFAULT_PERSONA?: string;
  readonly VITE_ADMIN_URL?: string;
}

// 開發時的 Django 位址，由 vite.config.ts 的 define 帶進來（預設 http://localhost:8000，可用 BACKEND_URL 改）
declare const __BACKEND_URL__: string;

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
