/// <reference types="vite/client" />

// 前端會讀到的環境變數（說明見專案根目錄的 .envExample.md）
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_ASSISTANT_ENABLED?: string;
  readonly VITE_DEFAULT_PERSONA?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
