// frontend/src/pages/club/LessonExtras.tsx
// 單堂社課頁下方：這堂課的照片（登入才看得到）與成果牆作品
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchLessonWorks, fetchPhotos, type Lesson, type ManagedWork, type Photo } from '../../api/club';
import { useAuth } from '../../contexts/auth';
import PhotoGallery from './PhotoGallery';

export default function LessonExtras({ lesson }: { lesson: Lesson }) {
  const { isAuthenticated } = useAuth();
  const [photos, setPhotos] = useState<Photo[] | null>(null);
  const [canUpload, setCanUpload] = useState(false);
  const [works, setWorks] = useState<ManagedWork[]>([]);

  useEffect(() => {
    fetchLessonWorks(lesson.id).then(setWorks).catch(() => setWorks([]));
  }, [lesson.id]);

  useEffect(() => {
    if (!isAuthenticated) return;
    fetchPhotos({ lesson: lesson.id })
      .then(res => {
        setPhotos(res.photos);
        setCanUpload(Boolean(res.upload?.categories.some(c => c.id === lesson.category)));
      })
      .catch(() => setPhotos([]));
  }, [isAuthenticated, lesson.id, lesson.category]);

  const uploadLink = `/photos?kind=lesson&category=${lesson.category}&lesson=${lesson.id}&upload=1`;

  return (
    <>
      <section className="sf-section">
        <div className="sf-section-row">
          <h2 className="sf-section-title">照片</h2>
          {canUpload && <Link to={uploadLink} className="sf-button">上傳照片</Link>}
        </div>
        {!isAuthenticated && <p className="sf-muted">照片只有社員看得到，請先<Link to="/login">登入</Link>。</p>}
        {photos?.length === 0 && <p className="sf-muted">這堂課還沒有照片。</p>}
        {photos && photos.length > 0 && <PhotoGallery photos={photos} onChange={setPhotos} />}
      </section>

      {works.length > 0 && (
        <section className="sf-section">
          <h2 className="sf-section-title">這堂課的成果</h2>
          <div className="lesson-works">
            {works.map(work => (
              <Link key={work.id} to={`/club/works?category=${lesson.category}`} className="sf-card lesson-work">
                {work.thumbnail ? <img src={work.thumbnail} alt="" loading="lazy" /> : <div className="works-manage-noimg">{work.type === 'video' ? '影片' : '圖片'}</div>}
                <span>{work.title}</span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
