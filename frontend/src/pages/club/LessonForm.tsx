// frontend/src/pages/club/LessonForm.tsx
// 新增、修改一堂社課。欄位照社課負責人在 Discord 發的公告格式。
import { useState, type FormEvent } from 'react';
import { apiErrorMessage } from '../../api/songfest';
import {
  createLesson, fromLocalInput, lessonLabel, toLocalInput, updateLesson,
  type Lesson, type LessonInput, type LessonManageData,
} from '../../api/club';

interface Props {
  data: LessonManageData;
  initial?: Lesson;        // 有值就是修改
  onSaved: (lesson: Lesson) => void;
  onCancel: () => void;
}

type TextKey = 'title' | 'location' | 'content' | 'notes' | 'prerequisites' | 'discordRole' | 'slidesUrl';

export default function LessonForm({ data, initial, onSaved, onCancel }: Props) {
  const [category, setCategory] = useState(initial?.category ?? data.categories[0]?.id ?? '');
  const defaults = data.defaults[category];
  const [text, setText] = useState<Record<TextKey, string>>({
    title: initial?.title ?? '',
    location: initial?.location ?? defaults?.location ?? '社辦',
    content: initial?.content ?? '',
    notes: initial?.notes ?? '',
    prerequisites: initial?.prerequisites ?? '',
    discordRole: initial?.discordRole ?? defaults?.discordRole ?? '',
    slidesUrl: initial?.slidesUrl ?? '',
  });
  const [number, setNumber] = useState(initial ? String(initial.number ?? '') : String(defaults?.nextNumber ?? ''));
  const [start, setStart] = useState(toLocalInput(initial?.startTime ?? null));
  const [end, setEnd] = useState(toLocalInput(initial?.endTime ?? null));
  const [requires, setRequires] = useState<number[]>(initial?.requires.map(r => r.id) ?? []);
  const [isPublished, setIsPublished] = useState(initial?.isPublished ?? true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (key: TextKey) => (e: { target: { value: string } }) =>
    setText(prev => ({ ...prev, [key]: e.target.value }));

  // 換社課時，地點、身分組、第幾堂跟著換成那個社課的預設值（只在新增時）
  const changeCategory = (next: string) => {
    setCategory(next);
    setRequires([]);
    const d = data.defaults[next];
    if (!initial && d) {
      setText(prev => ({ ...prev, location: d.location, discordRole: d.discordRole }));
      setNumber(String(d.nextNumber));
    }
  };

  // 「建議先參加」只能選同一個社課、比這堂早的
  const earlier = data.lessons.filter(l =>
    l.category === category && l.id !== initial?.id && (!start || new Date(l.startTime) < new Date(start)),
  );

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!start) {
      setError('請填開始時間');
      return;
    }
    const input: LessonInput = {
      category,
      number: number.trim() ? Number(number) : null,
      title: text.title.trim(),
      startTime: fromLocalInput(start) ?? undefined,
      endTime: fromLocalInput(end),
      location: text.location.trim(),
      content: text.content.trim(),
      notes: text.notes.trim(),
      prerequisites: text.prerequisites.trim(),
      requires,
      discordRole: text.discordRole.trim(),
      slidesUrl: text.slidesUrl.trim(),
      isPublished,
    };

    setSaving(true);
    try {
      onSaved(initial ? await updateLesson(initial.id, input) : await createLesson(input));
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="sf-card sf-form" onSubmit={handleSubmit}>
      <h3>{initial ? `修改〈${initial.title}〉` : '新增社課'}</h3>

      <fieldset className="sf-fieldset">
        <legend>基本資料</legend>
        <div className="sf-form-grid">
          <label>
            社課 *
            <select value={category} onChange={e => changeCategory(e.target.value)} disabled={data.categories.length < 2}>
              {data.categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>
            第幾堂
            <input value={number} onChange={e => setNumber(e.target.value)} inputMode="numeric" placeholder="可以不填" />
          </label>
          <label className="lesson-span">
            主題 *
            <small className="sf-hint">公告「內容：」那一行，例如「高鐵與捷運」</small>
            <input required maxLength={100} value={text.title} onChange={set('title')} />
          </label>
          <label>
            開始時間 *
            <input
              type="datetime-local"
              required
              value={start}
              onChange={e => {
                setStart(e.target.value);
                // 社課通常兩小時：結束時間還沒填時先幫忙帶
                if (!end && e.target.value) {
                  setEnd(toLocalInput(new Date(new Date(e.target.value).getTime() + 2 * 3600 * 1000).toISOString()));
                }
              }}
            />
          </label>
          <label>
            結束時間
            <input type="datetime-local" value={end} onChange={e => setEnd(e.target.value)} />
          </label>
          <label>
            地點 *
            <input required maxLength={100} value={text.location} onChange={set('location')} />
          </label>
          <label>
            Discord 身分組
            <small className="sf-hint">貼在公告最後，例如 @鐵道社課通知</small>
            <input maxLength={50} value={text.discordRole} onChange={set('discordRole')} />
          </label>
        </div>
      </fieldset>

      <fieldset className="sf-fieldset">
        <legend>公告內容</legend>
        <label>
          內容介紹
          <small className="sf-hint">這堂課要做什麼、歡迎誰來</small>
          <textarea rows={4} value={text.content} onChange={set('content')} />
        </label>
        <label>
          備註
          <small className="sf-hint">放在分隔線下面，例如「負責人在準備段考，ppt 可能比較隨便」</small>
          <textarea rows={2} value={text.notes} onChange={set('notes')} />
        </label>
        <label>
          建議具備
          <small className="sf-hint">一行一項</small>
          <textarea rows={2} value={text.prerequisites} onChange={set('prerequisites')} />
        </label>
        {earlier.length > 0 && (
          <div className="lesson-requires">
            <span>建議先參加的堂次（公告會寫成「參加過前面的社課（《…》）」）</span>
            {earlier.map(l => (
              <label key={l.id} className="sf-check">
                <input
                  type="checkbox"
                  checked={requires.includes(l.id)}
                  onChange={e => setRequires(e.target.checked ? [...requires, l.id] : requires.filter(id => id !== l.id))}
                />
                {lessonLabel(l)}
              </label>
            ))}
          </div>
        )}
      </fieldset>

      <fieldset className="sf-fieldset">
        <legend>課後</legend>
        <label>
          簡報連結
          <small className="sf-hint">上完課再補也可以</small>
          <input type="url" value={text.slidesUrl} onChange={set('slidesUrl')} placeholder="https://" />
        </label>
      </fieldset>

      <label className="sf-check">
        <input type="checkbox" checked={isPublished} onChange={e => setIsPublished(e.target.checked)} />
        公開（取消勾選就只有負責人看得到，可以先存成草稿）
      </label>

      {error && <p className="sf-error" role="alert">{error}</p>}
      <div className="sf-form-actions">
        <button type="button" className="sf-button" onClick={onCancel}>取消</button>
        <button type="submit" className="sf-button is-primary" disabled={saving}>
          {saving ? '儲存中…' : '儲存'}
        </button>
      </div>
    </form>
  );
}
