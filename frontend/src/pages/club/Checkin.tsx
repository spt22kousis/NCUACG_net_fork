// frontend/src/pages/club/Checkin.tsx
// 活動簽到（管理）：建立簽到、設定簽到時段、給外場掃描連結、看人數、下載名單。
// 掃描本身在 public/scan/index.html（barcoder demo 搬進來的），外場志工用掃描連結打開，不用帳號。
// 學校的 QR code 時數系統照舊，這裡是社團自己的出席紀錄。
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { apiErrorMessage, formatDate, formatDateTime } from '../../api/songfest';
import { fromLocalInput, toLocalInput } from '../../api/club';
import {
  addCheckinSlot, createCheckinEvent, deleteCheckinEvent, deleteCheckinRecord, deleteCheckinSlot,
  downloadCheckinCsv, downloadCheckinStats, fetchCheckinEvent, fetchCheckinEvents, resetScanKey, scanUrl,
  updateCheckinSlot,
  type CheckinEvent, type CheckinEventDetail, type CheckinSlot, type CheckinSources,
} from '../../api/checkin';
import { useAuth } from '../../contexts/auth';
import ClubLayout from './ClubLayout';

const KIND_LABEL: Record<CheckinEvent['kind'], string> = { songfest: '歌謠祭', lesson: '社課', other: '其他' };

function LoginNeeded() {
  return (
    <ClubLayout>
      <p className="sf-card sf-empty">請先<Link to="/login">登入</Link>。活動簽到由幹部、排歌組與社課負責人管理。</p>
    </ClubLayout>
  );
}

// ── 列表與建立 ──────────────────────────────────────────────────────────────

function CustomForm({ onCreated }: { onCreated: (event: CheckinEvent) => void }) {
  const [title, setTitle] = useState('');
  const [rows, setRows] = useState([{ name: '', start: '', end: '' }]);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      onCreated(await createCheckinEvent({
        title: title.trim(),
        slots: rows.map(r => ({ name: r.name.trim(), startsAt: fromLocalInput(r.start) ?? '', endsAt: fromLocalInput(r.end) ?? '' })),
      }));
    } catch (err) {
      setError(apiErrorMessage(err, '建立失敗'));
    }
  };

  const set = (i: number, key: 'name' | 'start' | 'end', value: string) =>
    setRows(rows.map((r, j) => (j === i ? { ...r, [key]: value } : r)));

  return (
    <form className="sf-form" onSubmit={submit}>
      <label>活動名稱 *<input required maxLength={100} value={title} onChange={e => setTitle(e.target.value)} placeholder="例如 社員大會" /></label>
      {rows.map((r, i) => (
        <div key={i} className="sf-form-grid checkin-slot-row">
          <label>場次 *<input required maxLength={50} value={r.name} onChange={e => set(i, 'name', e.target.value)} placeholder="例如 上半場" /></label>
          <label>開始 *<input required type="datetime-local" value={r.start} onChange={e => set(i, 'start', e.target.value)} /></label>
          <label>結束 *<input required type="datetime-local" value={r.end} onChange={e => set(i, 'end', e.target.value)} /></label>
        </div>
      ))}
      {error && <p className="sf-error" role="alert">{error}</p>}
      <div className="sf-form-actions">
        <button type="button" className="sf-button" onClick={() => setRows([...rows, { name: '', start: '', end: '' }])}>＋ 再加一個場次</button>
        <button type="submit" className="sf-button is-primary">建立</button>
      </div>
    </form>
  );
}

export default function Checkin() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [events, setEvents] = useState<CheckinEvent[] | null>(null);
  const [sources, setSources] = useState<CheckinSources | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCustom, setShowCustom] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    fetchCheckinEvents()
      .then(res => { setEvents(res.events); setSources(res.sources); })
      .catch(err => setError(apiErrorMessage(err, '載入失敗')));
  }, [isAuthenticated]);

  if (!isAuthenticated) return <LoginNeeded />;

  const create = async (input: { festival: number } | { lesson: number }) => {
    try {
      const event = await createCheckinEvent(input);
      navigate(`/checkin/${event.id}`);
    } catch (err) {
      setError(apiErrorMessage(err, '建立失敗'));
    }
  };

  const hasSources = sources && (sources.festivals.length > 0 || sources.lessons.length > 0 || sources.custom);

  return (
    <ClubLayout>
      <p className="sf-lead">
        社團自己的出席紀錄（學校的 QR code 時數系統照舊）。建立簽到後，把「掃描連結」傳給外場，用手機或筆電打開就能掃學生證；
        斷網時資料先存在裝置上，連上網路自動上傳。學號只有幹部、該場排歌組與該社課負責人看得到。
      </p>
      {error && <p className="sf-error" role="alert">{error}</p>}
      {events === null && !error && <p className="sf-muted">載入中…</p>}

      {hasSources && (
        <section className="sf-card sf-after-section">
          <h3>建立簽到</h3>
          {sources.festivals.map(f => (
            <div key={`f${f.id}`} className="checkin-source">
              <span><span className="sf-tag">歌謠祭</span> {f.name}（{formatDate(f.date, true)}）・場次照排歌台的時段</span>
              <button type="button" className="sf-button" onClick={() => void create({ festival: f.id })}>建立</button>
            </div>
          ))}
          {sources.lessons.map(l => (
            <div key={`l${l.id}`} className="checkin-source">
              <span><span className="sf-tag">社課</span> {l.title}（{formatDate(l.date, true)}）</span>
              <button type="button" className="sf-button" onClick={() => void create({ lesson: l.id })}>建立</button>
            </div>
          ))}
          {sources.custom && (
            <>
              <button type="button" className="sf-link-button" onClick={() => setShowCustom(!showCustom)} aria-expanded={showCustom}>
                {showCustom ? '收起' : '其他活動（社員大會、社遊…）→'}
              </button>
              {showCustom && <CustomForm onCreated={event => navigate(`/checkin/${event.id}`)} />}
            </>
          )}
        </section>
      )}

      {events && (
        <section className="sf-section">
          <div className="sf-section-row">
            <h2 className="sf-section-title">簽到活動（{events.length}）</h2>
            {events.length > 0 && (
              <button type="button" className="sf-button" onClick={() => void downloadCheckinStats().catch(() => setError('下載失敗'))}>
                下載人數統計（評鑑用）
              </button>
            )}
          </div>
          {events.length === 0 && <p className="sf-card sf-empty">還沒有簽到活動。</p>}
          <div className="lesson-list">
            {events.map(event => (
              <Link key={event.id} to={`/checkin/${event.id}`} className="sf-card checkin-card">
                <div className="lesson-card-head">
                  <span className="lesson-category">{KIND_LABEL[event.kind]}</span>
                  {event.date && <span className="sf-muted">{formatDate(event.date, true)}</span>}
                </div>
                <strong>{event.title}</strong>
                <span className="sf-muted">
                  {event.slots.map(s => `${s.name} ${s.count} 人`).join('・')}
                  {event.slots.length > 1 && `・共 ${event.people} 人`}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </ClubLayout>
  );
}

// ── 單一活動 ────────────────────────────────────────────────────────────────

function SlotRow({ slot, onSave, onDelete }: {
  slot: CheckinSlot; onSave: (input: Parameters<typeof updateCheckinSlot>[1]) => void; onDelete: () => void;
}) {
  // 改完離開欄位就存（跟排歌台的時段設定一樣）
  const save = (key: 'opensAt' | 'closesAt' | 'startsAt' | 'endsAt') => (e: { target: { value: string } }) => {
    const value = fromLocalInput(e.target.value);
    if (value && value !== slot[key]) onSave({ [key]: value });
  };
  return (
    <tr>
      <td className="sf-manage-song">
        <input
          className="checkin-slot-name"
          defaultValue={slot.name}
          maxLength={50}
          aria-label="場次名稱"
          onBlur={e => e.target.value.trim() && e.target.value !== slot.name && onSave({ name: e.target.value.trim() })}
        />
      </td>
      <td data-label="場次時間">
        <input type="datetime-local" defaultValue={toLocalInput(slot.startsAt)} onBlur={save('startsAt')} aria-label="開始" />
        <input type="datetime-local" defaultValue={toLocalInput(slot.endsAt)} onBlur={save('endsAt')} aria-label="結束" />
      </td>
      <td data-label="簽到時段">
        <input type="datetime-local" defaultValue={toLocalInput(slot.opensAt)} onBlur={save('opensAt')} aria-label="開放簽到" />
        <input type="datetime-local" defaultValue={toLocalInput(slot.closesAt)} onBlur={save('closesAt')} aria-label="停止簽到" />
      </td>
      <td data-label="人數"><strong>{slot.count}</strong></td>
      <td>
        <button type="button" className="sf-link-button is-danger" onClick={onDelete}>刪除</button>
      </td>
    </tr>
  );
}

export function CheckinDetail() {
  const { id } = useParams();
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [event, setEvent] = useState<CheckinEventDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [slotFilter, setSlotFilter] = useState<number | ''>('');
  const [copied, setCopied] = useState(false);

  const load = useCallback(() => {
    fetchCheckinEvent(Number(id))
      .then(setEvent)
      .catch(err => setError(apiErrorMessage(err, '載入失敗')));
  }, [id]);

  useEffect(() => {
    if (!isAuthenticated) return;
    load();
    // 活動進行中，人數每 15 秒更新一次
    const timer = window.setInterval(load, 15000);
    return () => window.clearInterval(timer);
  }, [isAuthenticated, load]);

  const records = useMemo(() => (event?.records ?? []).filter(r =>
    (!query || r.studentId.includes(query.trim())) && (!slotFilter || r.slotId === slotFilter),
  ), [event, query, slotFilter]);

  if (!isAuthenticated) return <LoginNeeded />;

  const run = async (action: () => Promise<unknown>, message?: string) => {
    setError(null);
    try {
      await action();
      if (message) setNotice(message);
      load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const copyLink = async () => {
    if (!event) return;
    try {
      await navigator.clipboard.writeText(scanUrl(event));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      window.prompt('複製這個連結：', scanUrl(event));
    }
  };

  const addSlot = () => {
    if (!event) return;
    const last = event.slots[event.slots.length - 1];
    const start = last ? new Date(last.endsAt) : new Date();
    const end = new Date(start.getTime() + 2 * 3600 * 1000);
    void run(() => addCheckinSlot(event.id, { name: `場次 ${event.slots.length + 1}`, startsAt: start.toISOString(), endsAt: end.toISOString() }));
  };

  return (
    <ClubLayout>
      <Link to="/checkin" className="sf-back">← 所有簽到活動</Link>
      {error && <p className="sf-error" role="alert">{error}</p>}
      {notice && <p className="sf-notice" role="status">{notice}</p>}
      {!event && !error && <p className="sf-muted">載入中…</p>}

      {event && (
        <>
          <section className="sf-card sf-upcoming">
            <div className="sf-upcoming-head">
              <h2>{event.title}</h2>
              <span className="sf-badge">{KIND_LABEL[event.kind]}</span>
            </div>
            <dl className="sf-upcoming-meta">
              <div><dt>簽到筆數</dt><dd>{event.total}</dd></div>
              <div><dt>不重複人數</dt><dd>{event.people}</dd></div>
              {event.slots.map(s => <div key={s.id}><dt>{s.name}</dt><dd>{s.count} 人</dd></div>)}
            </dl>
          </section>

          <section className="sf-card sf-after-section">
            <h3>掃描連結</h3>
            <p className="sf-hint">
              傳給外場志工，用手機或筆電的瀏覽器打開（不用登入）。拿到連結的人可以寫入簽到，但只看得到學號末三碼。
              連結外流的話按「重設連結」，舊連結立刻失效。第一次打開要有網路，之後斷網也能掃。
            </p>
            <div className="checkin-link">
              <input readOnly value={scanUrl(event)} onFocus={e => e.target.select()} aria-label="掃描連結" />
              <button type="button" className="sf-button is-primary" onClick={() => void copyLink()}>{copied ? '已複製 ✓' : '複製連結'}</button>
              <a className="sf-button" href={scanUrl(event)} target="_blank" rel="noreferrer">打開掃描頁</a>
              <button
                type="button"
                className="sf-button is-danger"
                onClick={() => {
                  if (window.confirm('重設後，外場手上的舊連結會立刻失效（已經掃的資料要等他們換新連結才傳得上來）。確定嗎？')) {
                    void run(() => resetScanKey(event.id), '已重設，請把新連結傳給外場。');
                  }
                }}
              >
                重設連結
              </button>
            </div>
          </section>

          <section className="sf-card sf-after-section">
            <h3>場次與簽到時段</h3>
            <p className="sf-hint">
              只有在「簽到時段」內掃描才算數，預設是整場。例如想讓觀眾提早 10 分鐘簽到，就把開放簽到往前調。改完離開欄位就會儲存。
            </p>
            <div className="sf-table-wrap">
              <table className="sf-manage-table checkin-slots">
                <thead><tr><th>場次</th><th>開始／結束</th><th>開放／停止簽到</th><th>人數</th><th></th></tr></thead>
                <tbody>
                  {event.slots.map(slot => (
                    <SlotRow
                      key={`${slot.id}-${slot.opensAt}-${slot.closesAt}-${slot.startsAt}-${slot.endsAt}`}
                      slot={slot}
                      onSave={input => void run(() => updateCheckinSlot(slot.id, input), '已儲存。')}
                      onDelete={() => {
                        if (window.confirm(`刪除「${slot.name}」？這個場次的 ${slot.count} 筆簽到會一起刪掉。`)) {
                          void run(() => deleteCheckinSlot(slot.id));
                        }
                      }}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <div className="sf-form-actions sf-after-actions">
              <button type="button" className="sf-button" onClick={addSlot}>＋ 加一個場次</button>
            </div>
          </section>

          <section className="sf-card sf-after-section">
            <div className="sf-section-row">
              <h3>簽到紀錄（{records.length}）</h3>
              <div className="sf-form-actions">
                <button type="button" className="sf-button" onClick={() => void downloadCheckinCsv(event, 'detail').catch(() => setError('下載失敗'))}>下載明細</button>
                <button type="button" className="sf-button" onClick={() => void downloadCheckinCsv(event, 'summary').catch(() => setError('下載失敗'))}>下載彙整</button>
              </div>
            </div>
            <p className="sf-hint">明細與彙整的欄位跟原本 barcoder 匯出的 CSV 一樣。同一場同一個學號只會留第一筆。</p>
            <div className="sf-filter-row checkin-filter">
              <input className="sf-search" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="搜尋學號" aria-label="搜尋學號" />
              <select value={slotFilter} onChange={e => setSlotFilter(e.target.value ? Number(e.target.value) : '')} aria-label="篩選場次">
                <option value="">全部場次</option>
                {event.slots.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            {records.length === 0 ? <p className="sf-muted">還沒有紀錄。</p> : (
              <div className="sf-table-wrap">
                <table className="sf-manage-table">
                  <thead><tr><th>學號</th><th>場次</th><th>時間</th><th>來源</th><th></th></tr></thead>
                  <tbody>
                    {records.map(r => (
                      <tr key={r.id}>
                        <td className="sf-code">{r.studentId}</td>
                        <td data-label="場次">{r.slotName}</td>
                        <td data-label="時間">{formatDateTime(r.scannedAt)}</td>
                        <td data-label="來源">{r.source}</td>
                        <td>
                          <button
                            type="button"
                            className="sf-link-button is-danger"
                            onClick={() => window.confirm(`刪除 ${r.studentId} 在「${r.slotName}」的簽到？`) && void run(() => deleteCheckinRecord(r.id))}
                          >
                            刪除
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <div className="sf-form-actions sf-after-actions">
            <button
              type="button"
              className="sf-button is-danger"
              onClick={() => {
                if (window.confirm(`刪除「${event.title}」的簽到？${event.total} 筆紀錄會一起刪掉，找不回來。`)) {
                  void deleteCheckinEvent(event.id).then(() => navigate('/checkin')).catch(err => setError(apiErrorMessage(err)));
                }
              }}
            >
              刪除這個簽到活動
            </button>
          </div>
        </>
      )}
    </ClubLayout>
  );
}
