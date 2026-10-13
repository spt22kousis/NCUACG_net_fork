// frontend/src/pages/songfest/SetlistBoard.tsx
// 排歌台：把新曲、舊曲、CM 排進各時段，即時算總長與每首播完的時刻，標出超時、窗歌、上一場播過等問題。
// 可以拖拉排序（桌機），也可以用 ↑ ↓ 與「移到」（手機）。每個操作都直接存到後端，三個人同時排也不會互相蓋掉。
import { useCallback, useEffect, useState, type DragEvent, type FormEvent } from 'react';
import {
  addEntry, apiErrorMessage, autoDistribute, deleteEntry, downloadSetlist, fetchFillSuggestions, fetchSetlist,
  fetchTracks, formatDuration, formatLongDuration, parseDuration, publishSetlist, updateEntry, updateSession,
  type CustomType, type PoolItem, type SetlistBoard as Board, type SetlistEntry, type SetlistExport,
  type SetlistSession, type SongRequest, type Track,
} from '../../api/songfest';
import { Link } from 'react-router-dom';

type DragPayload = { entryId: number } | { submissionId: number };

const EXPORTS: { type: SetlistExport; label: string; file: string }[] = [
  { type: 'public', label: '對外公開歌單', file: '對外公開歌單.csv' },
  { type: 'workspace', label: '排歌工作區', file: '排歌工作區.csv' },
  { type: 'order', label: '播放順序（播歌用）', file: '播放順序.txt' },
  { type: 'credits', label: '結尾名單（抄歌用）', file: '結尾名單.txt' },
];

function readDrag(e: DragEvent): DragPayload | null {
  try {
    return JSON.parse(e.dataTransfer.getData('application/json')) as DragPayload;
  } catch {
    return null;
  }
}

function startDrag(e: DragEvent, payload: DragPayload) {
  e.dataTransfer.setData('application/json', JSON.stringify(payload));
  e.dataTransfer.effectAllowed = 'move';
}

interface BoardProps {
  festivalId: number;
}

export default function SetlistBoard({ festivalId }: BoardProps) {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    fetchSetlist(festivalId)
      .then(data => { setBoard(data); setError(null); })
      .catch(err => setError(apiErrorMessage(err, '載入失敗')));
  }, [festivalId]);

  useEffect(load, [load]);

  // 其他排歌組成員可能同時在排：切回這個分頁時重新抓一次
  useEffect(() => {
    window.addEventListener('focus', load);
    return () => window.removeEventListener('focus', load);
  }, [load]);

  /** 所有修改都回傳整份排歌台，直接換掉 */
  const run = async (action: () => Promise<Board>, message?: string) => {
    setBusy(true);
    try {
      setBoard(await action());
      setError(null);
      if (message) setNotice(message);
    } catch (err) {
      setError(apiErrorMessage(err, '儲存失敗'));
    } finally {
      setBusy(false);
    }
  };

  const drop = (session: SetlistSession, position?: number) => (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const payload = readDrag(e);
    if (!payload) return;
    if ('entryId' in payload) {
      void run(() => updateEntry(payload.entryId, { sessionId: session.id, position }));
    } else {
      void run(() => addEntry(session.id, { kind: 'new', submissionId: payload.submissionId, position }));
    }
  };

  if (error && !board) return <p className="sf-error">{error}</p>;
  if (!board) return <p className="sf-muted">載入中…</p>;

  const mainSessions = board.sessions.filter(s => !s.isTest);
  const regularPool = board.pool.filter(p => !p.isBackup);
  const backupPool = board.pool.filter(p => p.isBackup);

  const runAuto = () => {
    if (!window.confirm(`把 ${regularPool.length} 首還沒排的新曲平均分到各場？已經排好的不會動。`)) return;
    void run(async () => {
      const res = await autoDistribute(festivalId);
      setNotice(`已排入 ${res.placed} 首，請再調整順序（每場最後一首盡量排最熱的歌）。`);
      return res;
    });
  };

  const togglePublic = async () => {
    const next = !board.festival.setlistPublic;
    if (next && !window.confirm('公布後，所有人都能在「歌單瀏覽」看到這份歌單。確定要公布嗎？')) return;
    try {
      await publishSetlist(festivalId, next);
      load();
      setNotice(next ? '歌單已公布到「歌單瀏覽」。' : '已取消公布。');
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  return (
    <div className="sf-board">
      <div className="sf-card sf-board-toolbar">
        <div className="sf-form-actions">
          <button type="button" className="sf-button is-primary" onClick={runAuto} disabled={busy || regularPool.length === 0}>
            一鍵初排
          </button>
          {EXPORTS.map(x => (
            <button
              key={x.type}
              type="button"
              className="sf-button"
              onClick={() => void downloadSetlist(festivalId, x.type, `${board.festival.name}_${x.file}`).catch(() => setError('匯出失敗'))}
            >
              {x.label}
            </button>
          ))}
          <label className="sf-check sf-publish">
            <input type="checkbox" checked={board.festival.setlistPublic} onChange={() => void togglePublic()} />
            公布到歌單瀏覽
          </label>
          <button type="button" className="sf-button" onClick={load} disabled={busy}>重新整理</button>
        </div>
        {board.warnings.map(w => <p key={w} className="sf-warning">{w}</p>)}
        {error && <p className="sf-error" role="alert">{error}</p>}
        {notice && <p className="sf-notice" role="status">{notice}</p>}
      </div>

      <div className="sf-board-layout">
        <aside className="sf-card sf-pool">
          <h3>還沒排的新曲（{regularPool.length}）</h3>
          <p className="sf-hint">拖到右邊的時段，或選時段後按「加入」。</p>
          {regularPool.length === 0 && <p className="sf-muted">新曲都排好了。</p>}
          {regularPool.map(item => (
            <PoolRow key={item.submissionId} item={item} sessions={mainSessions} onAdd={(sid) => run(() => addEntry(sid, { kind: 'new', submissionId: item.submissionId }))} />
          ))}
          {backupPool.length > 0 && (
            <>
              <h3>{board.festival.partnerName}備曲（{backupPool.length}）</h3>
              <p className="sf-hint">正選未滿 {board.festival.partnerLimit} 首時才補上。</p>
              {backupPool.map(item => (
                <PoolRow key={item.submissionId} item={item} sessions={mainSessions} onAdd={(sid) => run(() => addEntry(sid, { kind: 'new', submissionId: item.submissionId }))} />
              ))}
            </>
          )}

          <h3 className="sf-pool-requests-title">
            點歌（採用 {board.requestStats.adopted}/{board.requestStats.total}）
          </h3>
          <p className="sf-hint">
            社員在<Link to="/songfest/requests">點歌</Link>頁點的歌，依票數排序；排進任一時段就算採用。徵剪輯是歌單裡還沒有的歌，只能參考。
          </p>
          {board.requests.length === 0 && <p className="sf-muted">還沒有人點歌。</p>}
          {board.requests.map(req => (
            <RequestPoolRow
              key={req.id}
              req={req}
              sessions={board.sessions}
              onAdd={sid => run(() => addEntry(sid, { kind: 'old', dvdCode: req.dvdCode ?? '' }))}
            />
          ))}
        </aside>

        <div className="sf-sessions">
          {board.sessions.map(session => (
            <SessionCard
              key={session.id}
              session={session}
              board={board}
              festivalId={festivalId}
              busy={busy}
              run={run}
              onDrop={drop}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function PoolRow({ item, sessions, onAdd }: { item: PoolItem; sessions: SetlistSession[]; onAdd: (sessionId: number) => void }) {
  const [target, setTarget] = useState(sessions[0]?.id ?? 0);
  return (
    <div className="sf-pool-row" draggable onDragStart={e => startDrag(e, { submissionId: item.submissionId })}>
      <div className="sf-song-line">
        <strong>〈{item.title}〉</strong>
        <span>{item.editor} · {item.sourceLabel} · {item.duration ? formatDuration(item.duration) : '沒長度'}{item.chainWith && ' · 連曲'}</span>
      </div>
      <div className="sf-pool-actions">
        <select value={target} onChange={e => setTarget(Number(e.target.value))} aria-label={`〈${item.title}〉要加到哪個時段`}>
          {sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button type="button" className="sf-button" onClick={() => onAdd(target)}>加入</button>
      </div>
    </div>
  );
}

function RequestPoolRow({ req, sessions, onAdd }: { req: SongRequest; sessions: SetlistSession[]; onAdd: (sessionId: number) => void }) {
  const [target, setTarget] = useState(sessions.find(s => !s.isTest)?.id ?? sessions[0]?.id ?? 0);
  return (
    <div className={`sf-pool-row is-request${req.scheduledIn.length ? ' is-adopted' : ''}`}>
      <div className="sf-song-line">
        <strong>〈{req.title}〉</strong>
        <span>
          {req.votes} 票 · {req.kind === 'old'
            ? `${req.dvdCode} · ${formatDuration(req.duration)} · 上次 ${req.lastPlayed ?? '沒播過'}`
            : `徵剪輯${req.submitted ? '（有人報了）' : ''}`}
        </span>
        {req.note && <span>「{req.note}」</span>}
        {req.scheduledIn.length > 0 && <span className="sf-request-adopted">已排進 {req.scheduledIn.join('、')}</span>}
      </div>
      {req.kind === 'old' && (
        <div className="sf-pool-actions">
          <select value={target} onChange={e => setTarget(Number(e.target.value))} aria-label={`〈${req.title}〉要加到哪個時段`}>
            {sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <button type="button" className="sf-button" onClick={() => onAdd(target)}>加入</button>
        </div>
      )}
    </div>
  );
}

interface SessionProps {
  session: SetlistSession;
  board: Board;
  festivalId: number;
  busy: boolean;
  run: (action: () => Promise<Board>, message?: string) => Promise<void>;
  onDrop: (session: SetlistSession, position?: number) => (e: DragEvent) => void;
}

function SessionCard({ session, board, festivalId, busy, run, onDrop }: SessionProps) {
  const limit = session.targetSeconds ? session.targetSeconds + session.toleranceSeconds : null;
  const state = session.over ? 'is-over' : session.under ? 'is-under' : 'is-ok';

  return (
    <section className="sf-card sf-session" onDragOver={e => e.preventDefault()} onDrop={onDrop(session)}>
      <header className="sf-session-head">
        <h3>{session.name}</h3>
        <label className="sf-sort">
          負責
          <select
            value={session.ownerId ?? ''}
            onChange={e => void run(() => updateSession(session.id, { ownerId: e.target.value ? Number(e.target.value) : null }))}
          >
            <option value="">未指定</option>
            {board.staff.map(s => <option key={s.id} value={s.id}>{s.name}（{s.role}）</option>)}
          </select>
        </label>
      </header>

      <div className={`sf-session-total ${state}`}>
        <strong>{formatLongDuration(session.totalSeconds)}</strong>
        {session.targetSeconds ? (
          <span>目標 {formatLongDuration(session.targetSeconds)}，最多 {formatLongDuration(limit!)}</span>
        ) : (
          <span>輪播 {session.rounds} 輪</span>
        )}
      </div>
      <dl className="sf-session-times">
        {session.speechSeconds > 0 && <div><dt>講話</dt><dd>{session.speechAt.slice(0, 5)}</dd></div>}
        <div><dt>開播</dt><dd>{session.startTime}</dd></div>
        <div><dt>預計結束</dt><dd>{session.endAt}</dd></div>
        {session.bufferSeconds > 0 && <div><dt>最晚結束</dt><dd>{session.latestEndAt}</dd></div>}
        {session.endTime && <div><dt>應結束</dt><dd>{session.endTime}</dd></div>}
      </dl>
      {session.warnings.map(w => <p key={w} className="sf-warning">{w}</p>)}

      <SessionSettings session={session} run={run} />

      {session.entries.length === 0 ? (
        <p className="sf-muted sf-drop-hint">把歌拖到這裡，或用下面的「加入舊曲」。</p>
      ) : (
        <ol className="sf-entries">
          {session.entries.map(entry => (
            <EntryRow key={entry.id} entry={entry} session={session} board={board} festivalId={festivalId} busy={busy} run={run} onDrop={onDrop} />
          ))}
        </ol>
      )}

      <AddOldSong session={session} run={run} />
      <AddCustom session={session} run={run} />
    </section>
  );
}

function SessionSettings({ session, run }: { session: SetlistSession; run: SessionProps['run'] }) {
  const save = (input: Parameters<typeof updateSession>[1]) => void run(() => updateSession(session.id, input));
  const minutes = (seconds: number | null) => (seconds ? formatLongDuration(seconds) : '');
  return (
    <details className="sf-session-settings">
      <summary>時段設定</summary>
      <div className="sf-settings-grid">
        <label>開播<input type="time" defaultValue={session.startTime} onBlur={e => e.target.value && save({ startTime: e.target.value })} /></label>
        <label>應結束<input type="time" defaultValue={session.endTime ?? ''} onBlur={e => save({ endTime: e.target.value || null })} /></label>
        <label>
          目標長度
          <input
            defaultValue={minutes(session.targetSeconds)}
            placeholder="1:58:00"
            onBlur={e => save({ targetSeconds: parseDuration(e.target.value) })}
          />
        </label>
        <label>講話（秒）<input type="number" min={0} defaultValue={session.speechSeconds} onBlur={e => save({ speechSeconds: Number(e.target.value) })} /></label>
        <label>預留錯誤處理（秒）<input type="number" min={0} defaultValue={session.bufferSeconds} onBlur={e => save({ bufferSeconds: Number(e.target.value) })} /></label>
        <label>每首誤差（秒）<input type="number" min={0} defaultValue={session.perSongErrorSeconds} onBlur={e => save({ perSongErrorSeconds: Number(e.target.value) })} /></label>
        <label>輪數<input type="number" min={1} defaultValue={session.rounds} onBlur={e => save({ rounds: Number(e.target.value) })} /></label>
      </div>
    </details>
  );
}

interface EntryProps extends Omit<SessionProps, 'session'> {
  entry: SetlistEntry;
  session: SetlistSession;
}

function EntryRow({ entry, session, board, festivalId, busy, run, onDrop }: EntryProps) {
  const [suggestions, setSuggestions] = useState<Track[] | null>(null);
  const needsFill = entry.warnings.some(w => w.includes('窗歌或退件'));
  const last = session.entries.length;
  const move = (input: { sessionId?: number; position?: number }) => void run(() => updateEntry(entry.id, input));
  const sources = entry.visualSource && entry.visualSource !== entry.songSource
    ? `${entry.songSource}（畫面：${entry.visualSource}）`
    : entry.songSource;
  const detail = [sources, entry.dvdCode ?? entry.editor].filter(Boolean).join(' · ');

  const findFill = async () => {
    setSuggestions(await fetchFillSuggestions(festivalId, entry.duration ?? 240));
  };

  return (
    <li
      className={`sf-entry${entry.warnings.length ? ' has-warning' : ''}${needsFill ? ' is-inactive' : ''}`}
      draggable
      onDragStart={e => startDrag(e, { entryId: entry.id })}
      onDragOver={e => e.preventDefault()}
      onDrop={onDrop(session, entry.position)}
    >
      <div className="sf-entry-main">
        <span className="sf-rank" aria-hidden="true">{entry.position}</span>
        <div className="sf-song-line">
          <strong>〈{entry.title}〉</strong>
          {detail && <span>{detail}</span>}
        </div>
        <span className={`sf-kind is-${entry.kind}${entry.source ? ` is-${entry.source}` : ''}`}>{entry.sourceLabel}</span>
        {entry.requestVotes > 0 && (
          <span className="sf-kind is-requested" title="有人點歌（工作區的藍色標記）">點歌 {entry.requestVotes}</span>
        )}
        <span className="sf-entry-time">
          {entry.duration ? formatDuration(entry.duration) : '沒長度'}
          <small>{entry.endsAt.slice(0, 5)} 播完</small>
        </span>
      </div>
      <div className="sf-entry-actions">
        <label className="sf-heat">
          熱度
          <input
            type="number"
            min={0}
            max={10}
            defaultValue={entry.heat ?? ''}
            onBlur={e => {
              const value = e.target.value === '' ? null : Number(e.target.value);
              if (value !== entry.heat) void run(() => updateEntry(entry.id, { heat: value }));
            }}
          />
        </label>
        <button type="button" className="sf-icon-button" disabled={busy || entry.position === 1} onClick={() => move({ position: entry.position - 1 })} aria-label="往上">↑</button>
        <button type="button" className="sf-icon-button" disabled={busy || entry.position === last} onClick={() => move({ position: entry.position + 1 })} aria-label="往下">↓</button>
        <select value="" onChange={e => e.target.value && move({ sessionId: Number(e.target.value) })} aria-label="移到其他時段">
          <option value="">移到…</option>
          {board.sessions.filter(s => s.id !== session.id).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        {needsFill && <button type="button" className="sf-button" onClick={() => void findFill()}>找舊曲補位</button>}
        <button type="button" className="sf-link-button" onClick={() => void run(() => deleteEntry(entry.id))}>移除</button>
      </div>
      {entry.warnings.map(w => <span key={w} className="sf-warning">{w}</span>)}
      {suggestions && (
        <div className="sf-suggestions">
          {suggestions.length === 0 && <p className="sf-muted">找不到長度接近的舊曲，請用下面的「加入舊曲」搜尋。</p>}
          {suggestions.map(t => (
            <button
              key={t.dvdCode}
              type="button"
              className="sf-suggestion"
              onClick={() => { setSuggestions(null); void run(() => updateEntry(entry.id, { dvdCode: t.dvdCode })); }}
            >
              <strong>{t.dvdCode}〈{t.title}〉</strong>
              <span>{t.songSource} · {formatDuration(t.duration)} · 近 4 年 {t.recentPlayCount} 次</span>
            </button>
          ))}
        </div>
      )}
    </li>
  );
}

function AddOldSong({ session, run }: { session: SetlistSession; run: SessionProps['run'] }) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<Track[]>([]);

  useEffect(() => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetchTracks({ q, pageSize: 8 }, controller.signal).then(res => setResults(res.results)).catch(() => {});
    }, 300);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [q]);

  return (
    <div className="sf-add-old">
      <input
        value={q}
        onChange={e => setQ(e.target.value)}
        placeholder={`加入舊曲到${session.name}：搜尋作品、曲名或 DVD 編號`}
        aria-label={`加入舊曲到${session.name}`}
      />
      {results.length > 0 && (
        <div className="sf-suggestions">
          {results.map(t => (
            <button
              key={t.dvdCode}
              type="button"
              className="sf-suggestion"
              onClick={() => { setQ(''); void run(() => addEntry(session.id, { kind: 'old', dvdCode: t.dvdCode })); }}
            >
              <strong>{t.dvdCode}〈{t.title}〉</strong>
              <span>
                {t.songSource} · {formatDuration(t.duration)} · 上次 {t.lastPlayed ?? '沒播過'} · 近 4 年 {t.recentPlayCount} 次
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function AddCustom({ session, run }: { session: SetlistSession; run: SessionProps['run'] }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<CustomType>('cm');
  const [title, setTitle] = useState('');
  const [source, setSource] = useState('');
  const [duration, setDuration] = useState('');

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const seconds = parseDuration(duration);
    // CM 預設放在最前面，其他放最後（結尾影片本來就在最後）
    void run(() => addEntry(session.id, {
      kind: 'custom', customType: type, title: title.trim(), source: source.trim(), duration: seconds,
      position: type === 'cm' ? 1 : undefined,
    }));
    setTitle('');
    setSource('');
    setDuration('');
    setOpen(false);
  };

  if (!open) {
    return (
      <button type="button" className="sf-link-button sf-add-custom-toggle" onClick={() => setOpen(true)}>
        ＋ 加入 CM、結尾影片或其他（例如社外舊曲）
      </button>
    );
  }
  return (
    <form className="sf-add-custom" onSubmit={submit}>
      <select value={type} onChange={e => setType(e.target.value as CustomType)} aria-label="類型">
        <option value="cm">CM</option>
        <option value="credits">結尾影片</option>
        <option value="other">其他</option>
      </select>
      <input required value={title} onChange={e => setTitle(e.target.value)} placeholder="名稱，例如 CM1、春日影" aria-label="名稱" />
      <input value={source} onChange={e => setSource(e.target.value)} placeholder="作品（選填）" aria-label="作品" />
      <input value={duration} onChange={e => setDuration(e.target.value)} placeholder="長度 4:24" aria-label="長度" />
      <button type="submit" className="sf-button is-primary">加入</button>
      <button type="button" className="sf-button" onClick={() => setOpen(false)}>取消</button>
    </form>
  );
}
