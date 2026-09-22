// frontend/src/components/NoticeBoard.tsx
import React, { useState, useEffect, useRef } from 'react';
import fallbackNotices from '../data/notices.json'; // 失敗時備援
import { api } from '../api/client';
import '../styles/NoticeBoard.css';

const MAX_LINES = 6;
const LINE_HEIGHT = 24;

type UiNotice = {
  id: string | number;
  title: string;
  content: string;
  date: string; // 顯示用
  startISO?: string | null; // 比較用（若有）
};

function toLocalDateTimeString(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function parseMaybeDate(s?: string | null) {
  if (!s) return null;
  const d = new Date(s);
  return isNaN(+d) ? null : d;
}

// 後端 /api/event/upcoming/ 的一筆資料
type ApiEvent = {
  id?: number | string;
  title?: string;
  description?: string | null;
  start_time?: string | null;
};

// 本地備援 notices.json 的一筆資料
type LocalNotice = {
  title?: string;
  content?: string;
  date?: string;
};

function mapApiEventsToUi(data: ApiEvent[]): UiNotice[] {
  // 後端 /event/upcoming/ 回傳的欄位：id,title,description,location,start_time,end_time
  return (data || []).map((e) => ({
    id: e.id ?? crypto.randomUUID(),
    title: String(e.title ?? ''),
    content: String(e.description ?? ''),
    date: e.start_time ? toLocalDateTimeString(e.start_time) : '',
    startISO: e.start_time ?? null,
  }));
}

function mapLocalNoticesToUi(data: LocalNotice[]): UiNotice[] {
  // 你原本的 notices.json：title / content / date(字串)
  return (data || []).map((n, idx) => ({
    id: idx,
    title: String(n.title ?? ''),
    content: String(n.content ?? ''),
    date: String(n.date ?? ''),
    startISO: n.date ?? null,
  }));
}

function keepUpcoming(items: UiNotice[]): UiNotice[] {
  const now = new Date();
  return items
    .filter((n) => {
      const dt = parseMaybeDate(n.startISO ?? n.date);
      return dt ? dt >= now : true; // 沒時間就保留
    })
    .sort((a, b) => {
      const da = parseMaybeDate(a.startISO ?? a.date)?.getTime() ?? Number.MAX_SAFE_INTEGER;
      const db = parseMaybeDate(b.startISO ?? b.date)?.getTime() ?? Number.MAX_SAFE_INTEGER;
      return da - db;
    });
}

const NoticeBoard: React.FC = () => {
  const [items, setItems] = useState<UiNotice[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);
  const [shouldShowReadMore, setShouldShowReadMore] = useState(false);

  const contentRef = useRef<HTMLDivElement>(null);
  const current = items[currentIndex];

  // 取資料：優先後端 API，失敗時退回本地檔
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const resp = await api.get<ApiEvent[]>('/event/upcoming/', { params: { days: 30 } });
        const mapped = keepUpcoming(mapApiEventsToUi(resp.data));
        if (!cancelled) setItems(mapped);
      } catch {
        const mapped = keepUpcoming(mapLocalNoticesToUi(fallbackNotices as LocalNotice[]));
        if (!cancelled) setItems(mapped);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // 切換公告時重設展開狀態
  useEffect(() => {
    setIsExpanded(false);
  }, [currentIndex]);

  // 測量是否需要顯示 read more
  useEffect(() => {
    if (!contentRef.current) return;
    const el = contentRef.current;
    // 強制更新 scrollHeight
    requestAnimationFrame(() => {
      const maxVisibleHeight = MAX_LINES * LINE_HEIGHT;
      const actualHeight = el.scrollHeight;
      setShouldShowReadMore(actualHeight > maxVisibleHeight);
    });
  }, [current?.content, isExpanded]);

  const handleNext = () => {
    if (currentIndex < items.length - 1) setCurrentIndex((i) => i + 1);
  };
  const handlePrev = () => {
    if (currentIndex > 0) setCurrentIndex((i) => i - 1);
  };

  if (loading) {
    return (
      <div className="notice-board-container">
        <div className="notice-card-wrapper">
          <div className="notice-card empty-state">載入中…</div>
        </div>
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="notice-board-container">
        <div className="notice-card-wrapper">
          <div className="notice-card empty-state">目前 30 天內沒有活動</div>
        </div>
      </div>
    );
  }

  return (
    <div className="notice-board-container">
      <div className="notice-stack-back" />
      <div className="notice-stack-middle" />

      <div className="notice-card-wrapper">
        <div className="notice-card">
          <div className="notice-title">{current.title}</div>

          <div
            className={`notice-content ${isExpanded ? 'expanded' : 'collapsed'}`}
            ref={contentRef}
            style={{
              maxHeight: isExpanded ? '2000px' : `${MAX_LINES * LINE_HEIGHT}px`,
              transition: 'max-height 1s ease',
            }}
          >
            {current.content}
          </div>

          {shouldShowReadMore && (
            <div className="notice-more" onClick={() => setIsExpanded((prev) => !prev)}>
              {isExpanded ? '收起 ▲' : 'read more ▼'}
            </div>
          )}

          {(isExpanded || !shouldShowReadMore) && (
            <div className="notice-date">{current.date}</div>
          )}
        </div>
      </div>

      {/* 公告導航圓點 */}
      <div className="notice-nav-dots-container">
        {items.map((_, index) => (
          <div
            key={index}
            className={`notice-nav-dots ${index === currentIndex ? 'active' : ''}`}
            onClick={() => setCurrentIndex(index)}
          />
        ))}
      </div>

      {/* 公告導航按鈕 */}
      <div className="notice-nav">
        <button
          className={`nav-button ${currentIndex === 0 ? 'hidden' : ''}`}
          onClick={handlePrev}
        >
          ◀
        </button>
        <button
          className={`nav-button ${currentIndex === items.length - 1 ? 'hidden' : ''}`}
          onClick={handleNext}
        >
          ▶
        </button>
      </div>
    </div>
  );
};

export default NoticeBoard;
