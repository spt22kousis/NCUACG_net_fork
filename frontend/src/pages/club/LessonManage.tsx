// frontend/src/pages/club/LessonManage.tsx
// 社課負責人發、改自己社課的公告；幹部可以管全部社課。負責人由幹部在後台「社課負責人」指定。
import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiErrorMessage } from '../../api/songfest';
import { deleteLesson, fetchLessonManage, type Lesson, type LessonManageData } from '../../api/club';
import { useAuth } from '../../contexts/auth';
import ClubLayout from './ClubLayout';
import LessonCard, { CopyDiscordButton } from './LessonCard';
import LessonForm from './LessonForm';

export default function LessonManage() {
  const { isAuthenticated } = useAuth();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<LessonManageData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [filter, setFilter] = useState('');

  // 從單堂頁面按「修改」過來時會帶 ?edit=<id>
  const editingId = Number(params.get('edit')) || null;
  const setEditing = (id: number | null) => setParams(id ? { edit: String(id) } : {});

  const load = useCallback(() => {
    fetchLessonManage()
      .then(setData)
      .catch(err => setError(apiErrorMessage(err, '載入失敗')));
  }, []);

  useEffect(() => {
    if (isAuthenticated) load();
  }, [isAuthenticated, load]);

  if (!isAuthenticated) {
    return (
      <ClubLayout>
        <p className="sf-card sf-empty">請先<Link to="/login">登入</Link>。社課負責人由幹部在後台指定。</p>
      </ClubLayout>
    );
  }

  const saved = (lesson: Lesson) => {
    setCreating(false);
    setEditing(null);
    setNotice(`已儲存〈${lesson.title}〉。可以按「複製 Discord 公告」貼到社課頻道。`);
    load();
  };

  const remove = async (lesson: Lesson) => {
    if (!window.confirm(`刪除〈${lesson.title}〉？刪掉就找不回來了。`)) return;
    try {
      await deleteLesson(lesson.id);
      setNotice(`已刪除〈${lesson.title}〉。`);
      load();
    } catch (err) {
      setError(apiErrorMessage(err, '刪除失敗'));
    }
  };

  const lessons = (data?.lessons ?? []).filter(l => !filter || l.category === filter);
  const now = Date.now();
  // 接下來的照時間先後，過去的新的在上面
  const upcoming = lessons.filter(l => new Date(l.endTime ?? l.startTime).getTime() >= now).reverse();
  const past = lessons.filter(l => new Date(l.endTime ?? l.startTime).getTime() < now);
  const editing = data?.lessons.find(l => l.id === editingId);

  const renderRow = (lesson: Lesson) =>
    editing?.id === lesson.id && data ? (
      <LessonForm key={lesson.id} data={data} initial={lesson} onSaved={saved} onCancel={() => setEditing(null)} />
    ) : (
      <div key={lesson.id} className="lesson-manage-row">
        <LessonCard lesson={lesson} />
        <div className="sf-form-actions lesson-actions">
          <CopyDiscordButton lesson={lesson} />
          <button type="button" className="sf-button" onClick={() => { setCreating(false); setEditing(lesson.id); }}>
            修改{new Date(lesson.startTime).getTime() < now && !lesson.slidesUrl ? '／補簡報' : ''}
          </button>
          <button type="button" className="sf-button is-danger" onClick={() => void remove(lesson)}>刪除</button>
        </div>
      </div>
    );

  return (
    <ClubLayout>
      {error && <p className="sf-error" role="alert">{error}</p>}
      {notice && <p className="sf-notice" role="status">{notice}</p>}
      {!error && !data && <p className="sf-muted">載入中…</p>}

      {data && (
        <>
          <p className="sf-lead">
            你可以管理：{data.categories.map(c => c.name).join('、')}。
            存好之後按「複製 Discord 公告」，格式跟平常在社課頻道發的一樣；網站的社課公告、社課介紹與行事曆也會一起更新。
          </p>

          {creating ? (
            <LessonForm data={data} onSaved={saved} onCancel={() => setCreating(false)} />
          ) : (
            <button type="button" className="sf-button is-primary" onClick={() => { setEditing(null); setCreating(true); }}>
              ＋ 新增社課
            </button>
          )}

          {data.categories.length > 1 && (
            <div className="sf-chips lesson-filter" role="group" aria-label="篩選社課">
              <button type="button" className={filter === '' ? 'is-active' : ''} onClick={() => setFilter('')}>全部</button>
              {data.categories.map(c => (
                <button key={c.id} type="button" className={filter === c.id ? 'is-active' : ''} onClick={() => setFilter(c.id)}>
                  {c.name}
                </button>
              ))}
            </div>
          )}

          <section className="sf-section">
            <h2 className="sf-section-title">接下來的社課</h2>
            {upcoming.length === 0 && <p className="sf-card sf-empty">還沒有排定的社課。</p>}
            <div className="lesson-list">{upcoming.map(renderRow)}</div>
          </section>

          {past.length > 0 && (
            <section className="sf-section">
              <h2 className="sf-section-title">過去的堂次</h2>
              <div className="lesson-list">{past.map(renderRow)}</div>
            </section>
          )}
        </>
      )}
    </ClubLayout>
  );
}
