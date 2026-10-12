// frontend/src/pages/songfest/SubmissionForm.tsx
// 報曲與修改投稿的表單。欄位對應原本回報串，說明文字照「歌謠祭曲目投稿規則」。
import { useState, type FormEvent } from 'react';
import {
  apiErrorMessage, createSubmission, formatDuration, parseDuration, updateSubmission,
  type MySubmission, type SongfestFestival, type SubmissionInput,
} from '../../api/songfest';

interface Props {
  festival: SongfestFestival;
  initial?: MySubmission;          // 有值就是修改
  ownSubmissions: MySubmission[];  // 連曲只能選自己的其他投稿
  onSaved: (sub: MySubmission) => void;
  onCancel: () => void;
}

type TextKey =
  | 'songSource' | 'visualSource' | 'title' | 'artist' | 'attributes' | 'songLink' | 'remarks'
  | 'fileLink' | 'fiveSecLink';

const SONG_KEYS: TextKey[] = ['songSource', 'visualSource', 'title', 'artist'];
const DETAIL_KEYS: TextKey[] = ['attributes', 'songLink', 'remarks'];
const UPLOAD_KEYS: TextKey[] = ['fileLink', 'fiveSecLink'];

function initialText(sub?: MySubmission): Record<TextKey, string> {
  return {
    songSource: sub?.songSource ?? '',
    visualSource: sub?.visualSource ?? '',
    title: sub?.title ?? '',
    artist: sub?.artist ?? '',
    attributes: sub?.attributes ?? '',
    songLink: sub?.songLink ?? '',
    remarks: sub?.remarks ?? '',
    fileLink: sub?.fileLink ?? '',
    fiveSecLink: sub?.fiveSecLink ?? '',
  };
}

export default function SubmissionForm({ festival, initial, ownSubmissions, onSaved, onCancel }: Props) {
  const songLocked = initial !== undefined && !initial.permissions.canEditSong;
  const sources = (['member', 'partner'] as const).filter(s => festival.reportOpen[s]);

  const [text, setText] = useState(initialText(initial));
  const [source, setSource] = useState<'member' | 'partner'>(sources[0] ?? 'member');
  const [fiveSec, setFiveSec] = useState(initial?.fiveSec ?? false);
  const [restrictedWork, setRestrictedWork] = useState(initial?.restrictedWork ?? false);
  const [isBackup, setIsBackup] = useState(initial?.isBackup ?? false);
  const [duration, setDuration] = useState(initial?.duration ? formatDuration(initial.duration) : '');
  const [chainWith, setChainWith] = useState<number | null>(initial?.chainWith ?? null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (key: TextKey) => (e: { target: { value: string } }) =>
    setText(prev => ({ ...prev, [key]: e.target.value }));

  const chainOptions = ownSubmissions.filter(
    s => s.id !== initial?.id && s.status !== 'withdrawn' && s.status !== 'rejected',
  );

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const seconds = parseDuration(duration);
    if (duration.trim() && seconds === null) {
      setError('影片長度請用「分:秒」的格式，例如 4:25');
      return;
    }

    // 修改時只送有變動的欄位：報曲截止後歌曲欄位是鎖住的，送了沒變的值也沒關係，但沒必要
    const input: SubmissionInput = {};
    if (initial) {
      const before = initialText(initial);
      for (const key of [...(songLocked ? [] : SONG_KEYS), ...DETAIL_KEYS, ...UPLOAD_KEYS]) {
        if (text[key] !== before[key]) input[key] = text[key].trim();
      }
      if (!songLocked && fiveSec !== initial.fiveSec) input.fiveSec = fiveSec;
      if (!songLocked && restrictedWork !== initial.restrictedWork) input.restrictedWork = restrictedWork;
      if (!songLocked && isBackup !== initial.isBackup) input.isBackup = isBackup;
      if (seconds !== initial.duration) input.duration = seconds;
      if (chainWith !== initial.chainWith) input.chainWith = chainWith;
    } else {
      for (const key of [...SONG_KEYS, ...DETAIL_KEYS]) input[key] = text[key].trim();
      Object.assign(input, { source, fiveSec, restrictedWork, isBackup: source === 'partner' && isBackup });
    }

    setSaving(true);
    try {
      const saved = initial ? await updateSubmission(initial.id, input) : await createSubmission(festival.id, input);
      onSaved(saved);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="sf-card sf-form" onSubmit={handleSubmit}>
      <h3>{initial ? `修改〈${initial.title}〉` : '報曲'}</h3>

      {!initial && sources.length > 1 && (
        <fieldset className="sf-radio-row">
          <legend>投稿身分</legend>
          <label><input type="radio" name="source" checked={source === 'member'} onChange={() => setSource('member')} /> 本社</label>
          <label><input type="radio" name="source" checked={source === 'partner'} onChange={() => setSource('partner')} /> {festival.partnerName}</label>
        </fieldset>
      )}

      <fieldset className="sf-fieldset" disabled={songLocked}>
        <legend>歌曲</legend>
        {songLocked && <p className="sf-hint">報曲截止後要換歌或改 5 秒畫面，請找排歌組。</p>}
        <div className="sf-form-grid">
          <label>
            歌曲出處 *
            <small className="sf-hint">ACGN 歌曲填作品名稱；非 ACGN 歌曲填「一般曲」</small>
            <input required value={text.songSource} onChange={set('songSource')} />
          </label>
          <label>
            畫面出處 *
            <small className="sf-hint">單一作品填作品名稱；多部作品或非 ACGN 畫面填「複數作品」</small>
            <input required value={text.visualSource} onChange={set('visualSource')} />
          </label>
          <label>
            曲名 *
            <input required value={text.title} onChange={set('title')} />
          </label>
          <label>
            原唱歌手
            <input value={text.artist} onChange={set('artist')} />
          </label>
        </div>
        <label className="sf-check">
          <input type="checkbox" checked={fiveSec} onChange={e => setFiveSec(e.target.checked)} />
          要上傳 5 秒畫面（每報 1 首可以放 1 個 5 秒彩蛋，在活動結束的合輯影片播出）
        </label>
        {(initial ? initial.source : source) === 'partner' && (
          <label className="sf-check">
            <input type="checkbox" checked={isBackup} onChange={e => setIsBackup(e.target.checked)} />
            這首是備曲（{festival.partnerName}正選未滿 {festival.partnerLimit} 首時才會補上）
          </label>
        )}
        <label className="sf-check">
          <input type="checkbox" checked={restrictedWork} onChange={e => setRestrictedWork(e.target.checked)} />
          作品有公告禁止二創或有限制（例如曼迪、羚邦代理）
        </label>
      </fieldset>

      <fieldset className="sf-fieldset">
        <legend>說明</legend>
        <label>
          畫面或作品屬性
          <small className="sf-hint">簡述畫面素材或作品性質，自製畫面也請註明</small>
          <input value={text.attributes} onChange={set('attributes')} />
        </label>
        <label>
          歌曲連結 *
          <small className="sf-hint">使用歌曲的連結，自製歌曲也請註明</small>
          <input required value={text.songLink} onChange={set('songLink')} />
        </label>
        <label>
          備註
          <small className="sf-hint">畫面素材、歌曲、剪輯手法等；較難界定的內容務必在這裡註明，沒註明可能無法播出</small>
          <textarea rows={3} value={text.remarks} onChange={set('remarks')} />
        </label>
      </fieldset>

      {initial && (
        <fieldset className="sf-fieldset">
          <legend>繳交</legend>
          <p className="sf-hint">
            把檔案放到雲端（檔名：[畫面出處][曲名][作者名]），貼上分享連結並填影片長度就算繳交。
            繳交後再改檔案或長度，排歌組會看到提醒。
          </p>
          <div className="sf-form-grid">
            <label>
              檔案連結
              <input value={text.fileLink} onChange={set('fileLink')} placeholder="Google 雲端硬碟等分享連結" />
            </label>
            <label>
              影片長度
              <input value={duration} onChange={e => setDuration(e.target.value)} placeholder="例如 4:25" inputMode="numeric" />
            </label>
            {initial.fiveSec && (
              <label>
                5 秒畫面連結
                <input value={text.fiveSecLink} onChange={set('fiveSecLink')} placeholder="檔名：[作者名]_5sec" />
              </label>
            )}
          </div>
          {chainOptions.length > 0 && (
            <label>
              連曲（想跟自己的哪一首連續播出；至多 2 首、合計 10 分鐘內）
              <select value={chainWith ?? ''} onChange={e => setChainWith(e.target.value ? Number(e.target.value) : null)}>
                <option value="">不連曲</option>
                {chainOptions.map(s => <option key={s.id} value={s.id}>〈{s.title}〉</option>)}
              </select>
            </label>
          )}
        </fieldset>
      )}

      {error && <p className="sf-error" role="alert">{error}</p>}
      <div className="sf-form-actions">
        <button type="button" className="sf-button" onClick={onCancel} disabled={saving}>取消</button>
        <button type="submit" className="sf-button is-primary" disabled={saving}>
          {saving ? '送出中…' : initial ? '儲存' : '送出報曲'}
        </button>
      </div>
    </form>
  );
}
