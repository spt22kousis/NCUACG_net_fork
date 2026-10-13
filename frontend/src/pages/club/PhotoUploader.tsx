// frontend/src/pages/club/PhotoUploader.tsx
// 上傳照片：選歸屬（社課／歌謠祭／日常）、拍攝日期、說明，一次選多張。
// 每張先在瀏覽器縮小，再一張一張上傳，顯示進度。
import { useEffect, useState, type FormEvent } from 'react';
import { apiErrorMessage } from '../../api/songfest';
import {
  PHOTO_KIND_LABEL, fetchLessons, lessonLabel, resizeImage, uploadPhoto,
  type Lesson, type Photo, type PhotoInput, type PhotoKind, type PhotoUploadOptions,
} from '../../api/club';

interface Props {
  options: PhotoUploadOptions;
  /** 從網址帶進來的預設歸屬，例如從某一堂社課按「上傳照片」 */
  initial?: { kind?: PhotoKind; category?: string; lesson?: number; festival?: number; topic?: string };
  onUploaded: (photos: Photo[]) => void;
  onClose: () => void;
}

export default function PhotoUploader({ options, initial, onUploaded, onClose }: Props) {
  const kinds = (['lesson', 'songfest', 'daily'] as PhotoKind[]).filter(k =>
    k === 'lesson' ? options.categories.length > 0 : k === 'songfest' ? options.festivals.length > 0 : options.daily,
  );
  const [kind, setKind] = useState<PhotoKind>(initial?.kind && kinds.includes(initial.kind) ? initial.kind : kinds[0]);
  const [category, setCategory] = useState(initial?.category ?? options.categories[0]?.id ?? '');
  const [lesson, setLesson] = useState<number | ''>(initial?.lesson ?? '');
  const [festival, setFestival] = useState<number | ''>(initial?.festival ?? options.festivals[0]?.id ?? '');
  const [topic, setTopic] = useState(initial?.topic ?? '');
  const [takenOn, setTakenOn] = useState('');
  const [caption, setCaption] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [progress, setProgress] = useState<{ done: number; total: number; current: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 社課的堂次清單（新的在上面）
  useEffect(() => {
    if (kind !== 'lesson' || !category) return;
    fetchLessons(category).then(list => setLessons([...list].reverse())).catch(() => setLessons([]));
  }, [kind, category]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (files.length === 0) {
      setError('請選照片');
      return;
    }
    const input: PhotoInput = { kind, caption: caption.trim(), takenOn: takenOn || undefined };
    if (kind === 'lesson') Object.assign(input, { category, lesson: lesson || undefined });
    if (kind === 'songfest') input.festival = festival || undefined;
    if (kind === 'daily') input.topic = topic.trim();

    const uploaded: Photo[] = [];
    const done = new Set<File>();
    const failed: string[] = [];
    for (const [i, file] of files.entries()) {
      setProgress({ done: i, total: files.length, current: 0 });
      try {
        const blob = await resizeImage(file);
        uploaded.push(await uploadPhoto(blob, input, ratio => setProgress({ done: i, total: files.length, current: ratio })));
        done.add(file);
      } catch (err) {
        failed.push(`${file.name}：${apiErrorMessage(err, '上傳失敗')}`);
        // 不是照片本身的問題（歸屬填錯、沒有權限）時，每張都會失敗，不用再試下一張
        const res = (err as { response?: { status?: number; data?: object } }).response;
        if (res && (res.status === 403 || (res.status === 400 && res.data && !('image' in res.data)))) break;
      }
    }
    setProgress(null);
    if (uploaded.length) onUploaded(uploaded);
    if (done.size === files.length) {
      onClose();
    } else {
      // 沒傳成功的留著，改好再按一次上傳
      setFiles(files.filter(f => !done.has(f)));
      setError(failed.join('\n'));
    }
  };

  const busy = progress !== null;
  return (
    <form className="sf-card sf-form photo-uploader" onSubmit={submit}>
      <h3>上傳照片</h3>
      <fieldset className="sf-radio-row" disabled={busy}>
        <legend>歸屬</legend>
        {kinds.map(k => (
          <label key={k}>
            <input type="radio" name="kind" checked={kind === k} onChange={() => setKind(k)} /> {PHOTO_KIND_LABEL[k]}
          </label>
        ))}
      </fieldset>

      <div className="sf-form-grid">
        {kind === 'lesson' && (
          <>
            <label>
              社課 *
              <select value={category} onChange={e => { setCategory(e.target.value); setLesson(''); }} disabled={busy}>
                {options.categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label>
              哪一堂（選填）
              <select value={lesson} onChange={e => setLesson(e.target.value ? Number(e.target.value) : '')} disabled={busy}>
                <option value="">不指定</option>
                {lessons.map(l => <option key={l.id} value={l.id}>{l.startTime.slice(5, 10).replace('-', '/')} {lessonLabel(l)}</option>)}
              </select>
            </label>
          </>
        )}
        {kind === 'songfest' && (
          <label>
            歌謠祭場次 *
            <select value={festival} onChange={e => setFestival(Number(e.target.value))} disabled={busy}>
              {options.festivals.map(f => <option key={f.id} value={f.id}>{f.name}（{f.date.replace(/-/g, '/')}）</option>)}
            </select>
          </label>
        )}
        {kind === 'daily' && (
          <label>
            分類 *
            <small className="sf-hint">例如 社遊、聚餐、社博；打過的會出現在建議清單</small>
            <input required list="photo-topics" maxLength={50} value={topic} onChange={e => setTopic(e.target.value)} disabled={busy} />
            <datalist id="photo-topics">
              {options.topics.map(t => <option key={t} value={t} />)}
            </datalist>
          </label>
        )}
        <label>
          拍攝日期
          <small className="sf-hint">不填就用那堂課或那場歌謠祭的日期，都沒有就是今天</small>
          <input type="date" value={takenOn} onChange={e => setTakenOn(e.target.value)} disabled={busy} />
        </label>
        <label className="lesson-span">
          說明（選填，會套用到這次選的每一張）
          <input maxLength={200} value={caption} onChange={e => setCaption(e.target.value)} disabled={busy} />
        </label>
      </div>

      <label>
        照片 *
        <small className="sf-hint">可以一次選多張；上傳前會自動縮小，拍攝地點等資訊也會拿掉</small>
        <input type="file" accept="image/*" multiple disabled={busy} onChange={e => setFiles([...(e.target.files ?? [])])} />
      </label>
      {files.length > 0 && !busy && <p className="sf-hint">已選 {files.length} 張</p>}

      {progress && (
        <div className="photo-progress" role="status">
          <span>上傳中 {progress.done + 1} / {progress.total}</span>
          <progress value={progress.done + progress.current} max={progress.total} />
        </div>
      )}
      {error && <p className="sf-error" role="alert" style={{ whiteSpace: 'pre-wrap' }}>{error}</p>}

      <div className="sf-form-actions">
        <button type="button" className="sf-button" onClick={onClose} disabled={busy}>取消</button>
        <button type="submit" className="sf-button is-primary" disabled={busy || files.length === 0}>
          上傳 {files.length > 0 ? `${files.length} 張` : ''}
        </button>
      </div>
    </form>
  );
}
