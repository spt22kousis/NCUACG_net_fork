// frontend/src/components/ChatWidget.tsx
import { useEffect, useMemo, useState, type CSSProperties } from 'react';

import AssistantChat from '../pages/AssistantChat';        // 重用聊天頁
import personasJson from '../data/personas.json';

const PERSONA_LS_KEY = 'ncuacg.personaId';

type Persona = {
  id: string;
  name?: string;         // 有些資料用 name
  displayName?: string;  // 有些資料用 displayName
  summary?: string;
  avatar?: string;
};

export default function ChatWidget() {
  const [open, setOpen] = useState(false);

  // personas 映射表（id -> 顯示名稱）
  const personas = useMemo(() => (Array.isArray(personasJson) ? personasJson as Persona[] : Object.values(personasJson as Record<string, Persona>)), []);
  const getPersonaName = (id?: string | null) => {
    if (!id) return '';
    const p = personas.find(x => x.id === id);
    return p?.displayName || p?.name || id;
  };

  // 目前 persona：LocalStorage 初值 + 事件同步
  const [personaId, setPersonaId] = useState<string>(() => {
    try {
      return localStorage.getItem(PERSONA_LS_KEY) || '';
    } catch {
      return '';
    }
  });

  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.id) setPersonaId(detail.id as string);
    };
    window.addEventListener('persona:change', onChange as EventListener);
    return () => window.removeEventListener('persona:change', onChange as EventListener);
  }, []);

  // 開啟面板時鎖住 body 捲動（行動裝置更穩）
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = open ? 'hidden' : prev || '';
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  // --- 樣式：固定在左下角 ---
  const basePanelStyle: CSSProperties = {
    position: 'fixed',
    bottom: '96px',
    left: '24px',
    width: '360px',
    height: '520px',
    background: '#fff',
    borderRadius: '12px',
    boxShadow: '0 8px 20px rgba(0,0,0,.25)',
    zIndex: 1000,
    overflow: 'hidden',               // 外層不捲動，內層處理
    display: 'flex',                  // 子層用 flex 取得可捲高度
    flexDirection: 'column',
    transition: 'opacity .2s ease, transform .2s ease',
  };
  const visibleStyle: CSSProperties = {
    opacity: 1,
    transform: 'translateY(0)',
    visibility: 'visible',
    pointerEvents: 'auto',
  };
  const hiddenStyle: CSSProperties = {
    opacity: 0,
    transform: 'translateY(8px)',
    visibility: 'hidden',
    pointerEvents: 'none',
  };

  const headerStyle: CSSProperties = {
    height: 44,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 12px',
    borderBottom: '1px solid #eee',
    background: '#fafbff',
    fontSize: '.9rem',
  };
  const pillStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '4px 10px',
    borderRadius: 999,
    border: '1px solid #dde3ff',
    background: '#f1f4ff',
    color: '#3f5bd9',
    fontWeight: 600,
  };

  return (
    <>
      {/* 浮動開關按鈕 */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="ai-chat-panel"
        aria-label={open ? '收合助理' : '開啟助理'}
        style={{
          position: 'fixed',
          bottom: '24px',
          left: '24px',
          width: '56px',
          height: '56px',
          borderRadius: '50%',
          background: '#4f8cff',
          color: '#fff',
          border: 'none',
          fontSize: '1.5rem',
          cursor: 'pointer',
          boxShadow: '0 4px 12px rgba(0,0,0,.2)',
          zIndex: 1001,
        } as CSSProperties}
        title={open ? '收合助理' : '開啟助理'}
      >
        💬
      </button>

      {/* 面板：永遠掛載，用樣式切換可見性（保留對話狀態） */}
      <div
        id="ai-chat-panel"
        style={{
          ...basePanelStyle,
          ...(open ? visibleStyle : hiddenStyle),
        }}
        // 若 @types/react 過舊可把 overscroll-behavior 放到 CSS 類別
      >
        {/* 標頭：顯示當前 persona 名稱 */}
        <div style={headerStyle}>
          <strong>社網 AI 助理</strong>
          <span style={pillStyle} title="於面板內可切換角色">
            🤖 角色：{getPersonaName(personaId) || '（預設）'}
          </span>
        </div>

        {/* 主要聊天內容（含 PersonaSwitch 與訊息列表/輸入框） */}
        <div style={{ height: 'calc(100% - 44px)' }}>
          <AssistantChat />
        </div>
      </div>
    </>
  );
}
