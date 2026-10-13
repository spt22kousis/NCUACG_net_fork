// frontend/src/pages/songfest/Submit.tsx
// 新曲投稿：取代原本的 Google 試算表回報串。上方是截止時間與規定，下方分「我的投稿」與「回報串」。
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import SongfestLayout from './SongfestLayout';
import SubmissionForm from './SubmissionForm';
import CommentThread from './CommentThread';
import { useAuth } from '../../contexts/auth';
import {
  FIVE_SEC_LABEL, STATUS_LABEL, apiErrorMessage, deleteSubmission, fetchActiveFestival, fetchMySubmissions,
  fetchReportThread, formatDate, formatDateTime, formatDuration, isPast, withdrawSubmission,
  fetchMyLibraryConsent, setLibraryConsent,
  type ActiveFestival, type LibraryConsentItem, type MySubmission, type SongfestFestival, type SubmissionPublic,
} from '../../api/songfest';

export function DeadlineList({ festival, guest = false }: { festival: SongfestFestival; guest?: boolean }) {
  const items = guest
    ? [{ label: '亂入曲截止', at: festival.guestDeadline }]
    : [
        { label: '報曲截止', at: festival.reportDeadline },
        { label: '窗歌截止', at: festival.withdrawDeadline },
        { label: '新曲與 5 秒畫面繳交截止', at: festival.uploadDeadline },
      ];
  return (
    <ul className="sf-deadlines">
      {items.map(item => (
        <li key={item.label} className={isPast(item.at) ? 'is-past' : undefined}>
          <span>{item.label}</span>
          <strong>{formatDateTime(item.at)}</strong>
          {isPast(item.at) && <em>已截止</em>}
        </li>
      ))}
    </ul>
  );
}

function StatusBadge({ status }: { status: MySubmission['status'] }) {
  return <span className={`sf-status is-${status}`}>{STATUS_LABEL[status]}</span>;
}

function SongLine({ sub }: { sub: SubmissionPublic }) {
  const sources = sub.visualSource && sub.visualSource !== sub.songSource
    ? `${sub.songSource}（畫面：${sub.visualSource}）`
    : sub.songSource;
  return (
    <div className="sf-song-line">
      <strong>〈{sub.title}〉</strong>
      <span>{sources}{sub.artist && ` · ${sub.artist}`}</span>
    </div>
  );
}

interface MyCardProps {
  sub: MySubmission;
  festival: SongfestFestival;
  all: MySubmission[];
  onChanged: () => void;
}

function MySubmissionCard({ sub, festival, all, onChanged }: MyCardProps) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const perms = sub.permissions;
  const chained = all.find(s => s.id === sub.chainWith);

  const remove = async () => {
    if (!window.confirm(`確定要刪除〈${sub.title}〉嗎？報曲截止前刪除不會有罰則。`)) return;
    try {
      await deleteSubmission(sub.id);
      onChanged();
    } catch (err) {
      setError(apiErrorMessage(err, '刪除失敗'));
    }
  };

  const withdraw = async () => {
    const warning = perms.withdrawIsLate
      ? '已經過了窗歌截止，現在窗歌會被記罰則：下次歌謠祭禁止報曲 1 次。確定要窗歌嗎？'
      : `確定要窗歌〈${sub.title}〉嗎？窗歌後不能復原。`;
    if (!window.confirm(warning)) return;
    try {
      await withdrawSubmission(sub.id);
      onChanged();
    } catch (err) {
      setError(apiErrorMessage(err, '窗歌失敗'));
    }
  };

  if (editing) {
    return (
      <SubmissionForm
        festival={festival}
        initial={sub}
        ownSubmissions={all}
        onSaved={() => { setEditing(false); onChanged(); }}
        onCancel={() => setEditing(false)}
      />
    );
  }

  return (
    <article className={`sf-card sf-submission${sub.status === 'withdrawn' || sub.status === 'rejected' ? ' is-inactive' : ''}`}>
      <header className="sf-submission-head">
        <SongLine sub={sub} />
        <StatusBadge status={sub.status} />
      </header>
      <dl className="sf-submission-meta">
        <div><dt>投稿</dt><dd>{sub.sourceLabel}{sub.isBackup && '（備曲）'} · {sub.editorName}</dd></div>
        <div><dt>長度</dt><dd>{sub.duration ? formatDuration(sub.duration) : '未填'}</dd></div>
        <div><dt>5 秒畫面</dt><dd>{FIVE_SEC_LABEL[sub.fiveSecStatus]}</dd></div>
        {chained && <div><dt>連曲</dt><dd>〈{chained.title}〉</dd></div>}
        {sub.status !== 'withdrawn' && sub.status !== 'rejected' && (
          <div>
            <dt>繳交截止</dt>
            <dd>{formatDateTime(sub.uploadDeadline)}{sub.extendedUntil && '（已延期）'}</dd>
          </div>
        )}
      </dl>
      {sub.status === 'overdue' && (
        <p className="sf-error">已經過了繳交截止還沒上傳，視同逾期窗歌。需要延期請找排歌組。</p>
      )}
      {sub.status === 'rejected' && sub.rejectReason && <p className="sf-error">退件原因：{sub.rejectReason}</p>}
      {error && <p className="sf-error">{error}</p>}
      <div className="sf-form-actions">
        {perms.canEditDetails && (
          <button type="button" className="sf-button is-primary" onClick={() => setEditing(true)}>
            {perms.canEditSong ? '修改／繳交' : '繳交／修改說明'}
          </button>
        )}
        {perms.canDelete && <button type="button" className="sf-button" onClick={remove}>刪除</button>}
        {perms.canWithdraw && (
          <button type="button" className={`sf-button${perms.withdrawIsLate ? ' is-danger' : ''}`} onClick={withdraw}>
            窗歌{perms.withdrawIsLate && '（會記罰則）'}
          </button>
        )}
      </div>
    </article>
  );
}

function ThreadRow({ sub }: { sub: SubmissionPublic }) {
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(sub.commentCount);
  return (
    <li className={`sf-thread-row${sub.status === 'withdrawn' || sub.status === 'rejected' ? ' is-inactive' : ''}`}>
      <div className="sf-thread-main">
        <SongLine sub={sub} />
        <div className="sf-thread-meta">
          <span>{sub.editorName}{sub.isMine && '（我）'}</span>
          <span className="sf-muted">{sub.sourceLabel}{sub.isBackup && '（備曲）'}</span>
          {sub.fiveSec && <span className="sf-muted">5 秒</span>}
          <StatusBadge status={sub.status} />
        </div>
        {sub.attributes && <p className="sf-thread-note">{sub.attributes}</p>}
        {sub.remarks && <p className="sf-thread-note sf-muted">{sub.remarks}</p>}
        <button type="button" className="sf-link-button" onClick={() => setOpen(o => !o)} aria-expanded={open}>
          閒聊（{count}）{open ? '▲' : '▼'}
        </button>
      </div>
      {open && <CommentThread submissionId={sub.id} onCountChange={setCount} />}
    </li>
  );
}

/** 活動結束後的「入歌單回報」：同意的新曲之後可能以舊曲形式在歌謠祭播出 */
function LibraryConsentCard() {
  const [items, setItems] = useState<LibraryConsentItem[]>([]);

  useEffect(() => {
    fetchMyLibraryConsent().then(setItems).catch(() => setItems([]));
  }, []);

  if (items.length === 0) return null;
  const toggle = async (item: LibraryConsentItem) => {
    await setLibraryConsent(item.submissionId, !item.consent);
    setItems(items.map(i => (i.submissionId === item.submissionId ? { ...i, consent: !i.consent } : i)));
  };
  return (
    <section className="sf-card sf-festival-panel">
      <h2>入歌單回報</h2>
      <p className="sf-hint">勾選同意的歌會收進中央動畫社歌單，之後可能在歌謠祭以舊曲的形式播出。</p>
      {items.map(item => (
        <label key={item.submissionId} className="sf-check">
          <input type="checkbox" checked={item.consent} onChange={() => void toggle(item)} />
          {item.festivalName}〈{item.title}〉
        </label>
      ))}
    </section>
  );
}

export default function Submit() {
  const { isAuthenticated } = useAuth();
  const [active, setActive] = useState<ActiveFestival | null>(null);
  const [mine, setMine] = useState<MySubmission[]>([]);
  const [thread, setThread] = useState<SubmissionPublic[]>([]);
  const [tab, setTab] = useState<'mine' | 'thread'>('mine');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(false);

  const festival = active?.festival ?? null;

  useEffect(() => {
    fetchActiveFestival().then(setActive).catch(() => setError(true));
  }, [isAuthenticated]);

  const reload = useCallback(() => {
    if (!festival || !isAuthenticated) return;
    fetchMySubmissions(festival.id).then(setMine).catch(() => setError(true));
    fetchReportThread(festival.id).then(setThread).catch(() => setError(true));
  }, [festival, isAuthenticated]);

  useEffect(reload, [reload]);

  const reportOpen = festival ? festival.reportOpen.member || festival.reportOpen.partner : false;
  const banReason = active?.viewer?.banReason ?? null;
  const activeCount = thread.filter(s => s.status !== 'withdrawn' && s.status !== 'rejected').length;

  return (
    <SongfestLayout>
      <p className="sf-lead">
        報曲、繳交、窗歌都在這裡，取代原本的 Google 試算表回報串。報曲即視為同意遵守出曲規定，並服從排歌組的判定。
      </p>

      {error && <p className="sf-error">載入失敗，請稍後再試。</p>}
      {!error && active === null && <p className="sf-muted">載入中…</p>}
      {/* 活動結束後下一場可能還沒建立，所以放在場次之外 */}
      {isAuthenticated && <LibraryConsentCard />}
      {active !== null && festival === null && (
        <div className="sf-card sf-empty">目前沒有準備中的歌謠祭。下一場的投稿時間會公告在社團 Discord。</div>
      )}

      {festival && (
        <>
          <section className="sf-card sf-festival-panel">
            <h2>{festival.name}歌謠祭 · {formatDate(festival.date, true)}</h2>
            {festival.reportDeadline ? <DeadlineList festival={festival} /> : <p className="sf-muted">這一場還沒開放投稿。</p>}
            <details className="sf-rules">
              <summary>出曲規定</summary>
              {festival.rules
                ? <p>{festival.rules}</p>
                : <p className="sf-muted">排歌組還沒貼上這一場的出曲規定，有疑問請先問排歌組。</p>}
            </details>
          </section>

          {!isAuthenticated && (
            <div className="sf-card sf-empty">
              <Link to="/login">登入</Link>後才能報曲、查看回報串。
            </div>
          )}

          {isAuthenticated && (
            <>
              {banReason && <div className="sf-card sf-empty sf-error">{banReason}</div>}

              <div className="sf-toggle sf-tabs-inline" role="tablist">
                <button type="button" role="tab" aria-selected={tab === 'mine'} className={tab === 'mine' ? 'is-active' : ''} onClick={() => setTab('mine')}>
                  我的投稿（{mine.length}）
                </button>
                <button type="button" role="tab" aria-selected={tab === 'thread'} className={tab === 'thread' ? 'is-active' : ''} onClick={() => setTab('thread')}>
                  回報串（{activeCount}）
                </button>
              </div>

              {tab === 'mine' && (
                <section className="sf-section-tight">
                  {reportOpen && !banReason && !creating && (
                    <button type="button" className="sf-button is-primary sf-new-button" onClick={() => setCreating(true)}>
                      ＋ 報曲
                    </button>
                  )}
                  {creating && festival && (
                    <SubmissionForm
                      festival={festival}
                      ownSubmissions={mine}
                      onSaved={() => { setCreating(false); reload(); }}
                      onCancel={() => setCreating(false)}
                    />
                  )}
                  {mine.length === 0 && !creating && (
                    <p className="sf-muted">{reportOpen ? '你這一場還沒有報曲。' : '你這一場沒有報曲。'}</p>
                  )}
                  <div className="sf-submission-list">
                    {mine.map(sub => (
                      <MySubmissionCard key={sub.id} sub={sub} festival={festival} all={mine} onChanged={reload} />
                    ))}
                  </div>
                </section>
              )}

              {tab === 'thread' && (
                <section className="sf-section-tight">
                  <p className="sf-muted sf-note">
                    這一場大家報了哪些歌。不接受兩人報同一首，報曲前可以先看看；亂入曲由排歌組另外處理，不列在這裡。
                  </p>
                  {thread.length === 0 && <p className="sf-muted">還沒有人報曲。</p>}
                  {thread.length > 0 && (
                    <ul className="sf-card sf-thread">
                      {thread.map(sub => <ThreadRow key={sub.id} sub={sub} />)}
                    </ul>
                  )}
                </section>
              )}
            </>
          )}
        </>
      )}
    </SongfestLayout>
  );
}
