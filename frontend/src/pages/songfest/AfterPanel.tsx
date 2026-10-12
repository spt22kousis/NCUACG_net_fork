// frontend/src/pages/songfest/AfterPanel.tsx
// 活動結束後：把排好的歌單寫成播放紀錄、把同意的新曲收進社團歌單（自動編 DVD 編號或匯出名單給社產）。
// 兩件事都可以照舊在試算表做再匯入；網站跟試算表誰後寫入就以誰為準。
import { useCallback, useEffect, useState } from 'react';
import {
  addToLibrary, apiErrorMessage, downloadLibraryCsv, fetchLibraryCandidates, formatDuration, staffUpdateSubmission,
  writePlays, type LibraryCandidate,
} from '../../api/songfest';

export default function AfterPanel({ festivalId, festivalName }: { festivalId: number; festivalName: string }) {
  const [candidates, setCandidates] = useState<LibraryCandidate[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchLibraryCandidates(festivalId)
      .then(list => { setCandidates(list); setSelected(new Set()); })
      .catch(err => setError(apiErrorMessage(err, '載入失敗')));
  }, [festivalId]);

  useEffect(load, [load]);

  const write = async () => {
    if (!window.confirm(`把排好的歌單寫成「${festivalName}」的播放紀錄？這一場原本的播放紀錄會被取代。`)) return;
    try {
      const res = await writePlays(festivalId);
      setNotice(`已寫入 ${res.written} 筆播放紀錄（CM 和窗掉的歌不算）。舊曲的「上次播放」「播放次數」會跟著更新。`);
    } catch (err) {
      setError(apiErrorMessage(err, '寫入失敗'));
    }
  };

  const toggleConsent = async (c: LibraryCandidate) => {
    try {
      await staffUpdateSubmission(c.submissionId, { libraryConsent: !c.libraryConsent });
      load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const add = async () => {
    const ids = [...selected];
    if (!window.confirm(`幫 ${ids.length} 首自動編 DVD 編號並收進舊曲清單？`)) return;
    try {
      const res = await addToLibrary(festivalId, ids);
      setCandidates(res.candidates);
      setSelected(new Set());
      setNotice(res.added.length
        ? `已收進歌單：${res.added.join('、')}。記得把匯出的名單貼回「中央動畫社線上歌單」試算表。`
        : '沒有新增（要作者同意、而且還沒收進歌單的才能收）。');
    } catch (err) {
      setError(apiErrorMessage(err, '收進歌單失敗'));
    }
  };

  const ready = (candidates ?? []).filter(c => c.libraryConsent && !c.dvdCode);

  return (
    <div className="sf-after">
      {error && <p className="sf-error" role="alert">{error}</p>}
      {notice && <p className="sf-notice" role="status">{notice}</p>}

      <section className="sf-card sf-after-section">
        <h3>寫入播放紀錄</h3>
        <p className="sf-hint">
          活動結束後按一次，網站就會用排好的歌單更新播放紀錄。也可以照舊填「最新播放曲目統計」試算表再匯入，以最後一次為準。
        </p>
        <button type="button" className="sf-button is-primary" onClick={() => void write()}>寫入播放紀錄</button>
      </section>

      <section className="sf-card sf-after-section">
        <h3>收進歌單</h3>
        <p className="sf-hint">
          列出這場有排進歌單、已繳交的新曲。作者可以在「新曲投稿」頁回報同意，排歌組也可以在這裡代為勾選。
          勾選後按「自動編號」由網站接著編 DVD 編號；或只匯出名單交給社產負責人貼回試算表。
        </p>
        {candidates === null && <p className="sf-muted">載入中…</p>}
        {candidates?.length === 0 && <p className="sf-muted">這場還沒有可以收進歌單的新曲。</p>}
        {candidates && candidates.length > 0 && (
          <table className="sf-manage-table">
            <thead>
              <tr><th>選</th><th>曲名</th><th>製作者</th><th>長度</th><th>同意收進</th><th>DVD 編號</th></tr>
            </thead>
            <tbody>
              {candidates.map(c => (
                <tr key={c.submissionId}>
                  <td>
                    <input
                      type="checkbox"
                      disabled={!c.libraryConsent || Boolean(c.dvdCode)}
                      checked={selected.has(c.submissionId)}
                      onChange={e => {
                        const next = new Set(selected);
                        if (e.target.checked) next.add(c.submissionId); else next.delete(c.submissionId);
                        setSelected(next);
                      }}
                      aria-label={`選擇〈${c.title}〉`}
                    />
                  </td>
                  <td className="sf-manage-song">〈{c.title}〉<span className="sf-secondary">{c.songSource}</span></td>
                  <td data-label="製作者">{c.editor}</td>
                  <td data-label="長度">{formatDuration(c.duration)}</td>
                  <td data-label="同意">
                    <input
                      type="checkbox"
                      checked={c.libraryConsent}
                      disabled={Boolean(c.dvdCode)}
                      onChange={() => void toggleConsent(c)}
                      aria-label={`〈${c.title}〉同意收進歌單`}
                    />
                  </td>
                  <td data-label="DVD">{c.dvdCode ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="sf-form-actions sf-after-actions">
          <button type="button" className="sf-button" onClick={() => setSelected(new Set(ready.map(c => c.submissionId)))} disabled={ready.length === 0}>
            全選可收的（{ready.length}）
          </button>
          <button type="button" className="sf-button is-primary" onClick={() => void add()} disabled={selected.size === 0}>
            自動編號並收進舊曲
          </button>
          <button
            type="button"
            className="sf-button"
            onClick={() => void downloadLibraryCsv(festivalId, `${festivalName}_收進歌單.csv`).catch(() => setError('匯出失敗'))}
          >
            匯出名單（給社產）
          </button>
        </div>
      </section>
    </div>
  );
}
