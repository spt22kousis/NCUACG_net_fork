// frontend/src/pages/club/PhotoGallery.tsx
// 照片縮圖格與全螢幕檢視（左右切換、鍵盤 ←→、Esc 關閉）。相簿頁、單堂社課頁、社課介紹彈窗共用。
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiErrorMessage } from '../../api/songfest';
import { deletePhoto, updatePhoto, type Photo } from '../../api/club';

interface Props {
  photos: Photo[];
  /** 改了說明或刪掉照片後通知外層更新 */
  onChange?: (photos: Photo[]) => void;
  /** 小尺寸（社課介紹彈窗用） */
  compact?: boolean;
}

/** 照片的來源連結：社課那一堂、歌謠祭那一場 */
function sourceLink(photo: Photo) {
  if (photo.lesson) return <Link to={`/club/lessons/${photo.lesson.id}`}>{photo.lesson.title}</Link>;
  if (photo.festival) return <Link to={`/photos?kind=songfest&festival=${photo.festival.id}`}>{photo.groupLabel}</Link>;
  return <span>{photo.groupLabel}</span>;
}

function Viewer({ photos, index, onIndex, onClose, onChange }: {
  photos: Photo[]; index: number; onIndex: (i: number) => void; onClose: () => void;
  onChange?: (photos: Photo[]) => void;
}) {
  const photo = photos[index];
  const [caption, setCaption] = useState(photo.caption);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCaption(photo.caption);
    setEditing(false);
    setError(null);
  }, [photo]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (editing) return;
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft' && index > 0) onIndex(index - 1);
      if (e.key === 'ArrowRight' && index < photos.length - 1) onIndex(index + 1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [editing, index, photos.length, onClose, onIndex]);

  const save = async () => {
    try {
      const saved = await updatePhoto(photo.id, { caption: caption.trim() });
      onChange?.(photos.map(p => (p.id === saved.id ? saved : p)));
      setEditing(false);
    } catch (err) {
      setError(apiErrorMessage(err, '儲存失敗'));
    }
  };

  const remove = async () => {
    if (!window.confirm('刪除這張照片？刪掉就找不回來了。')) return;
    try {
      await deletePhoto(photo.id);
      const rest = photos.filter(p => p.id !== photo.id);
      onChange?.(rest);
      if (rest.length === 0) onClose();
      else onIndex(Math.min(index, rest.length - 1));
    } catch (err) {
      setError(apiErrorMessage(err, '刪除失敗'));
    }
  };

  return (
    <div className="photo-viewer" role="dialog" aria-modal="true" aria-label="照片" onClick={onClose}>
      <div className="photo-viewer-inner" onClick={e => e.stopPropagation()}>
        <div className="photo-viewer-top">
          <span>{index + 1} / {photos.length}</span>
          <a href={photo.url} target="_blank" rel="noreferrer">原圖</a>
          <button type="button" className="photo-viewer-close" onClick={onClose} aria-label="關閉">✕</button>
        </div>
        <div className="photo-viewer-stage">
          <button type="button" className="photo-viewer-nav" disabled={index === 0} onClick={() => onIndex(index - 1)} aria-label="上一張">‹</button>
          <img src={photo.url} alt={photo.caption || photo.groupLabel} />
          <button type="button" className="photo-viewer-nav" disabled={index === photos.length - 1} onClick={() => onIndex(index + 1)} aria-label="下一張">›</button>
        </div>
        <div className="photo-viewer-info">
          <div className="photo-viewer-meta">
            <span>{photo.takenOn.replace(/-/g, '/')}</span>
            {sourceLink(photo)}
          </div>
          {editing ? (
            <div className="photo-viewer-edit">
              <input value={caption} maxLength={200} onChange={e => setCaption(e.target.value)} placeholder="照片說明" autoFocus />
              <button type="button" className="sf-button is-primary" onClick={() => void save()}>儲存</button>
              <button type="button" className="sf-button" onClick={() => setEditing(false)}>取消</button>
            </div>
          ) : (
            photo.caption && <p>{photo.caption}</p>
          )}
          {photo.canEdit && !editing && (
            <div className="photo-viewer-actions">
              <button type="button" className="sf-link-button" onClick={() => setEditing(true)}>改說明</button>
              <button type="button" className="sf-link-button is-danger" onClick={() => void remove()}>刪除</button>
            </div>
          )}
          {error && <p className="sf-error">{error}</p>}
        </div>
      </div>
    </div>
  );
}

export default function PhotoGallery({ photos, onChange, compact = false }: Props) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <>
      <div className={`photo-grid${compact ? ' is-compact' : ''}`}>
        {photos.map((photo, i) => (
          <button key={photo.id} type="button" className="photo-thumb" onClick={() => setOpen(i)}>
            <img src={photo.thumbUrl} alt={photo.caption || photo.groupLabel} loading="lazy" />
          </button>
        ))}
      </div>
      {open !== null && photos[open] && (
        <Viewer photos={photos} index={open} onIndex={setOpen} onClose={() => setOpen(null)} onChange={onChange} />
      )}
    </>
  );
}
