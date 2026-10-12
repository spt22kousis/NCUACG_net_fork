// frontend/src/api/client.ts
// 全站唯一的 HTTP 進出口：統一 base URL、自動帶 token、access token 過期自動續命。
import axios from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';
import { API_BASE } from '../config';

const ACCESS_TOKEN_KEY = 'accessToken';
const REFRESH_TOKEN_KEY = 'refreshToken';

/** 續命失敗（refresh 也過期）時廣播，讓 AuthContext 把使用者狀態清掉 */
export const AUTH_LOGOUT_EVENT = 'auth:logout';

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function getAccessToken(): string | null {
  return safeGet(ACCESS_TOKEN_KEY);
}

export function setTokens(access: string, refresh?: string): void {
  try {
    if (access) localStorage.setItem(ACCESS_TOKEN_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
  } catch {
    /* 無痕模式等情況下寫不進去，忽略 */
  }
}

export function clearTokens(): void {
  try {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export const api = axios.create({ baseURL: API_BASE });

// 送出前自動帶上 access token。
// 後端的公開端點（login / register / logout / captcha）都設了
// authentication_classes = []，所以就算帶著過期 token 也不會被擋。
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 同一時間多個請求一起 401 時，只打一次 refresh，其餘共用同一個結果
let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refresh = safeGet(REFRESH_TOKEN_KEY);
  if (!refresh) throw new Error('no refresh token');

  // 這裡刻意用原生 axios 而非 api，避免 refresh 自己 401 時無限遞迴
  const res = await axios.post(`${API_BASE}/token/refresh/`, { refresh });
  const access: string = res.data?.access;
  if (!access) throw new Error('refresh response missing access token');

  // 後端 ROTATE_REFRESH_TOKENS=True，會一併回傳新的 refresh token
  setTokens(access, res.data?.refresh);
  return access;
}

/** refresh token 本身被拒（沒有、過期、帳號停用），而不是網路或伺服器暫時出錯 */
function isRefreshRejected(err: unknown): boolean {
  if (!axios.isAxiosError(err)) return true; // 手上沒有 refresh token、或回應缺 access
  const status = err.response?.status;
  return status === 400 || status === 401;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error?.config as
      | (InternalAxiosRequestConfig & { _retried?: boolean })
      | undefined;

    // 只處理 401，而且每個請求最多重試一次
    if (error?.response?.status !== 401 || !original || original._retried) {
      return Promise.reject(error);
    }
    original._retried = true;

    try {
      if (!refreshPromise) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }
      const access = await refreshPromise;
      original.headers.Authorization = `Bearer ${access}`;
      return api(original);
    } catch (refreshError) {
      // 斷線、後端 5xx、重啟中這類暫時性錯誤不代表 refresh token 失效，
      // 保留憑證、照原本的錯誤失敗即可，等後端恢復後下一個請求還能續命
      if (!isRefreshRejected(refreshError)) {
        return Promise.reject(error);
      }

      // refresh 也失效了：清掉憑證並通知全站
      clearTokens();
      try {
        window.dispatchEvent(new CustomEvent(AUTH_LOGOUT_EVENT));
      } catch {
        /* ignore */
      }

      // 以訪客身分重送一次：公開端點（公告、成果牆）會照常回資料，
      // 需要登入的端點則會再回 401，交給呼叫端處理。
      // 原本就沒帶 token 的請求重送也沒意義，直接失敗。
      if (original.headers.Authorization) {
        delete original.headers.Authorization;
        return api(original);
      }
      return Promise.reject(error);
    }
  }
);

export default api;
