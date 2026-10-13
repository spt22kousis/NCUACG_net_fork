// frontend/src/pages/club/WorksManage.tsx
// 社課負責人上架成果牆作品：圖片直接上傳（自動縮小、做縮圖），影片可以上傳檔案或貼 YouTube 連結。
// 只能動自己社課的作品；幹部可以管全部。
import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { apiErrorMessage } from '../../api/songfest';
import {
  categoryName, createWork, createWorkCourse, deleteWork, fetchWorkManage, lessonLabel, resizeImage, updateWork,
  type ManagedWork, type WorkInput, type WorkManageData,
} from '../../api/club';
import { useAuth } from '../../contexts/auth';
import ClubLayout from './ClubLayout';

function WorkForm({ data, initial, onSaved, onCancel, onCourseCreated }: {
  data: WorkManageData;
  initial?: ManagedWork;
  onSaved: (work: ManagedWork) => void;
  onCancel: () => void;
  onCourseCreated: () => void;
}) {
  const [course, setCourse] = useState(initial?.course ?? data.courses[0]?.id ?? '');
  const [title, setTitle] = useState(initial?.title ?? '');
  const [author, setAuthor] = useState(initial?.author ?? '');
  const [type, setType] = useState<'image' | 'video'>(initial?.type ?? 'image');
  const [source, setSource] = useState<'file' | 'link'>(initial && !initial.hasFile ? 'link' : 'file');
  const [externalUrl, setExternalUrl] = useState(initial?.externalUrl ?? '');
  const [file, setFile] = useState<File | null>(null);
  const [thumbnail, setThumbnail] = useState<File | null>(null);
  const [lesson, setLesson] = useState<number | ''>(initial?.lesson?.id ?? '');
  const [isPublished, setIsPublished] = useState(initial?.isPublished ?? true);
  const [newCourse, setNewCourse] = useState({ category: data.categories[0]?.id ?? '', name: '' });
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const courseCategory = data.courses.find(c => c.id === course)?.category;
  const lessons = data.lessons.filter(l => l.category === courseCategory);

  const addCourse = async () => {
    if (!newCourse.name.trim()) return;
    try {
      const created = await createWorkCourse(newCourse.category, newCourse.name.trim());
      setCourse(created.id);
      setNewCourse({ ...newCourse, name: '' });
      onCourseCreated();
    } catch (err) {
      setError(apiErrorMessage(err, '新增分類失敗'));
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const input: WorkInput = { course, title: title.trim(), author: author.trim(), type, lesson, isPublished };
    if (source === 'link') {
      input.externalUrl = externalUrl.trim();
    } else if (file) {
      if (type === 'video' && file.size > data.maxVideoMb * 1024 * 1024) {
        setError(`影片超過 ${data.maxVideoMb} MB，請改貼 YouTube 連結`);
        return;
      }
      // 圖片先在瀏覽器縮小；影片原檔上傳
      input.file = type === 'image' ? await resizeImage(file, 2560) : file;
    } else if (!initial?.hasFile) {
      setError('請選檔案，或改用貼連結');
      return;
    }
    if (thumbnail) input.thumbnail = await resizeImage(thumbnail, 480);

    setProgress(0);
    try {
      onSaved(initial ? await updateWork(initial.id, input, setProgress) : await createWork(input, setProgress));
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setProgress(null);
    }
  };

  const busy = progress !== null;
  return (
    <form className="sf-card sf-form" onSubmit={submit}>
      <h3>{initial ? `修改〈${initial.title}〉` : '上架作品'}</h3>
      <fieldset className="sf-fieldset" disabled={busy}>
        <legend>放在哪裡</legend>
        <div className="sf-form-grid">
          <label>
            成果牆分類 *
            <small className="sf-hint">成果牆左邊的列表，例如「115上」</small>
            <select required value={course} onChange={e => { setCourse(e.target.value); setLesson(''); }}>
              {data.courses.length === 0 && <option value="">還沒有分類，請先在右邊新增</option>}
              {data.courses.map(c => <option key={c.id} value={c.id}>{categoryName(c.category)}／{c.name}</option>)}
            </select>
          </label>
          <div className="works-new-course">
            <span>新增分類</span>
            <div>
              {data.categories.length > 1 && (
                <select value={newCourse.category} onChange={e => setNewCourse({ ...newCourse, category: e.target.value })}>
                  {data.categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              )}
              <input
                value={newCourse.name}
                maxLength={100}
                placeholder="例如 115上"
                onChange={e => setNewCourse({ ...newCourse, name: e.target.value })}
              />
              <button type="button" className="sf-button" onClick={() => void addCourse()} disabled={!newCourse.name.trim()}>新增</button>
            </div>
          </div>
          <label className="lesson-span">
            來自哪一堂社課（選填）
            <select value={lesson} onChange={e => setLesson(e.target.value ? Number(e.target.value) : '')}>
              <option value="">不指定</option>
              {lessons.map(l => <option key={l.id} value={l.id}>{l.startTime.slice(5, 10).replace('-', '/')} {lessonLabel(l)}</option>)}
            </select>
          </label>
        </div>
      </fieldset>

      <fieldset className="sf-fieldset" disabled={busy}>
        <legend>作品</legend>
        <div className="sf-form-grid">
          <label>
            標題 *
            <input required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} />
          </label>
          <label>
            作者
            <small className="sf-hint">顯示用，例如「113CM組」</small>
            <input maxLength={100} value={author} onChange={e => setAuthor(e.target.value)} />
          </label>
        </div>
        <div className="sf-radio-row">
          <label><input type="radio" checked={type === 'image'} onChange={() => setType('image')} /> 圖片</label>
          <label><input type="radio" checked={type === 'video'} onChange={() => setType('video')} /> 影片</label>
          <span className="works-source-sep">｜</span>
          <label><input type="radio" checked={source === 'file'} onChange={() => setSource('file')} /> 上傳檔案</label>
          <label><input type="radio" checked={source === 'link'} onChange={() => setSource('link')} /> 貼連結</label>
        </div>
        {source === 'file' ? (
          <label>
            {type === 'image' ? '圖片' : `影片（MP4，${data.maxVideoMb} MB 以內）`}{initial?.hasFile ? '（不換就不用選）' : ' *'}
            <input type="file" accept={type === 'image' ? 'image/*' : 'video/mp4,video/webm,video/quicktime'} onChange={e => setFile(e.target.files?.[0] ?? null)} />
          </label>
        ) : (
          <label>
            連結 *
            <small className="sf-hint">{type === 'video' ? 'YouTube 連結會直接嵌入播放，縮圖也會自動抓' : '圖片的直接網址'}</small>
            <input type="url" required value={externalUrl} onChange={e => setExternalUrl(e.target.value)} placeholder="https://" />
          </label>
        )}
        {type === 'video' && (
          <label>
            縮圖（選填）
            <small className="sf-hint">YouTube 影片不用傳；上傳的影片沒有縮圖時，成果牆會顯示預設圖</small>
            <input type="file" accept="image/*" onChange={e => setThumbnail(e.target.files?.[0] ?? null)} />
          </label>
        )}
        <label className="sf-check">
          <input type="checkbox" checked={isPublished} onChange={e => setIsPublished(e.target.checked)} />
          上架（取消勾選就先不顯示在成果牆）
        </label>
      </fieldset>

      {progress !== null && (
        <div className="photo-progress" role="status">
          <span>上傳中 {Math.round(progress * 100)}%</span>
          <progress value={progress} max={1} />
        </div>
      )}
      {error && <p className="sf-error" role="alert">{error}</p>}
      <div className="sf-form-actions">
        <button type="button" className="sf-button" onClick={onCancel} disabled={busy}>取消</button>
        <button type="submit" className="sf-button is-primary" disabled={busy || !course}>儲存</button>
      </div>
    </form>
  );
}

export default function WorksManage() {
  const { isAuthenticated } = useAuth();
  const [data, setData] = useState<WorkManageData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editing, setEditing] = useState<number | 'new' | null>(null);

  const load = useCallback(() => {
    fetchWorkManage().then(setData).catch(err => setError(apiErrorMessage(err, '載入失敗')));
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

  const saved = (work: ManagedWork) => {
    setEditing(null);
    setNotice(`已儲存〈${work.title}〉。`);
    load();
  };

  const remove = async (work: ManagedWork) => {
    if (!window.confirm(`刪除〈${work.title}〉？按讚和留言會一起刪掉，找不回來。`)) return;
    try {
      await deleteWork(work.id);
      setNotice(`已刪除〈${work.title}〉。`);
      load();
    } catch (err) {
      setError(apiErrorMessage(err, '刪除失敗'));
    }
  };

  const form = (initial?: ManagedWork) => data && (
    <WorkForm
      key={initial?.id ?? 'new'}
      data={data}
      initial={initial}
      onSaved={saved}
      onCancel={() => setEditing(null)}
      onCourseCreated={load}
    />
  );

  return (
    <ClubLayout>
      {error && <p className="sf-error" role="alert">{error}</p>}
      {notice && <p className="sf-notice" role="status">{notice}</p>}
      {!error && !data && <p className="sf-muted">載入中…</p>}
      {data && (
        <>
          <p className="sf-lead">
            你可以管理：{data.categories.map(c => c.name).join('、')}的成果牆。按讚、留言、瀏覽數照常在成果牆上累積。
          </p>
          {editing === 'new' ? form() : (
            <button type="button" className="sf-button is-primary" onClick={() => setEditing('new')}>＋ 上架作品</button>
          )}

          <section className="sf-section">
            <h2 className="sf-section-title">作品（{data.works.length}）</h2>
            {data.works.length === 0 && <p className="sf-card sf-empty">還沒有作品。</p>}
            <div className="lesson-list">
              {data.works.map(work => (editing === work.id ? form(work) : (
                <article key={work.id} className={`sf-card works-manage-row${work.isPublished ? '' : ' is-draft'}`}>
                  {work.thumbnail ? <img src={work.thumbnail} alt="" /> : <div className="works-manage-noimg">{work.type === 'video' ? '影片' : '圖片'}</div>}
                  <div className="works-manage-main">
                    <div className="lesson-card-head">
                      <span className="lesson-category">{categoryName(work.category)}</span>
                      <span className="sf-muted">{data.courses.find(c => c.id === work.course)?.name}</span>
                      {!work.isPublished && <span className="sf-tag">未上架</span>}
                    </div>
                    <strong>{work.title}</strong>
                    <span className="sf-muted">
                      {work.author && `by ${work.author}・`}{work.type === 'video' ? (work.embedUrl ? 'YouTube' : '影片') : '圖片'}
                      ・👍 {work.likes}・💬 {work.commentCount}・👁 {work.views}
                    </span>
                    {work.lesson && <Link to={`/club/lessons/${work.lesson.id}`}>來自 {lessonLabel(work.lesson)}</Link>}
                    <div className="sf-form-actions lesson-actions">
                      <button type="button" className="sf-button" onClick={() => setEditing(work.id)}>修改</button>
                      <button type="button" className="sf-button is-danger" onClick={() => void remove(work)}>刪除</button>
                      <Link className="sf-button" to={`/club/works?category=${work.category}`}>看成果牆</Link>
                    </div>
                  </div>
                </article>
              )))}
            </div>
          </section>
        </>
      )}
    </ClubLayout>
  );
}
