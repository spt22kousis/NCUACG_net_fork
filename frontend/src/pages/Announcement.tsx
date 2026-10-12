// frontend/src/pages/Announcement.tsx
import { useEffect, useState } from 'react';
import Sidebar from '../components/Sidebar';
import { api } from '../api/client';

type EventRow = {
  id: number;
  title: string;
  description?: string | null;
  location?: string | null;
  start_time: string; // ISO8601 from backend
  end_time?: string | null;
};

export default function Announcement() {
  const [events, setEvents] = useState<EventRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // 從後端拉「未來活動」清單（預設 30 天內）
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get<EventRow[]>('/event/upcoming/', { params: { days: 30 } });
        const data = res.data;
        setEvents(Array.isArray(data) ? data : []);
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load events.');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <>
      <Sidebar />
      <main style={{ padding: '16px', maxWidth: 960, margin: '0 auto' }}>
        <h1 style={{ margin: '8px 0 16px' }}>最新活動（未來 30 天）</h1>

        {loading && <div>載入中…</div>}
        {err && !loading && <div style={{ color: 'crimson' }}>載入失敗：{err}</div>}
        {!loading && !err && events.length === 0 && (
          <div>目前 30 天內沒有活動</div>
        )}

        {!loading && !err && events.length > 0 && (
          <div style={{ display: 'grid', gap: 12 }}>
            {events.map(e => {
              const start = new Date(e.start_time);
              const end = e.end_time ? new Date(e.end_time) : null;

              return (
                <article
                  key={e.id}
                  style={{
                    border: '1px solid #e5e7eb',
                    borderRadius: 12,
                    padding: 14,
                    background: '#fff',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                  }}
                >
                  <h2 style={{ margin: '0 0 6px', fontSize: 18 }}>{e.title}</h2>
                  <div style={{ fontSize: 14, color: '#374151', marginBottom: 6 }}>
                    🕒 {start.toLocaleString()}
                    {end ? ` – ${end.toLocaleString()}` : ''}
                  </div>
                  {e.location && (
                    <div style={{ fontSize: 14, color: '#4b5563', marginBottom: 6 }}>
                      📍 {e.location}
                    </div>
                  )}
                  {e.description && (
                    <p style={{ margin: 0, color: '#111827', whiteSpace: 'pre-wrap' }}>
                      {e.description}
                    </p>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </main>
    </>
  );
}
