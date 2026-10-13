// frontend/src/pages/songfest/Requests.tsx
// 點歌：每一場歌謠祭各自一份清單（工作區的「線上點歌」）。
// 從舊曲清單搜尋點一首，或點還沒人剪過的歌（徵剪輯）；別人點過的同一首就是 +1。
import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import SongfestLayout from './SongfestLayout';
import {
  apiErrorMessage, createRequest, deleteRequest, fetchRequests, fetchTracks, fetchWishes, formatDate, formatDateTime,
  formatDuration, voteRequest,
  type RequestFestival, type RequestInput, type SongRequest, type Track, type Wish,
} from '../../api/songfest';
import { useAuth } from '../../contexts/auth';

type Filter = 'all' | 'old' | 'wish';

function SearchOld({ onPick, disabled }: { onPick: (track: Track) => void; disabled: boolean }) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<Track[] | null>(null);

  // 打字停 300ms 才搜尋
  useEffect(() => {
    if (!q.trim()) {
      setResults(null);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetchTracks({ q: q.trim(), sort: 'popular', pageSize: 8 }, controller.signal)
        .then(page => setResults(page.results))
        .catch(() => {});
    }, 300);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [q]);

  return (
    <div className="sf-request-search">
      <input
        className="sf-search"
        type="search"
        value={q}
        onChange={e => setQ(e.target.value)}
        placeholder="搜尋舊曲：作品、曲名、製作者或 DVD 編號"
        aria-label="搜尋舊曲"
      />
      {results?.length === 0 && <p className="sf-muted">歌單裡找不到，可以用下面的「點還沒人剪過的歌」。</p>}
      {results && results.length > 0 && (
        <ul className="sf-request-results">
          {results.map(t => (
            <li key={t.dvdCode}>
              <span className="sf-song-line">
                <strong>〈{t.title}〉</strong>
                <span className="sf-secondary">{t.songSource}{t.editor && `・${t.editor}`}・<span className="sf-code">{t.dvdCode}</span></span>
              </span>
              <button type="button" className="sf-button" disabled={disabled} onClick={() => { onPick(t); setQ(''); }}>
                點這首
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function WishForm({ onSubmit, disabled }: { onSubmit: (input: RequestInput) => Promise<boolean>; disabled: boolean }) {
  const [form, setForm] = useState({ songSource: '', title: '', visualSource: '', link: '', note: '' });
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim()]));
    if (await onSubmit(trimmed)) setForm({ songSource: '', title: '', visualSource: '', link: '', note: '' });
  };
  return (
    <form className="sf-form sf-wish-form" onSubmit={submit}>
      <p className="sf-hint">歌單裡還沒有的歌會列進「徵剪輯」，給大家報曲時參考。歌單裡其實有的話會自動對到舊曲。</p>
      <div className="sf-form-grid">
        <label>歌曲出處 *<input required maxLength={255} value={form.songSource} onChange={set('songSource')} placeholder="作品名稱；非 ACGN 填「一般曲」" /></label>
        <label>曲名 *<input required maxLength={255} value={form.title} onChange={set('title')} /></label>
        <label>想看的畫面（選填）<input maxLength={255} value={form.visualSource} onChange={set('visualSource')} /></label>
        <label>歌曲連結（選填）<input type="url" value={form.link} onChange={set('link')} placeholder="https://" /></label>
      </div>
      <label>備註（選填）<input maxLength={200} value={form.note} onChange={set('note')} placeholder="例如想聽完整版" /></label>
      <div className="sf-form-actions">
        <button type="submit" className="sf-button is-primary" disabled={disabled}>點這首</button>
      </div>
    </form>
  );
}

function RequestRow({ req, festival, onVote, onDelete }: {
  req: SongRequest; festival: RequestFestival;
  onVote: (req: SongRequest) => void; onDelete: (req: SongRequest) => void;
}) {
  const { isAuthenticated } = useAuth();
  // 點歌的人自己那票不能收回；截止後也不能再 +1
  const canToggle = isAuthenticated && festival.open && !req.isMine;
  return (
    <li className="sf-card sf-request">
      <button
        type="button"
        className={`sf-vote${req.voted ? ' is-voted' : ''}`}
        disabled={!canToggle}
        onClick={() => onVote(req)}
        aria-pressed={req.voted}
        aria-label={`${req.voted ? '收回' : ''} +1〈${req.title}〉，目前 ${req.votes} 票`}
        title={!isAuthenticated ? '登入後可以 +1' : req.isMine ? '你點的歌' : undefined}
      >
        <span>+1</span>
        <strong>{req.votes}</strong>
      </button>
      <div className="sf-request-main">
        <div className="sf-song-line">
          <strong>〈{req.title}〉</strong>
          <span className="sf-secondary">
            {req.songSource}
            {req.visualSource && req.visualSource !== req.songSource && `／${req.visualSource}`}
          </span>
        </div>
        <div className="sf-request-meta">
          {req.kind === 'old' ? (
            <>
              <span className="sf-tag">舊曲</span>
              <span className="sf-code">{req.dvdCode}</span>
              {req.editor && <span>{req.editor}</span>}
              {req.duration !== null && <span>{formatDuration(req.duration)}</span>}
              <span>{req.lastPlayed ? `上次播 ${formatDate(req.lastPlayed)}` : '還沒播過'}</span>
            </>
          ) : (
            <span className="sf-tag is-wish">徵剪輯</span>
          )}
          {req.submitted && <span className="sf-tag is-done">有人報了</span>}
          {req.scheduledIn.length > 0 && <span className="sf-tag is-done">排進 {req.scheduledIn.join('、')}</span>}
          {req.link && <a href={req.link} target="_blank" rel="noreferrer">歌曲連結</a>}
        </div>
        {req.note && <p className="sf-request-note">{req.note}</p>}
        <div className="sf-request-meta sf-muted">
          <span>{req.requestedBy || '（帳號已刪除）'} 點的・{formatDateTime(req.createdAt)}</span>
          {req.canDelete && (
            <button type="button" className="sf-link-button is-danger" onClick={() => onDelete(req)}>刪除</button>
          )}
        </div>
      </div>
    </li>
  );
}

export default function Requests() {
  const { isAuthenticated } = useAuth();
  const [festival, setFestival] = useState<RequestFestival | null | undefined>(undefined);
  const [requests, setRequests] = useState<SongRequest[]>([]);
  const [wishes, setWishes] = useState<Wish[] | null>(null);
  const [filter, setFilter] = useState<Filter>('all');
  const [showWishForm, setShowWishForm] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    fetchRequests()
      .then(res => { setFestival(res.festival); setRequests(res.requests); })
      .catch(() => setError('載入失敗，請稍後再試'));
  }, []);

  // 登入狀態改變時重抓：「我有沒有 +1」跟登入的人有關
  useEffect(load, [load, isAuthenticated]);
  useEffect(() => { fetchWishes().then(setWishes).catch(() => setWishes([])); }, []);

  const submit = async (input: RequestInput): Promise<boolean> => {
    if (!festival) return false;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await createRequest({ ...input, festival: festival.id });
      setNotice(res.created
        ? `已點〈${res.request.title}〉。`
        : res.request.isMine
          ? `你已經點過〈${res.request.title}〉了。`
          : `〈${res.request.title}〉已經有人點過了，幫你 +1（不算在 ${festival.limit} 首裡）。`);
      setFestival(res.festival);
      load();
      return true;
    } catch (err) {
      setError(apiErrorMessage(err, '點歌失敗'));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const vote = async (req: SongRequest) => {
    try {
      const res = await voteRequest(req.id, !req.voted);
      setRequests(list => list.map(r => (r.id === req.id ? { ...r, ...res } : r)));
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const remove = async (req: SongRequest) => {
    if (!window.confirm(`刪除〈${req.title}〉？`)) return;
    try {
      await deleteRequest(req.id);
      load();
    } catch (err) {
      setError(apiErrorMessage(err, '刪除失敗'));
    }
  };

  const shown = requests.filter(r => filter === 'all' || r.kind === filter);
  const full = festival ? festival.myCount >= festival.limit : false;

  return (
    <SongfestLayout>
      <p className="sf-lead">
        想在歌謠祭聽到哪首歌？從舊曲清單點一首，或點還沒人剪過的歌。別人點過的歌按 +1，排歌組會參考票數排歌。
      </p>

      {festival === undefined && !error && <p className="sf-muted">載入中…</p>}
      {festival === null && <div className="sf-card sf-empty">目前沒有準備中的歌謠祭。</div>}

      {festival && (
        <section className="sf-card sf-upcoming">
          <div className="sf-upcoming-head">
            <h2>{festival.name} 點歌</h2>
            <span className="sf-badge">{festival.open ? '開放中' : '已截止'}</span>
          </div>
          <dl className="sf-upcoming-meta">
            <div><dt>活動日期</dt><dd>{formatDate(festival.date, true)}</dd></div>
            <div><dt>點歌截止</dt><dd>{festival.deadline ? formatDateTime(festival.deadline) : '活動前一天'}</dd></div>
            <div><dt>每人上限</dt><dd>{festival.limit} 首（+1 不限）</dd></div>
            {isAuthenticated && <div><dt>你已經點了</dt><dd>{festival.myCount} / {festival.limit} 首</dd></div>}
          </dl>

          {festival.open && !isAuthenticated && (
            <p className="sf-note"><Link to="/login">登入</Link>後就可以點歌和 +1。</p>
          )}
          {festival.open && isAuthenticated && (
            <div className="sf-request-forms">
              {full && <p className="sf-note">你已經點滿 {festival.limit} 首了；還是可以幫別人點的歌 +1，點到別人點過的歌也會變成 +1。</p>}
              <SearchOld onPick={t => void submit({ dvdCode: t.dvdCode })} disabled={busy} />
              <button type="button" className="sf-link-button" onClick={() => setShowWishForm(!showWishForm)} aria-expanded={showWishForm}>
                {showWishForm ? '收起' : '歌單裡找不到？點還沒人剪過的歌 →'}
              </button>
              {showWishForm && <WishForm onSubmit={submit} disabled={busy} />}
            </div>
          )}
          {error && <p className="sf-error" role="alert">{error}</p>}
          {notice && <p className="sf-notice" role="status">{notice}</p>}
        </section>
      )}

      {festival && (
        <section className="sf-section">
          <div className="sf-section-row">
            <h2 className="sf-section-title">點歌清單（{requests.length}）</h2>
            <div className="sf-chips" role="group" aria-label="篩選">
              {([['all', '全部'], ['old', '舊曲'], ['wish', '徵剪輯']] as [Filter, string][]).map(([key, label]) => (
                <button key={key} type="button" className={filter === key ? 'is-active' : ''} onClick={() => setFilter(key)}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          {shown.length === 0 && <div className="sf-card sf-empty">還沒有人點歌，來當第一個！</div>}
          <ol className="sf-request-list">
            {shown.map(req => <RequestRow key={req.id} req={req} festival={festival} onVote={vote} onDelete={remove} />)}
          </ol>
        </section>
      )}

      <section className="sf-section">
        <h2 className="sf-section-title">徵剪輯：歷屆大家想聽、還沒人剪的歌</h2>
        <p className="sf-note sf-muted">
          有人報了或收進歌單就會從這裡消失。想報曲但不知道剪什麼的話，可以從這裡挑（見<Link to="/songfest/submit">新曲投稿</Link>）。
        </p>
        {wishes === null && <p className="sf-muted">載入中…</p>}
        {wishes?.length === 0 && <div className="sf-card sf-empty">目前沒有。</div>}
        {wishes && wishes.length > 0 && (
          <div className="sf-table-wrap sf-card">
            <table className="sf-table">
              <thead><tr><th>票數</th><th>歌曲出處</th><th>曲名</th><th>備註</th><th>最近一次被點</th></tr></thead>
              <tbody>
                {wishes.map(w => (
                  <tr key={`${w.songSource}|${w.title}`}>
                    <td data-label="票數">{w.votes}</td>
                    <td data-label="歌曲出處">{w.songSource}</td>
                    <td data-label="曲名">{w.link ? <a href={w.link} target="_blank" rel="noreferrer">{w.title}</a> : w.title}</td>
                    <td data-label="備註">{[w.visualSource && `畫面：${w.visualSource}`, w.note].filter(Boolean).join('・')}</td>
                    <td data-label="最近一次">{w.lastFestival}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </SongfestLayout>
  );
}
