// frontend/src/pages/songfest/SongfestHome.tsx
// 歌謠祭首頁：下一場的時間地點、各功能入口、最常播的歌
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import SongfestLayout from './SongfestLayout';
import {
  fetchFestivals, fetchRanking, fetchTracks, formatDate, todayIso,
  type Festival, type RankedSong,
} from '../../api/songfest';

const KIND_LABEL: Record<Festival['kind'], string> = {
  hall: '大講堂',
  ktv: 'KTV',
};

function UpcomingCard({ festival }: { festival: Festival }) {
  const time = festival.startTime
    ? `${festival.startTime}${festival.endTime ? ` – ${festival.endTime}` : ''}`
    : null;
  return (
    <article className="sf-card sf-upcoming">
      <div className="sf-upcoming-head">
        <span className="sf-badge">{KIND_LABEL[festival.kind]}</span>
        <h2>{festival.name}歌謠祭</h2>
      </div>
      <dl className="sf-upcoming-meta">
        <div><dt>日期</dt><dd>{formatDate(festival.date, true)}</dd></div>
        {time && <div><dt>時間</dt><dd>{time}</dd></div>}
        {festival.venue && <div><dt>地點</dt><dd>{festival.venue}</dd></div>}
      </dl>
      {festival.description && <p className="sf-upcoming-desc">{festival.description}</p>}
    </article>
  );
}

export default function SongfestHome() {
  const [festivals, setFestivals] = useState<Festival[] | null>(null);
  const [trackTotal, setTrackTotal] = useState<number | null>(null);
  const [ranking, setRanking] = useState<RankedSong[] | null>(null);
  const [rankingYears, setRankingYears] = useState(4);
  const [error, setError] = useState(false);

  useEffect(() => {
    Promise.all([fetchFestivals(), fetchTracks({ pageSize: 1 })])
      .then(([fs, tracks]) => {
        setFestivals(fs);
        setTrackTotal(tracks.count);
      })
      .catch(() => setError(true));
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchRanking(rankingYears, 10)
      .then(data => { if (!cancelled) setRanking(data); })
      .catch(() => { if (!cancelled) setRanking([]); });
    return () => { cancelled = true; };
  }, [rankingYears]);

  const today = todayIso();
  const upcoming = (festivals ?? []).filter(f => f.date >= today).reverse(); // API 是新到舊
  const past = (festivals ?? []).filter(f => f.date < today && f.playCount > 0);
  const firstYear = past.length ? past[past.length - 1].date.slice(0, 4) : null;

  return (
    <SongfestLayout>
      <p className="sf-lead">
        推廣動漫文化，讓大家一起唱出心中的動畫歌！歌單以固定順序播放，可以欣賞社員的剪輯作品，也可以拿起麥克風大聲歡唱。
      </p>

      <section className="sf-section">
        <h2 className="sf-section-title">下一場</h2>
        {error && <p className="sf-error">載入失敗，請稍後再試。</p>}
        {!error && festivals === null && <p className="sf-muted">載入中…</p>}
        {festivals !== null && upcoming.length === 0 && (
          <div className="sf-card sf-empty">下一場歌謠祭的時間還沒公布，請留意社團粉專與 Discord 公告。</div>
        )}
        {upcoming.map(f => <UpcomingCard key={f.id} festival={f} />)}
      </section>

      <section className="sf-section">
        <div className="sf-links">
          <Link to="/songfest/library" className="sf-card sf-link-card">
            <strong>舊曲清單</strong>
            <span>{trackTotal !== null ? `收錄 ${trackTotal.toLocaleString()} 首` : '社團歷年的 MV 剪輯'}</span>
          </Link>
          <Link to="/songfest/setlists" className="sf-card sf-link-card">
            <strong>歌單瀏覽</strong>
            <span>{past.length ? `${firstYear} 年起共 ${past.length} 場的播放紀錄` : '歷屆播過哪些歌'}</span>
          </Link>
          <Link to="/songfest/submit" className="sf-card sf-link-card">
            <strong>新曲投稿</strong>
            <span>報曲、繳交、回報串</span>
          </Link>
          <Link to="/songfest/requests" className="sf-card sf-link-card">
            <strong>點歌系統</strong>
            <span>點想聽的歌、幫別人 +1、徵剪輯</span>
          </Link>
        </div>
      </section>

      <section className="sf-section">
        <div className="sf-section-row">
          <h2 className="sf-section-title">最常播的歌</h2>
          <div className="sf-toggle" role="group" aria-label="統計期間">
            <button type="button" className={rankingYears === 4 ? 'is-active' : ''} onClick={() => setRankingYears(4)}>近 4 年</button>
            <button type="button" className={rankingYears === 0 ? 'is-active' : ''} onClick={() => setRankingYears(0)}>全部</button>
          </div>
        </div>
        <p className="sf-muted sf-note">同一首歌的不同剪輯版本合併計算，不含結尾的 5 秒畫面影片。</p>
        {ranking === null && <p className="sf-muted">載入中…</p>}
        {ranking !== null && ranking.length === 0 && <p className="sf-muted">還沒有播放紀錄。</p>}
        {ranking !== null && ranking.length > 0 && (
          <ol className="sf-card sf-ranking">
            {ranking.map(song => (
              <li key={`${song.rank}-${song.title}`}>
                <span className="sf-rank">{song.rank}</span>
                <span className="sf-ranking-song">
                  <strong>{song.title}</strong>
                  <small>{song.songSource}</small>
                </span>
                <span className="sf-ranking-count">{song.playCount} 次</span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </SongfestLayout>
  );
}
