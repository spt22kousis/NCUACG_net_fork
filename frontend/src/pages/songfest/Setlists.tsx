// frontend/src/pages/songfest/Setlists.tsx
// 歌單瀏覽：歷屆歌謠祭列表（依學年度分組），點進去看該場播過的歌
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { isAxiosError } from 'axios';
import SongfestLayout from './SongfestLayout';
import {
  fetchFestival, fetchFestivals, formatDate, todayIso,
  type Festival, type FestivalDetail,
} from '../../api/songfest';

/** 學年度從 8 月開始：2025/09 與 2026/06 都是 114 學年度 */
function academicYear(iso: string): number {
  const [y, m] = iso.split('-').map(Number);
  return m >= 8 ? y - 1911 : y - 1912;
}

export function SetlistIndex() {
  const [festivals, setFestivals] = useState<Festival[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchFestivals().then(setFestivals).catch(() => setError(true));
  }, []);

  const today = todayIso();
  const byYear = new Map<number, Festival[]>();
  for (const f of festivals ?? []) {
    // 有播放紀錄的歷屆場次，加上排歌組已經公布歌單的場次（可能還沒舉辦）
    if (!(f.playCount > 0 && f.date < today) && !f.setlistPublic) continue;
    const year = academicYear(f.date);
    byYear.set(year, [...(byYear.get(year) ?? []), f]);
  }

  return (
    <SongfestLayout>
      <p className="sf-lead">歷屆大講堂歌謠祭播過的歌（KTV 場是當天點歌，沒有歌單）。</p>
      {error && <p className="sf-error">載入失敗，請稍後再試。</p>}
      {!error && festivals === null && <p className="sf-muted">載入中…</p>}
      {festivals !== null && byYear.size === 0 && <div className="sf-card sf-empty">還沒有播放紀錄。</div>}
      {[...byYear.entries()].map(([year, list]) => (
        <section key={year} className="sf-section">
          <h2 className="sf-section-title">{year} 學年度</h2>
          <div className="sf-festival-grid">
            {list.map(f => (
              <Link key={f.id} to={`/songfest/setlists/${f.id}`} className="sf-card sf-festival-card">
                <strong>{f.name}</strong>
                <span>{formatDate(f.date, true)}</span>
                <span className="sf-muted">{f.playCount > 0 ? `${f.playCount} 首` : '已公布歌單'}</span>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </SongfestLayout>
  );
}

export function SetlistDetail() {
  const { id } = useParams();
  const [festival, setFestival] = useState<FestivalDetail | null>(null);
  const [error, setError] = useState<'notFound' | 'failed' | null>(null);

  useEffect(() => {
    setFestival(null);
    setError(null);
    fetchFestival(Number(id))
      .then(setFestival)
      .catch(err => setError(isAxiosError(err) && err.response?.status === 404 ? 'notFound' : 'failed'));
  }, [id]);

  return (
    <SongfestLayout>
      <Link to="/songfest/setlists" className="sf-back">← 所有場次</Link>
      {error === 'notFound' && <div className="sf-card sf-empty">找不到這一場歌謠祭。</div>}
      {error === 'failed' && <p className="sf-error">載入失敗，請稍後再試。</p>}
      {!error && festival === null && <p className="sf-muted">載入中…</p>}
      {festival && (
        <>
          <div className="sf-setlist-head">
            <h2>{festival.name}</h2>
            <p className="sf-muted">
              {formatDate(festival.date, true)}
              {festival.venue && ` · ${festival.venue}`}
              {festival.playCount > 0 && ` · ${festival.playCount} 首`}
              {/* 相簿只有社員看得到，沒登入點進去會請他登入 */}
              {' · '}<Link to={`/photos?kind=songfest&festival=${festival.id}`}>活動照片</Link>
            </p>
          </div>
          {festival.playCount === 0 && festival.sessions.length > 0 && (
            <>
              <p className="sf-muted sf-note">排歌組公布的歌單，當天可能會有小調整。</p>
              {festival.sessions.map(session => (
                <section key={session.name} className="sf-section-tight">
                  <h3 className="sf-section-title">{session.name} · {session.startTime}</h3>
                  <ol className="sf-card sf-setlist">
                    {session.entries.map(e => (
                      <li key={e.position} className={e.label === '結尾影片' ? 'is-credits' : undefined}>
                        <span className="sf-rank">{e.position}</span>
                        <span className="sf-setlist-song">
                          <strong>{e.title}</strong>
                          <small>
                            {e.visualSource && e.visualSource !== e.songSource
                              ? `${e.songSource}（畫面：${e.visualSource}）`
                              : e.songSource}
                          </small>
                        </span>
                        <span className="sf-setlist-meta"><small>{e.label}</small></span>
                      </li>
                    ))}
                  </ol>
                </section>
              ))}
            </>
          )}
          {festival.playCount > 0 && (
          <>
          <p className="sf-muted sf-note">依播放紀錄的順序列出；有 DVD 編號的是歌單裡對得到的那一支。</p>
          <ol className="sf-card sf-setlist">
            {festival.plays.map(p => (
              <li key={p.position} className={p.isCredits ? 'is-credits' : undefined}>
                <span className="sf-rank">{p.position}</span>
                <span className="sf-setlist-song">
                  <strong>{p.title}</strong>
                  <small>
                    {p.isCredits
                      ? `結尾影片（5 秒畫面合輯）· ${p.songSource}`
                      : p.visualSource && p.visualSource !== p.songSource
                        ? `${p.songSource}（畫面：${p.visualSource}）`
                        : p.songSource}
                  </small>
                </span>
                {p.dvdCode && (
                  <span className="sf-setlist-meta">
                    <span className="sf-code">{p.dvdCode}</span>
                    {p.editor && <small>{p.editor}</small>}
                  </span>
                )}
              </li>
            ))}
          </ol>
          </>
          )}
        </>
      )}
    </SongfestLayout>
  );
}
