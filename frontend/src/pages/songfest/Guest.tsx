// frontend/src/pages/songfest/Guest.tsx
// 亂入投稿說明：非本社的投稿者用 Google 表單投稿，表單回覆由排歌組匯入網站
import { useEffect, useState } from 'react';
import SongfestLayout from './SongfestLayout';
import { DeadlineList } from './Submit';
import { fetchActiveFestival, formatDate, isPast, type ActiveFestival } from '../../api/songfest';

export default function Guest() {
  const [active, setActive] = useState<ActiveFestival | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchActiveFestival().then(setActive).catch(() => setError(true));
  }, []);

  const festival = active?.festival ?? null;
  const formOpen = festival !== null && festival.guestFormUrl !== '' && !isPast(festival.guestDeadline);

  return (
    <SongfestLayout>
      <p className="sf-lead">
        不是中央動畫社的社員，也歡迎投稿「亂入曲」！亂入曲用 Google 表單投稿，畫面或歌曲至少一者要符合廣義 ACGN，
        並請在影片中加上方便觀眾辨識的字幕。數量太多時由本社決定播放曲目。
      </p>

      {error && <p className="sf-error">載入失敗，請稍後再試。</p>}
      {!error && active === null && <p className="sf-muted">載入中…</p>}
      {active !== null && festival === null && (
        <div className="sf-card sf-empty">目前沒有準備中的歌謠祭，下一場的投稿資訊會公告在社團粉專。</div>
      )}

      {festival && (
        <section className="sf-card sf-festival-panel">
          <h2>{festival.name}歌謠祭 · {formatDate(festival.date, true)}</h2>
          {festival.guestDeadline && <DeadlineList festival={festival} guest />}
          {festival.guestInfo
            ? <p className="sf-guest-info">{festival.guestInfo}</p>
            : <p className="sf-muted">這一場的亂入曲投稿說明還沒公布。</p>}
          {formOpen && (
            <a className="sf-button is-primary sf-guest-link" href={festival.guestFormUrl} target="_blank" rel="noreferrer">
              前往亂入曲投稿表單
            </a>
          )}
          {festival.guestFormUrl && isPast(festival.guestDeadline) && <p className="sf-muted">這一場的亂入曲投稿已經截止。</p>}
        </section>
      )}

      <p className="sf-muted sf-note">
        有問題可以寄信到社團信箱 <a href="mailto:ncuacg.tw@gmail.com">ncuacg.tw@gmail.com</a>。
      </p>
    </SongfestLayout>
  );
}
