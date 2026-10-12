// frontend/src/hooks/useChat.ts
import { useEffect, useState } from 'react';
import { api } from '../api/client';

// —— 型別 —— //
export type ChatMessage = {
  role: 'assistant' | 'user';
  text: string;
};

// —— LocalStorage Keys（與 ChatContext 保持一致；避免循環依賴這裡自行宣告常數） —— //
const CHAT_LS_KEY = 'ncuacg.chat.history.v1';
const PERSONA_LS_KEY = 'ncuacg.personaId';

// —— API endpoint —— //
// 走全站共用的 api client（base URL 已含 /api）。
// 註：這裡原本自己組 `${API_BASE}/api/assistant/chat/`，一旦有人設定
// VITE_API_BASE=/api 就會變成 /api/api/assistant/chat/。
const CHAT_PATH = '/assistant/chat/';

type ChatResponse = {
  reply?: string;
  personaUsed?: string;
};

// —— Hook 主體 —— //
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const raw = typeof window !== 'undefined' ? window.localStorage.getItem(CHAT_LS_KEY) : null;
      return raw ? (JSON.parse(raw) as ChatMessage[]) : [];
    } catch {
      return [];
    }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 永續化聊天紀錄
  useEffect(() => {
    try {
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(CHAT_LS_KEY, JSON.stringify(messages));
      }
    } catch {
      /* ignore */
    }
  }, [messages]);

  // 送出訊息：自動帶上目前 personaId（來自 LocalStorage），並接住後端回傳的 personaUsed 做持久化
  const sendMessage = async (text: string, options?: { personaId?: string }) => {
    const clean = text.trim();
    if (!clean) return;

    // 先把使用者訊息放進視窗
    const userMsg: ChatMessage = { role: 'user', text: clean };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setError(null);

    try {
      // 從 LocalStorage 取目前 personaId；密語命中時，後端會覆蓋並回傳 personaUsed
      // 呼叫端可明確指定 persona；ChatContext 的初值可能來自 VITE_DEFAULT_PERSONA，
      // 那個值在使用者切換前並不會寫進 LocalStorage，所以不能只看 LocalStorage。
      const personaId =
        options?.personaId ||
        (typeof window !== 'undefined' && window.localStorage.getItem(PERSONA_LS_KEY)) ||
        '';

      const payload = {
        message: clean,
        personaId,                // 讓後端有「偏好 persona」；若有密語會被覆蓋
        now: new Date().toISOString(), // 可選：提供當前時間（後端/檢索可用）
      };

      // 非 2xx 時 axios 會直接丟例外，交給下面的 catch
      const { data } = await api.post<ChatResponse>(CHAT_PATH, payload);

      // 放入 AI 回覆
      const aiText = (data?.reply ?? '').toString();
      const aiMsg: ChatMessage = { role: 'assistant', text: aiText };
      setMessages((prev) => [...prev, aiMsg]);

      // ★ 關鍵：後端會回 personaUsed（包含密語觸發的隱藏 persona）
      const used: string | undefined = data?.personaUsed;
      if (used && typeof window !== 'undefined') {
        window.localStorage.setItem(PERSONA_LS_KEY, used);
        // 廣播事件，讓 ChatContext/PersonaSwitch 等即時同步
        window.dispatchEvent(new CustomEvent('persona:change', { detail: { id: used } }));
      }
    } catch {
      setError('發送失敗，請稍後再試');
      // 也可以選擇把剛剛 push 的 user 訊息移除；這裡先保留方便除錯
      // setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  const clear = () => {
    setMessages([]);
    try {
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(CHAT_LS_KEY);
      }
    } catch {
      /* ignore */
    }
  };

  return {
    messages,
    sendMessage,
    loading,
    error,
    clear,
  };
}
