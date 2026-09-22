// frontend/src/components/PersonaSwitch.tsx
import { useMemo } from 'react';
import { useChatContext } from '../contexts/chat';
import personasJson from '../data/personas.json';

type Persona = {
  id: string;
  name?: string;
  displayName?: string;
  description?: string;
  avatar?: string;
  hidden?: boolean; // ★ 新增：前端可見性
};

type Props = {
  showLabel?: boolean; // 是否顯示「角色：」標籤
};

export default function PersonaSwitch({ showLabel = true }: Props) {
  const { personaId, setPersonaId } = useChatContext();

  // 原始清單（保留 hidden 資訊以便判斷目前是否為隱藏 persona）
  const rawList: Persona[] = useMemo(
    () => (personasJson as Persona[]) ?? [],
    []
  );

  // 只顯示「非隱藏」的 personas（下拉清單可見）
  const visible = useMemo(
    () =>
      rawList
        .filter((p) => !p.hidden)
        .map((p) => ({
          id: p.id,
          name: p.displayName || p.name || p.id,
          description: p.description ?? '',
        })),
    [rawList]
  );

  // 目前選中的 id：若 context 尚未設定，用第一個可見項目當預設
  const currentId = personaId || visible[0]?.id || '';

  // 當前是否為「隱藏 persona」（例如透過密語啟用）
  const isHiddenActive = useMemo(() => {
    if (!currentId) return false;
    const inVisible = visible.some((p) => p.id === currentId);
    return !inVisible && rawList.some((p) => p.id === currentId);
  }, [currentId, visible, rawList]);

  // 取得目前（可能為隱藏）persona 的顯示名稱
  const currentLabel =
    rawList.find((p) => p.id === currentId)?.displayName ||
    rawList.find((p) => p.id === currentId)?.name ||
    currentId;

  return (
    <div className="persona-switch" role="group" aria-label="AI 角色切換">
      {showLabel && (
        <label htmlFor="persona-select" className="persona-switch__label">
          角色：
        </label>
      )}

      <select
        id="persona-select"
        className="persona-switch__select"
        value={currentId}
        onChange={(e) => setPersonaId(e.target.value)}
        aria-label="選擇 AI 助理角色"
      >
        {/* 若目前為隱藏 persona，就在頂端放一個唯讀展示用的 option，避免 value 不在 options 的警告 */}
        {isHiddenActive && (
          <option value={currentId} disabled>
            {currentLabel}（隱藏）
          </option>
        )}

        {visible.map((p) => (
          <option key={p.id} value={p.id} title={p.description}>
            {p.name}
          </option>
        ))}
      </select>

      {/* 超薄樣式；若有全域設計系統可移除 */}
      <style>{`
        .persona-switch { display: inline-flex; align-items: center; gap: .5rem; }
        .persona-switch__label { font-size: .9rem; color: #444; }
        .persona-switch__select {
          padding: .4rem .6rem;
          border-radius: .5rem;
          border: 1px solid #cfd4dc;
          background: #fff;
          font-size: .95rem;
          min-width: 180px;
        }
        .persona-switch__select:focus {
          outline: none;
          border-color: #5b8cff;
          box-shadow: 0 0 0 3px rgba(91,140,255,.18);
        }
        @media (max-width: 640px) {
          .persona-switch { width: 100%; }
          .persona-switch__select { width: 100%; }
        }
      `}</style>
    </div>
  );
}
