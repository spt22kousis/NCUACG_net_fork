// frontend/src/pages/songfest/Manage.tsx
// 排歌組總覽：所有投稿的繳交狀況、自動提醒（撞曲、撞作品、上一場播過…）、延期／退件／免除罰則、
// 匯出 CSV、催繳名單、匯入亂入曲 Google 表單。換歌、補報這類例外請到 Django 後台。
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import SongfestLayout from './SongfestLayout';
import { DeadlineList } from './Submit';
import { useAuth } from '../../contexts/auth';
import { ADMIN_URL } from '../../config';
import {
  FIVE_SEC_LABEL, STATUS_LABEL, apiErrorMessage, downloadSubmissionCsv, fetchManageFestivals, fetchManageOverview,
  formatDate, formatDateTime, formatDuration, formatLongDuration, importGuestForm, parseDuration,
  staffUpdateSubmission, todayIso,
  type ManageFestival, type ManageOverview, type StaffSubmission, type StaffUpdate, type SubmissionSource,
} from '../../api/songfest';

type RowFilter = 'all' | 'pending' | 'warning' | 'inactive';

const ROW_FILTERS: { value: RowFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'pending', label: '未繳交' },
  { value: 'warning', label: '有提醒' },
  { value: 'inactive', label: '窗歌／退件／未入選' },
];

const isInactive = (s: StaffSubmission) => s.status === 'withdrawn' || s.status === 'rejected';

/** 亂入曲由排歌組挑選，沒選上的叫「未入選」而不是「退件」 */
const statusLabel = (s: StaffSubmission) =>
  s.source === 'guest' && s.status === 'rejected' ? '未入選' : STATUS_LABEL[s.status];

function matches(sub: StaffSubmission, filter: RowFilter): boolean {
  if (filter === 'pending') return sub.status === 'reported' || sub.status === 'overdue';
  if (filter === 'warning') return sub.warnings.length > 0;
  if (filter === 'inactive') return isInactive(sub);
  return true;
}

/** ISO → <input type="datetime-local"> 要的本地時間字串 */
function toLocalInput(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** 依製作者整理還沒交的歌與 5 秒畫面，貼到 Discord 催繳 */
function buildReminder(data: ManageOverview): string {
  const group = (subs: StaffSubmission[]) => {
    const byName = new Map<string, string[]>();
    for (const s of subs) byName.set(s.editorName, [...(byName.get(s.editorName) ?? []), `〈${s.title}〉`]);
    return [...byName.entries()].map(([name, titles]) => `${name}：${titles.join('、')}`);
  };
  const songs = data.submissions.filter(s => s.status === 'reported' && s.source !== 'guest');
  const fiveSec = data.submissions.filter(s => s.fiveSecStatus === 'pending' && s.source !== 'guest');
  const lines = [`【${data.festival.name}歌謠祭】新曲與 5 秒畫面繳交截止：${formatDateTime(data.festival.uploadDeadline)}`];
  if (songs.length) lines.push('', '還沒繳交新曲：', ...group(songs));
  if (fiveSec.length) lines.push('', '還沒繳交 5 秒畫面：', ...group(fiveSec));
  if (!songs.length && !fiveSec.length) lines.push('', '大家都交齊了！');
  return lines.join('\n');
}

interface RowProps {
  sub: StaffSubmission;
  expanded: boolean;
  onToggle: () => void;
  onUpdate: (id: number, input: StaffUpdate) => Promise<void>;
}

function SubmissionRow({ sub, expanded, onToggle, onUpdate }: RowProps) {
  const [duration, setDuration] = useState(sub.duration ? formatDuration(sub.duration) : '');
  const [extension, setExtension] = useState(toLocalInput(sub.extendedUntil));

  const saveDuration = () => {
    const seconds = parseDuration(duration);
    if (duration.trim() && seconds === null) return;
    if (seconds !== sub.duration) void onUpdate(sub.id, { duration: seconds });
  };

  const reject = () => {
    const reason = window.prompt(
      sub.source === 'guest' ? `〈${sub.title}〉不入選的原因（排歌組內部紀錄）` : `退件〈${sub.title}〉的原因（投稿者看得到）`,
    );
    if (reason !== null) void onUpdate(sub.id, { isRejected: true, rejectReason: reason });
  };

  return (
    <>
      <tr className={`${isInactive(sub) ? 'is-inactive' : ''}${expanded ? ' is-expanded' : ''}`}>
        <td data-label="來源">{sub.sourceLabel}{sub.isBackup && <span className="sf-tag">備曲</span>}</td>
        <td data-label="製作者">{sub.editorName}</td>
        <td className="sf-manage-song">
          <button type="button" className="sf-link-button" onClick={onToggle} aria-expanded={expanded}>
            〈{sub.title}〉
          </button>
          <span className="sf-secondary">
            {sub.songSource}{sub.visualSource && sub.visualSource !== sub.songSource && `（畫面：${sub.visualSource}）`}
          </span>
        </td>
        <td data-label="長度">
          <input
            className="sf-duration-input"
            value={duration}
            onChange={e => setDuration(e.target.value)}
            onBlur={saveDuration}
            placeholder="未填"
            aria-label={`〈${sub.title}〉長度`}
          />
        </td>
        <td data-label="狀態">
          <span className={`sf-status is-${sub.status}`}>{statusLabel(sub)}</span>
          {sub.isOffense && <span className="sf-tag is-danger">罰則</span>}
        </td>
        <td data-label="5 秒">{FIVE_SEC_LABEL[sub.fiveSecStatus]}</td>
        <td data-label="檔案已確認">
          <input
            type="checkbox"
            checked={sub.fileChecked}
            disabled={sub.status !== 'uploaded'}
            onChange={e => void onUpdate(sub.id, { fileChecked: e.target.checked })}
            aria-label={`確認〈${sub.title}〉的檔案`}
          />
        </td>
        <td className="sf-manage-warnings">
          {sub.warnings.map(w => <span key={w.code + w.message} className="sf-warning">{w.message}</span>)}
        </td>
      </tr>
      {expanded && (
        <tr className="sf-manage-detail">
          <td colSpan={8}>
            <dl>
              {sub.submitterName && <div><dt>投稿帳號</dt><dd>{sub.submitterName}</dd></div>}
              {sub.contactEmail && <div><dt>聯絡信箱</dt><dd>{sub.contactEmail}</dd></div>}
              {sub.artist && <div><dt>原唱</dt><dd>{sub.artist}</dd></div>}
              {sub.attributes && <div><dt>畫面屬性</dt><dd>{sub.attributes}</dd></div>}
              {sub.songLink && <div><dt>歌曲連結</dt><dd>{sub.songLink}</dd></div>}
              {sub.remarks && <div><dt>備註</dt><dd>{sub.remarks}</dd></div>}
              <div>
                <dt>檔案</dt>
                <dd>
                  {sub.fileLink
                    ? <a href={sub.fileLink} target="_blank" rel="noreferrer">開啟</a>
                    : '未繳交'}
                  {sub.uploadedAt && `（${formatDateTime(sub.uploadedAt)} 繳交）`}
                </dd>
              </div>
              {sub.fiveSec && (
                <div>
                  <dt>5 秒畫面</dt>
                  <dd>
                    {sub.fiveSecLink ? <a href={sub.fiveSecLink} target="_blank" rel="noreferrer">開啟</a> : '未繳交'}
                  </dd>
                </div>
              )}
              {sub.guestMessage && <div><dt>想說的話</dt><dd>{sub.guestMessage}</dd></div>}
              {sub.source === 'guest' && <div><dt>收進歌單</dt><dd>{sub.libraryConsent ? '同意' : '不同意'}</dd></div>}
              {sub.rejectReason && <div><dt>{sub.source === 'guest' ? '未入選原因' : '退件原因'}</dt><dd>{sub.rejectReason}</dd></div>}
            </dl>
            <div className="sf-manage-actions">
              {!isInactive(sub) && (
                <label>
                  延後繳交到
                  <input type="datetime-local" value={extension} onChange={e => setExtension(e.target.value)} />
                  {(extension || sub.extendedUntil) && (
                    <button
                      type="button"
                      className="sf-button"
                      onClick={() => void onUpdate(sub.id, { extendedUntil: extension ? new Date(extension).toISOString() : null })}
                    >
                      {extension ? '儲存延期' : '取消延期'}
                    </button>
                  )}
                </label>
              )}
              {sub.status === 'rejected'
                ? <button type="button" className="sf-button" onClick={() => void onUpdate(sub.id, { isRejected: false })}>
                    {sub.source === 'guest' ? '改為入選' : '取消退件'}
                  </button>
                : sub.status !== 'withdrawn' && (
                  <button type="button" className="sf-button is-danger" onClick={reject}>
                    {sub.source === 'guest' ? '不入選' : '退件'}
                  </button>
                )}
              {(sub.isOffense || sub.penaltyWaived) && (
                <label className="sf-check">
                  <input
                    type="checkbox"
                    checked={sub.penaltyWaived}
                    onChange={e => void onUpdate(sub.id, { penaltyWaived: e.target.checked })}
                  />
                  免除罰則（下次可以報曲）
                </label>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function Manage() {
  const { isAuthenticated, user } = useAuth();
  const [festivals, setFestivals] = useState<ManageFestival[] | null>(null);
  const [festivalId, setFestivalId] = useState<number | null>(null);
  const [data, setData] = useState<ManageOverview | null>(null);
  const [filter, setFilter] = useState<RowFilter>('all');
  const [sourceFilter, setSourceFilter] = useState<'all' | SubmissionSource>('all');
  const [expanded, setExpanded] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reminder, setReminder] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    fetchManageFestivals()
      .then(list => {
        setFestivals(list);
        // 預設選最近一場還沒舉辦的；都辦完了就選最新的
        const today = todayIso();
        const upcoming = list.filter(f => f.date >= today).sort((a, b) => a.date.localeCompare(b.date));
        setFestivalId((upcoming[0] ?? list[0])?.id ?? null);
      })
      .catch(() => setError('載入失敗'));
  }, [isAuthenticated]);

  const reload = useCallback(() => {
    if (festivalId === null) return;
    fetchManageOverview(festivalId)
      .then(res => { setData(res); setError(null); })
      .catch(err => setError(apiErrorMessage(err, '載入失敗')));
  }, [festivalId]);

  useEffect(reload, [reload]);

  const update = async (id: number, input: StaffUpdate) => {
    try {
      await staffUpdateSubmission(id, input);
      reload(); // 統計與其他列的提醒也可能跟著變
    } catch (err) {
      setError(apiErrorMessage(err, '儲存失敗'));
    }
  };

  const copyReminder = async () => {
    if (!data) return;
    const text = buildReminder(data);
    try {
      await navigator.clipboard.writeText(text);
      setNotice('催繳名單已複製，可以直接貼到 Discord。');
      setReminder(null);
    } catch {
      setReminder(text); // 瀏覽器不允許時改成顯示出來讓人手動複製
    }
  };

  const importGuests = async (file: File | undefined) => {
    if (!file || festivalId === null) return;
    try {
      const report = await importGuestForm(festivalId, file);
      setNotice([...report.lines, ...report.warnings].join(' '));
      reload();
    } catch (err) {
      setError(apiErrorMessage(err, '匯入失敗'));
    } finally {
      if (fileInput.current) fileInput.current.value = '';
    }
  };

  const exportCsv = async () => {
    if (!data) return;
    try {
      await downloadSubmissionCsv(data.festival.id, `${data.festival.name}_新曲.csv`);
    } catch {
      setError('匯出失敗');
    }
  };

  if (!isAuthenticated || !(user?.songfestStaff || user?.role === 'admin' || user?.role === 'superadmin')) {
    return (
      <SongfestLayout>
        <div className="sf-card sf-empty">
          這一頁給排歌組使用。{!isAuthenticated && <><Link to="/login">登入</Link>後再試一次。</>}
          {isAuthenticated && '如果你是這次的排歌組，請幹部在後台的歌謠祭場次把你加進排歌組。'}
        </div>
      </SongfestLayout>
    );
  }

  const rows = (data?.submissions ?? []).filter(
    s => matches(s, filter) && (sourceFilter === 'all' || s.source === sourceFilter),
  );
  const summary = data?.summary;

  return (
    <SongfestLayout>
      <div className="sf-manage-head">
        <label className="sf-sort">
          場次
          <select value={festivalId ?? ''} onChange={e => setFestivalId(Number(e.target.value))}>
            {(festivals ?? []).map(f => <option key={f.id} value={f.id}>{f.name}（{formatDate(f.date)}）</option>)}
          </select>
        </label>
        {festivals?.length === 0 && <span className="sf-muted">你目前沒有負責的場次。</span>}
      </div>

      {error && <p className="sf-error" role="alert">{error}</p>}
      {notice && <p className="sf-notice" role="status">{notice}</p>}

      {data && summary && (
        <>
          <section className="sf-card sf-festival-panel">
            <DeadlineList festival={data.festival} />
          </section>

          <div className="sf-stats">
            <div className="sf-card sf-stat">
              <span>新曲</span>
              <strong>{summary.active}</strong>
              <small>本社 {summary.bySource.member}・{data.festival.partnerName} {summary.bySource.partner}/{summary.partnerLimit}{summary.partnerBackups > 0 && `（備曲 ${summary.partnerBackups}）`}・亂入 {summary.bySource.guest}</small>
            </div>
            <div className="sf-card sf-stat">
              <span>已繳交</span>
              <strong>{summary.uploaded}/{summary.active}</strong>
              <small>{summary.overdue ? `逾期 ${summary.overdue} 首` : '沒有逾期'}</small>
            </div>
            <div className="sf-card sf-stat">
              <span>5 秒畫面</span>
              <strong>{summary.fiveSecUploaded}/{summary.fiveSecRequested}</strong>
              <small>共 {summary.fiveSecRequested * 5} 秒（亂入每人最多 5 秒）</small>
            </div>
            <div className="sf-card sf-stat">
              <span>新曲總長</span>
              <strong>{formatLongDuration(summary.totalDuration)}</strong>
              <small>{summary.missingDuration ? `${summary.missingDuration} 首還沒有長度` : '長度都填了'}</small>
            </div>
            <div className="sf-card sf-stat">
              <span>窗歌／退件</span>
              <strong>{summary.withdrawn}／{summary.rejected}</strong>
              <small>&nbsp;</small>
            </div>
          </div>

          <div className="sf-card sf-filters sf-manage-tools">
            <div className="sf-filter-row">
              <div className="sf-chips" role="group" aria-label="篩選">
                {ROW_FILTERS.map(f => (
                  <button key={f.value} type="button" className={filter === f.value ? 'is-active' : ''} onClick={() => setFilter(f.value)}>
                    {f.label}
                  </button>
                ))}
              </div>
              <label className="sf-sort">
                來源
                <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value as 'all' | SubmissionSource)}>
                  <option value="all">全部</option>
                  <option value="member">本社</option>
                  <option value="partner">{data.festival.partnerName}</option>
                  <option value="guest">亂入</option>
                </select>
              </label>
            </div>
            <div className="sf-form-actions">
              <button type="button" className="sf-button" onClick={copyReminder}>複製催繳名單</button>
              <button type="button" className="sf-button" onClick={exportCsv}>匯出 CSV</button>
              <button type="button" className="sf-button" onClick={() => fileInput.current?.click()}>匯入亂入曲表單</button>
              <input
                ref={fileInput}
                type="file"
                accept=".xlsx"
                hidden
                onChange={e => void importGuests(e.target.files?.[0])}
              />
            </div>
            {reminder && <textarea className="sf-reminder" readOnly rows={8} value={reminder} />}
          </div>

          <p className="sf-muted sf-note">
            點曲名看詳細資料、延期或退件。換歌、補報請到 <a href={`${ADMIN_URL}songfest/submission/`} target="_blank" rel="noreferrer">Django 後台</a>。
          </p>

          {rows.length === 0 && <div className="sf-card sf-empty">沒有符合的投稿。</div>}
          {rows.length > 0 && (
            <div className="sf-card sf-table-wrap">
              <table className="sf-manage-table">
                <thead>
                  <tr>
                    <th>來源</th>
                    <th>製作者</th>
                    <th>歌曲</th>
                    <th>長度</th>
                    <th>狀態</th>
                    <th>5 秒</th>
                    <th>檔案已確認</th>
                    <th>提醒</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(sub => (
                    <SubmissionRow
                      key={`${sub.id}-${sub.duration}-${sub.extendedUntil}`}
                      sub={sub}
                      expanded={expanded === sub.id}
                      onToggle={() => setExpanded(expanded === sub.id ? null : sub.id)}
                      onUpdate={update}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </SongfestLayout>
  );
}
