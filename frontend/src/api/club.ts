// frontend/src/api/club.ts
// 社課堂次、公告與行事曆的型別與呼叫（對應後端 NCUACG/club/lesson_views.py 與 event/views.py 的 calendar）
import { api } from './client';

/** 社課種類，對應後端 club.Course.CATEGORY_CHOICES */
export const COURSE_CATEGORIES: { id: string; name: string }[] = [
  { id: 'anime', name: '動畫播放組' },
  { id: 'otaku', name: '御宅藝' },
  { id: 'model', name: '模型製作' },
  { id: 'art', name: '繪畫' },
  { id: 'trpg', name: 'TRPG' },
  { id: 'mv', name: 'MV剪輯' },
  { id: 'seiyuu', name: '聲優' },
  { id: 'railway', name: '鐵道' },
];

export function categoryName(id: string): string {
  return COURSE_CATEGORIES.find(c => c.id === id)?.name ?? id;
}

export interface Lesson {
  id: number;
  category: string;
  categoryName: string;
  number: number | null;   // 第幾堂
  title: string;
  startTime: string;       // ISO 8601
  endTime: string | null;
  location: string;
  content: string;
  notes: string;
  prerequisites: string;   // 一行一項
  requires: { id: number; number: number | null; title: string }[];
  slidesUrl: string;
  // 以下只有這個社課的負責人或幹部拿得到
  discordRole?: string;
  isPublished?: boolean;
  discordText?: string;
  canEdit?: boolean;
}

export interface LessonInput {
  category?: string;
  number?: number | null;
  title?: string;
  startTime?: string;
  endTime?: string | null;
  location?: string;
  content?: string;
  notes?: string;
  prerequisites?: string;
  requires?: number[];
  discordRole?: string;
  slidesUrl?: string;
  isPublished?: boolean;
}

export interface LessonManageData {
  categories: { id: string; name: string }[];
  defaults: Record<string, { location: string; discordRole: string; nextNumber: number }>;
  lessons: Lesson[];
}

/** 某社課所有公開的堂次（含過去的），依時間排序 */
export async function fetchLessons(category: string): Promise<Lesson[]> {
  return (await api.get<Lesson[]>('/club/lessons/', { params: { category } })).data;
}

/** 還沒結束、N 天內開始的堂次 */
export async function fetchUpcomingLessons(days = 30): Promise<Lesson[]> {
  return (await api.get<Lesson[]>('/club/lessons/', { params: { days } })).data;
}

export async function fetchLesson(id: number): Promise<Lesson> {
  return (await api.get<Lesson>(`/club/lessons/${id}/`)).data;
}

export async function fetchLessonManage(): Promise<LessonManageData> {
  return (await api.get<LessonManageData>('/club/lessons/manage/')).data;
}

export async function createLesson(input: LessonInput): Promise<Lesson> {
  return (await api.post<Lesson>('/club/lessons/manage/', input)).data;
}

export async function updateLesson(id: number, input: LessonInput): Promise<Lesson> {
  return (await api.patch<Lesson>(`/club/lessons/${id}/`, input)).data;
}

export async function deleteLesson(id: number): Promise<void> {
  await api.delete(`/club/lessons/${id}/`);
}

// ── 行事曆 ──────────────────────────────────────────────────────────────────

export interface CalendarItem {
  id: string;
  kind: 'event' | 'lesson' | 'songfest';
  title: string;
  start: string;
  end: string | null;
  allDay: boolean;
  location: string;
  category: string | null;
  link: string;
}

/** from、to 是 YYYY-MM-DD，to 不含 */
export async function fetchCalendar(from: string, to: string): Promise<CalendarItem[]> {
  return (await api.get<CalendarItem[]>('/event/calendar/', { params: { from, to } })).data;
}

// ── 顯示 ────────────────────────────────────────────────────────────────────

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];
const pad = (n: number) => String(n).padStart(2, '0');

/** 10/12（日）18:00~20:00；跨日才寫出結束日期 */
export function formatLessonTime(lesson: Pick<Lesson, 'startTime' | 'endTime'>, withYear = false): string {
  const start = new Date(lesson.startTime);
  const date = `${withYear ? `${start.getFullYear()}/` : ''}${start.getMonth() + 1}/${start.getDate()}`;
  let text = `${date}（${WEEKDAYS[start.getDay()]}）${pad(start.getHours())}:${pad(start.getMinutes())}`;
  if (lesson.endTime) {
    const end = new Date(lesson.endTime);
    const sameDay = end.toDateString() === start.toDateString();
    text += sameDay
      ? `~${pad(end.getHours())}:${pad(end.getMinutes())}`
      : `~${end.getMonth() + 1}/${end.getDate()} ${pad(end.getHours())}:${pad(end.getMinutes())}`;
  }
  return text;
}

/** 第 3 堂：高鐵與捷運 */
export function lessonLabel(lesson: { number: number | null; title: string }): string {
  return lesson.number ? `第 ${lesson.number} 堂：${lesson.title}` : lesson.title;
}

/** ISO → <input type="datetime-local"> 的值（本地時間） */
export function toLocalInput(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** <input type="datetime-local"> 的值 → ISO（帶時區），空字串回 null */
export function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

/** Date → YYYY-MM-DD（本地時間） */
export function isoDay(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// ── 照片（對應後端 NCUACG/club/photo_views.py）──────────────────────────────

export type PhotoKind = 'lesson' | 'songfest' | 'daily';

export const PHOTO_KIND_LABEL: Record<PhotoKind, string> = { lesson: '社課', songfest: '歌謠祭', daily: '日常' };

export interface Photo {
  id: number;
  kind: PhotoKind;
  category: string;
  lesson: { id: number; number: number | null; title: string } | null;
  festival: { id: number; name: string } | null;
  topic: string;
  groupLabel: string;   // 鐵道社課、歌謠祭 115上期末、社遊
  caption: string;
  takenOn: string;      // YYYY-MM-DD
  width: number;
  height: number;
  url: string;          // 帶簽章的網址，當天與隔天有效
  thumbUrl: string;
  canEdit: boolean;
}

export interface PhotoUploadOptions {
  categories: { id: string; name: string }[];        // 我負責的社課
  festivals: { id: number; name: string; date: string }[]; // 我是排歌組的場次（幹部是全部）
  daily: boolean;                                   // 可以傳日常照片（幹部）
  topics: string[];                                 // 用過的日常分類
}

export interface PhotoPage {
  photos: Photo[];
  total: number;
  hasMore: boolean;
  topics: string[];
  upload: PhotoUploadOptions | null; // 什麼都不能傳就是 null
}

export interface PhotoFilter {
  kind?: PhotoKind | '';
  category?: string;
  lesson?: number;
  festival?: number;
  topic?: string;
  page?: number;
  limit?: number;
}

export interface PhotoInput {
  kind?: PhotoKind;
  category?: string;
  lesson?: number | null;
  festival?: number | null;
  topic?: string;
  takenOn?: string;
  caption?: string;
}

export async function fetchPhotos(filter: PhotoFilter = {}): Promise<PhotoPage> {
  const params = Object.fromEntries(Object.entries(filter).filter(([, v]) => v !== undefined && v !== ''));
  return (await api.get<PhotoPage>('/club/photos/', { params })).data;
}

/** 一次傳一張，才能顯示進度、也不會碰到伺服器單次上傳的大小限制 */
export async function uploadPhoto(image: Blob, input: PhotoInput, onProgress?: (ratio: number) => void): Promise<Photo> {
  const form = new FormData();
  form.append('image', image, 'photo.jpg');
  for (const [key, value] of Object.entries(input)) {
    if (value !== undefined && value !== null && value !== '') form.append(key, String(value));
  }
  const res = await api.post<Photo>('/club/photos/', form, {
    onUploadProgress: e => { if (onProgress && e.total) onProgress(e.loaded / e.total); },
  });
  return res.data;
}

export async function updatePhoto(id: number, input: PhotoInput): Promise<Photo> {
  return (await api.patch<Photo>(`/club/photos/${id}/`, input)).data;
}

export async function deletePhoto(id: number): Promise<void> {
  await api.delete(`/club/photos/${id}/`);
}

/**
 * 上傳前先在瀏覽器把照片縮到長邊 maxSide，手機拍的 5MB 照片會變成幾百 KB。
 * 讀不了的格式（例如部分 HEIC）就原檔上傳，交給後端判斷。
 */
export async function resizeImage(file: File, maxSide = 1920): Promise<Blob> {
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const ctx = canvas.getContext('2d');
    if (!ctx) return file;
    ctx.fillStyle = '#FFFFFF'; // 透明 PNG 鋪白底
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.88));
    return blob ?? file;
  } catch {
    return file;
  }
}

// ── 成果牆上架（對應後端 NCUACG/club/work_manage_views.py）──────────────────

export interface ManagedWork {
  id: number;
  course: string;          // 成果牆分類的 slug
  category: string;
  title: string;
  author: string;
  type: 'video' | 'image';
  url: string;
  thumbnail: string | null;
  embedUrl: string | null; // YouTube
  lesson: { id: number; number: number | null; title: string } | null;
  isPublished: boolean;
  externalUrl: string;
  hasFile: boolean;
  likes: number;
  views: number;
  commentCount: number;
  createdAt: string;
}

export interface WorkCourse {
  id: string;   // slug
  name: string;
  color: 'blue' | 'green';
  category: string;
  workCount: number;
}

export interface WorkManageData {
  categories: { id: string; name: string }[];
  courses: WorkCourse[];
  works: ManagedWork[];
  lessons: { id: number; category: string; number: number | null; title: string; startTime: string }[];
  maxVideoMb: number;
}

export interface WorkInput {
  course?: string;
  title?: string;
  author?: string;
  type?: 'video' | 'image';
  externalUrl?: string;
  lesson?: number | '';   // 空字串 = 不連結
  isPublished?: boolean;
  file?: Blob | File;
  thumbnail?: Blob | File;
}

function workForm(input: WorkInput): FormData {
  const form = new FormData();
  for (const [key, value] of Object.entries(input)) {
    if (value === undefined) continue;
    if (value instanceof Blob) {
      form.append(key, value, value instanceof File ? value.name : `${key}.jpg`);
    } else {
      form.append(key, String(value));
    }
  }
  return form;
}

export async function fetchWorkManage(): Promise<WorkManageData> {
  return (await api.get<WorkManageData>('/club/works/manage/')).data;
}

export async function createWork(input: WorkInput, onProgress?: (ratio: number) => void): Promise<ManagedWork> {
  return (await api.post<ManagedWork>('/club/works/manage/', workForm(input), {
    onUploadProgress: e => { if (onProgress && e.total) onProgress(e.loaded / e.total); },
  })).data;
}

export async function updateWork(id: number, input: WorkInput, onProgress?: (ratio: number) => void): Promise<ManagedWork> {
  return (await api.patch<ManagedWork>(`/club/works/manage/${id}/`, workForm(input), {
    onUploadProgress: e => { if (onProgress && e.total) onProgress(e.loaded / e.total); },
  })).data;
}

export async function deleteWork(id: number): Promise<void> {
  await api.delete(`/club/works/manage/${id}/`);
}

export async function createWorkCourse(category: string, name: string): Promise<WorkCourse> {
  return (await api.post<WorkCourse>('/club/courses/manage/', { category, name })).data;
}

/** 某一堂社課的成果（公開） */
export async function fetchLessonWorks(lessonId: number): Promise<ManagedWork[]> {
  return (await api.get<ManagedWork[]>('/club/works/', { params: { lesson: lessonId } })).data;
}
