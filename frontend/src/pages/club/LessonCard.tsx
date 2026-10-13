// frontend/src/pages/club/LessonCard.tsx
// 一堂社課的卡片：社課公告列表、社課介紹頁的「下一堂」、單堂頁面共用
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { formatLessonTime, lessonLabel, type Lesson } from '../../api/club';

/** 把文字複製到剪貼簿；成功回 true。非 https 時 navigator.clipboard 不能用，改用舊方法。 */
async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    try {
      return document.execCommand('copy');
    } catch {
      return false;
    } finally {
      area.remove();
    }
  }
}

export function CopyDiscordButton({ lesson }: { lesson: Lesson }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [preview, setPreview] = useState(false);
  if (!lesson.discordText) return null;
  const copy = async () => {
    const ok = await copyText(lesson.discordText ?? '');
    setState(ok ? 'copied' : 'failed');
    if (ok) window.setTimeout(() => setState('idle'), 2500);
  };
  // 複製失敗（瀏覽器不給權限）時直接把文字選好，讓人按 Ctrl+C
  const showText = preview || state === 'failed';
  return (
    <>
      <button type="button" className="sf-button is-primary" onClick={() => void copy()}>
        {state === 'copied' ? '已複製 ✓' : '複製 Discord 公告'}
      </button>
      <button type="button" className="sf-button" onClick={() => { setPreview(!showText); setState('idle'); }}aria-expanded={showText}>
        {showText ? '收起公告' : '預覽公告'}
      </button>
      {showText && (
        <div className="lesson-discord">
          {state === 'failed' && <p className="sf-error">瀏覽器不讓網站直接複製，請在下面按 Ctrl+C（手機長按）複製。</p>}
          <textarea
            readOnly
            rows={Math.min(16, lesson.discordText.split('\n').length + 1)}
            value={lesson.discordText}
            onFocus={e => e.target.select()}
            autoFocus={state === 'failed'}
          />
        </div>
      )}
    </>
  );
}

interface Props {
  lesson: Lesson;
  /** 完整顯示內容、備註與建議具備（單堂頁面）；否則只顯示摘要 */
  full?: boolean;
  /** 卡片標題前的小標，例如「下一堂」 */
  badge?: string;
}

export default function LessonCard({ lesson, full = false, badge }: Props) {
  const prereq = lesson.prerequisites.split('\n').map(s => s.trim()).filter(Boolean);
  return (
    <article className={`sf-card lesson-card${lesson.isPublished === false ? ' is-draft' : ''}`}>
      <div className="lesson-card-head">
        <span className={`lesson-category is-${lesson.category}`}>{lesson.categoryName}</span>
        {badge && <span className="sf-badge">{badge}</span>}
        {lesson.isPublished === false && <span className="sf-tag">未公開</span>}
      </div>
      <h3 className="lesson-title">
        {full ? lessonLabel(lesson) : <Link to={`/club/lessons/${lesson.id}`}>{lessonLabel(lesson)}</Link>}
      </h3>
      <dl className="lesson-meta">
        <div><dt>時間</dt><dd>{formatLessonTime(lesson)}</dd></div>
        <div><dt>地點</dt><dd>{lesson.location}</dd></div>
      </dl>
      {lesson.content && <p className={`lesson-content${full ? '' : ' is-clamped'}`}>{lesson.content}</p>}
      {full && lesson.notes && <p className="lesson-notes">{lesson.notes}</p>}
      {full && (prereq.length > 0 || lesson.requires.length > 0) && (
        <div className="lesson-prereq">
          <strong>建議具備</strong>
          <ul>
            {prereq.map(line => <li key={line}>{line}</li>)}
            {lesson.requires.length > 0 && (
              <li>
                參加過前面的社課：
                {lesson.requires.map((r, i) => (
                  <span key={r.id}>
                    {i > 0 && '、'}
                    <Link to={`/club/lessons/${r.id}`}>《{r.title}》</Link>
                  </span>
                ))}
              </li>
            )}
          </ul>
        </div>
      )}
      {lesson.slidesUrl && (
        <p className="lesson-slides">
          <a href={lesson.slidesUrl} target="_blank" rel="noreferrer">📑 課堂簡報</a>
        </p>
      )}
    </article>
  );
}
