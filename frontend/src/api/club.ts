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
