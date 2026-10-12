// frontend/src/contexts/chat.ts
// ChatContext 物件、型別、常數與 useChatContext hook。
// 跟 ChatContext.tsx（只放 <ChatProvider> 元件）分開的原因同 ./auth.ts。
import { createContext, useContext } from 'react';
import type { useChat } from '../hooks/useChat';

// ---- 常數（也讓其他元件可引用） ----
export const PERSONA_LS_KEY = 'ncuacg.personaId';
export const PERSONA_EVENT = 'persona:change';

// ---- 型別 ----
type BaseChat = ReturnType<typeof useChat>;
export type ChatContextType = BaseChat & {
  personaId: string;
  setPersonaId: (id: string) => void;
};

// ---- Context ----
export const ChatCtx = createContext<ChatContextType | null>(null);

// ---- Hook ----
export function useChatContext(): ChatContextType {
  const ctx = useContext(ChatCtx);
  if (!ctx) throw new Error('useChatContext must be used within <ChatProvider>');
  return ctx;
}
