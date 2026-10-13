// frontend/src/pages/club/Photos.tsx
// 相簿：社課、歌謠祭、日常（社遊、聚餐…）的照片，只有登入的社員看得到。
// 篩選條件放在網址上（?kind=lesson&category=railway&lesson=3），從別的頁面可以直接連過來。
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiErrorMessage } from '../../api/songfest';
import {
  COURSE_CATEGORIES, PHOTO_KIND_LABEL, fetchPhotos, type Photo, type PhotoFilter, type PhotoKind, type PhotoPage,
} from '../../api/club';
import { useAuth } from '../../contexts/auth';
import ClubLayout from './ClubLayout';
import PhotoGallery from './PhotoGallery';
import PhotoUploader from './PhotoUploader';

const KINDS: PhotoKind[] = ['lesson', 'songfest', 'daily'];

/** 連續、同一個來源、同一天的照片放在同一組 */
function groupPhotos(photos: Photo[]) {
  const groups: { key: string; title: string; date: string; link: string | null; photos: Photo[] }[] = [];
  for (const photo of photos) {
    const source = photo.lesson ? `l${photo.lesson.id}` : photo.festival ? `f${photo.festival.id}` : `${photo.kind}:${photo.category}${photo.topic}`;
    const key = `${source}@${photo.takenOn}`;
    const last = groups[groups.length - 1];
    if (last?.key === key) {
      last.photos.push(photo);
      continue;
    }
    groups.push({
      key,
      title: photo.lesson ? `${photo.groupLabel}：${photo.lesson.title}` : photo.groupLabel,
      date: photo.takenOn,
      link: photo.lesson ? `/club/lessons/${photo.lesson.id}` : null,
      photos: [photo],
    });
  }
  return groups;
}

export default function Photos() {
  const { isAuthenticated } = useAuth();
  const [params, setParams] = useSearchParams();
  const filter = useMemo<PhotoFilter>(() => ({
    kind: (params.get('kind') as PhotoKind | null) ?? '',
    category: params.get('category') ?? '',
    lesson: Number(params.get('lesson')) || undefined,
    festival: Number(params.get('festival')) || undefined,
    topic: params.get('topic') ?? '',
  }), [params]);

  const [data, setData] = useState<PhotoPage | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(params.get('upload') === '1');

  const load = useCallback((pageNo: number) => {
    setError(null);
    fetchPhotos({ ...filter, page: pageNo })
      .then(res => setData(prev => (pageNo > 1 && prev ? { ...res, photos: [...prev.photos, ...res.photos] } : res)))
      .catch(err => setError(apiErrorMessage(err, '載入失敗')));
  }, [filter]);

  useEffect(() => {
    if (!isAuthenticated) return;
    setPage(1);
    load(1);
  }, [isAuthenticated, load]);

  const setFilter = (next: Record<string, string>) => {
    const clean = Object.fromEntries(Object.entries(next).filter(([, v]) => v));
    setParams(clean);
  };

  if (!isAuthenticated) {
    return (
      <ClubLayout>
        <p className="sf-card sf-empty">相簿只有社員看得到，請先<Link to="/login">登入</Link>。</p>
      </ClubLayout>
    );
  }

  const photos = data?.photos ?? [];
  const groups = groupPhotos(photos);
  const kind = filter.kind ?? '';
  // 從某一堂、某一場連過來時的篩選，顯示成可以取消的標籤
  const narrowed = filter.lesson || filter.festival;

  return (
    <ClubLayout>
      <p className="sf-lead">社課、歌謠祭和日常活動的照片，只有登入的社員看得到。點照片可以放大，左右切換。</p>

      {data?.upload && !uploading && (
        <button type="button" className="sf-button is-primary" onClick={() => setUploading(true)}>＋ 上傳照片</button>
      )}
      {data?.upload && uploading && (
        <PhotoUploader
          options={data.upload}
          initial={{ kind: kind || undefined, category: filter.category, lesson: filter.lesson, festival: filter.festival, topic: filter.topic }}
          onUploaded={() => { setPage(1); load(1); }}
          onClose={() => {
            setUploading(false);
            if (params.get('upload')) setFilter({ ...Object.fromEntries(params), upload: '' });
          }}
        />
      )}

      <div className="sf-chips photo-filter" role="group" aria-label="照片分類">
        <button type="button" className={kind === '' ? 'is-active' : ''} onClick={() => setFilter({})}>全部</button>
        {KINDS.map(k => (
          <button key={k} type="button" className={kind === k && !narrowed ? 'is-active' : ''} onClick={() => setFilter({ kind: k })}>
            {PHOTO_KIND_LABEL[k]}
          </button>
        ))}
      </div>
      {kind === 'lesson' && !narrowed && (
        <div className="sf-chips photo-filter" role="group" aria-label="社課">
          {COURSE_CATEGORIES.map(c => (
            <button
              key={c.id}
              type="button"
              className={filter.category === c.id ? 'is-active' : ''}
              onClick={() => setFilter({ kind: 'lesson', category: filter.category === c.id ? '' : c.id })}
            >
              {c.name}
            </button>
          ))}
        </div>
      )}
      {kind === 'daily' && (data?.topics.length ?? 0) > 0 && (
        <div className="sf-chips photo-filter" role="group" aria-label="日常分類">
          {data?.topics.map(t => (
            <button
              key={t}
              type="button"
              className={filter.topic === t ? 'is-active' : ''}
              onClick={() => setFilter({ kind: 'daily', topic: filter.topic === t ? '' : t })}
            >
              {t}
            </button>
          ))}
        </div>
      )}
      {narrowed && photos[0] && (
        <p className="photo-narrowed">
          只看：{groups[0]?.title}
          <button type="button" className="sf-link-button" onClick={() => setFilter({ kind })}>看全部</button>
        </p>
      )}

      {error && <p className="sf-error" role="alert">{error}</p>}
      {!error && !data && <p className="sf-muted">載入中…</p>}
      {data && photos.length === 0 && <p className="sf-card sf-empty">這裡還沒有照片。</p>}

      {groups.map(group => (
        <section key={group.key} className="photo-group">
          <h2 className="photo-group-title">
            {group.link ? <Link to={group.link}>{group.title}</Link> : group.title}
            <span className="sf-muted">{group.date.replace(/-/g, '/')}・{group.photos.length} 張</span>
          </h2>
          <PhotoGallery
            photos={group.photos}
            onChange={next => setData(prev => prev && {
              ...prev,
              photos: prev.photos.flatMap(p => (group.photos.some(g => g.id === p.id) ? next.filter(n => n.id === p.id) : [p])),
            })}
          />
        </section>
      ))}

      {data?.hasMore && (
        <div className="sf-form-actions photo-more">
          <button type="button" className="sf-button" onClick={() => { const next = page + 1; setPage(next); load(next); }}>
            載入更多（還有 {data.total - photos.length} 張）
          </button>
        </div>
      )}
    </ClubLayout>
  );
}
