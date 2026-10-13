// frontend/src/pages/club/Lessons.tsx
// 社課公告：全部社課近期的堂次，或選一個社課看下一堂與過去的堂次（含簡報）
import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  COURSE_CATEGORIES, categoryName, fetchLesson, fetchLessons, fetchUpcomingLessons, type Lesson,
} from '../../api/club';
import ClubLayout from './ClubLayout';
import LessonCard, { CopyDiscordButton } from './LessonCard';

function isOver(lesson: Lesson): boolean {
  return new Date(lesson.endTime ?? lesson.startTime).getTime() < Date.now();
}

export default function Lessons() {
  const [params, setParams] = useSearchParams();
  const category = params.get('category') ?? '';
  const [lessons, setLessons] = useState<Lesson[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLessons(null);
    setError(null);
    (category ? fetchLessons(category) : fetchUpcomingLessons(30))
      .then(setLessons)
      .catch(() => setError('載入失敗，請稍後再試'));
  }, [category]);

  const upcoming = (lessons ?? []).filter(l => !isOver(l));
  // 過去的堂次新的在上面
  const past = (lessons ?? []).filter(isOver).reverse();

  return (
    <ClubLayout>
      <p className="sf-lead">
        各社課的上課時間、地點與內容。社課負責人會在 Discord 發同一份公告；課後的簡報也會放在這裡。
      </p>
      <div className="sf-chips" role="group" aria-label="社課">
        <button type="button" className={category === '' ? 'is-active' : ''} onClick={() => setParams({})}>
          近期全部
        </button>
        {COURSE_CATEGORIES.map(c => (
          <button
            key={c.id}
            type="button"
            className={category === c.id ? 'is-active' : ''}
            onClick={() => setParams({ category: c.id })}
          >
            {c.name}
          </button>
        ))}
      </div>

      {error && <p className="sf-error" role="alert">{error}</p>}
      {!error && lessons === null && <p className="sf-muted">載入中…</p>}

      {lessons && (
        <section className="sf-section">
          <h2 className="sf-section-title">
            {category ? `${categoryName(category)}：接下來的社課` : '30 天內的社課'}
          </h2>
          {upcoming.length === 0 && <p className="sf-card sf-empty">目前還沒有排定的社課。</p>}
          <div className="lesson-list">
            {upcoming.map((lesson, i) => (
              <LessonCard key={lesson.id} lesson={lesson} badge={category && i === 0 ? '下一堂' : undefined} />
            ))}
          </div>
        </section>
      )}

      {category && past.length > 0 && (
        <section className="sf-section">
          <h2 className="sf-section-title">過去的堂次</h2>
          <div className="lesson-list">
            {past.map(lesson => <LessonCard key={lesson.id} lesson={lesson} />)}
          </div>
        </section>
      )}

      {category && (
        <p className="sf-note">
          <Link to={`/club/works?category=${category}`}>看{categoryName(category)}的成果牆 →</Link>
        </p>
      )}
    </ClubLayout>
  );
}

export function LessonDetail() {
  const { id } = useParams();
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLesson(Number(id))
      .then(setLesson)
      .catch(() => setError('找不到這堂社課'));
  }, [id]);

  return (
    <ClubLayout>
      <Link to={lesson ? `/club/lessons?category=${lesson.category}` : '/club/lessons'} className="sf-back">
        ← {lesson ? `${lesson.categoryName}的所有堂次` : '社課公告'}
      </Link>
      {error && <p className="sf-error" role="alert">{error}</p>}
      {!error && !lesson && <p className="sf-muted">載入中…</p>}
      {lesson && (
        <>
          <LessonCard lesson={lesson} full />
          {lesson.canEdit && (
            <div className="sf-form-actions lesson-actions">
              <CopyDiscordButton lesson={lesson} />
              <Link to={`/club/lessons/manage?edit=${lesson.id}`} className="sf-button">修改</Link>
            </div>
          )}
        </>
      )}
    </ClubLayout>
  );
}
