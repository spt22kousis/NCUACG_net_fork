// frontend/src/pages/songfest/Library.tsx
// 舊曲清單：社團歷年收進歌單的 MV 剪輯（只有資料，不放影片）
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { isCancel } from 'axios';
import SongfestLayout from './SongfestLayout';
import {
  fetchTrackGroups, fetchTracks, formatDate, formatDuration,
  type TrackGroup, type TrackPage, type TrackSort,
} from '../../api/songfest';

const SORT_OPTIONS: { value: TrackSort; label: string }[] = [
  { value: 'index', label: '五十音' },
  { value: 'newest', label: '最新收錄' },
  { value: 'popular', label: '近 4 年最常播' },
];

/** 「あ」→「あ行」；一般曲、特攝等分類照原名 */
function groupLabel(group: string): string {
  return /^[぀-ゟ]$/.test(group) ? `${group}行` : group;
}

export default function Library() {
  // 搜尋條件放在網址上，重新整理或分享連結都會保留
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const group = params.get('group') ?? '';
  const sort = (params.get('sort') as TrackSort | null) ?? 'index';
  const page = Number(params.get('page')) || 1;

  const [draft, setDraft] = useState(q);
  const [groups, setGroups] = useState<TrackGroup[]>([]);
  const [data, setData] = useState<TrackPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const update = (changes: Record<string, string | number | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === '' || (key === 'page' && value === 1) || (key === 'sort' && value === 'index')) {
        next.delete(key);
      } else {
        next.set(key, String(value));
      }
    }
    setParams(next, { replace: true });
  };

  useEffect(() => {
    fetchTrackGroups().then(setGroups).catch(() => setGroups([]));
  }, []);

  // 按上一頁等方式改到網址時，搜尋框跟著更新
  useEffect(() => {
    if (q !== draft.trim()) setDraft(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  // 打字停 300ms 才搜尋，避免每個字都打一次 API
  useEffect(() => {
    if (draft.trim() === q) return;
    const timer = setTimeout(() => update({ q: draft.trim(), page: null }), 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchTracks({ q, group, sort, page }, controller.signal)
      .then(res => { setData(res); setError(false); })
      .catch(err => { if (!isCancel(err)) setError(true); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [q, group, sort, page]);

  const goToPage = (next: number) => {
    update({ page: next });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <SongfestLayout>
      <p className="sf-lead">
        社團歷年收進歌單的 MV 剪輯，歌謠祭可以直接排進去播放。播放次數以「歌」計算，同一首歌的不同剪輯版本共用。
      </p>

      <div className="sf-card sf-filters">
        <input
          type="search"
          className="sf-search"
          placeholder="搜尋作品、曲名、歌手、製作者或 DVD 編號"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          aria-label="搜尋舊曲"
        />
        <div className="sf-filter-row">
          <div className="sf-chips" role="group" aria-label="五十音分類">
            <button type="button" className={group === '' ? 'is-active' : ''} onClick={() => update({ group: null, page: null })}>
              全部
            </button>
            {groups.map(g => (
              <button
                key={g.group}
                type="button"
                className={group === g.group ? 'is-active' : ''}
                onClick={() => update({ group: g.group, page: null })}
              >
                {groupLabel(g.group)}
              </button>
            ))}
          </div>
          <label className="sf-sort">
            排序
            <select value={sort} onChange={e => update({ sort: e.target.value, page: null })}>
              {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
        </div>
      </div>

      {error && <p className="sf-error">載入失敗，請稍後再試。</p>}
      {data && (
        <p className="sf-muted sf-result-count">
          {loading ? '搜尋中…' : `共 ${data.count.toLocaleString()} 首`}
        </p>
      )}

      {data && data.results.length === 0 && !loading && (
        <div className="sf-card sf-empty">找不到符合的歌。可以試試只輸入作品名或曲名的一部分。</div>
      )}

      {data && data.results.length > 0 && (
        <div className={`sf-card sf-table-wrap${loading ? ' is-loading' : ''}`}>
          <table className="sf-table">
            <thead>
              <tr>
                <th>DVD</th>
                <th>作品</th>
                <th>曲名</th>
                <th>製作者</th>
                <th className="sf-num">長度</th>
                <th>上次播放</th>
                <th className="sf-num">播放次數<br /><small>近 4 年 / 全部</small></th>
              </tr>
            </thead>
            <tbody>
              {data.results.map(t => (
                <tr key={t.dvdCode}>
                  <td className="sf-code">{t.dvdCode}</td>
                  <td>
                    <span className="sf-primary">{t.songSource}</span>
                    {t.visualSource && t.visualSource !== t.songSource && (
                      <span className="sf-secondary">畫面：{t.visualSource}</span>
                    )}
                  </td>
                  <td>
                    <span className="sf-primary">{t.title}</span>
                    {t.artist && <span className="sf-secondary">{t.artist}</span>}
                  </td>
                  <td data-label="製作者">{t.editor}</td>
                  <td data-label="長度" className="sf-num">{formatDuration(t.duration)}</td>
                  <td data-label="上次播放">{t.lastPlayed ? formatDate(t.lastPlayed) : '沒有紀錄'}</td>
                  <td data-label="播放（近 4 年/全部）" className="sf-num">
                    {t.recentPlayCount} / {t.playCount}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.pageCount > 1 && (
        <nav className="sf-pager" aria-label="分頁">
          <button type="button" disabled={data.page <= 1} onClick={() => goToPage(data.page - 1)}>上一頁</button>
          <span>第 {data.page} / {data.pageCount} 頁</span>
          <button type="button" disabled={data.page >= data.pageCount} onClick={() => goToPage(data.page + 1)}>下一頁</button>
        </nav>
      )}
    </SongfestLayout>
  );
}
