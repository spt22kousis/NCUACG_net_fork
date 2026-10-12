// frontend/src/api/songfest.ts
// 歌謠祭 API 的型別與呼叫（對應後端 NCUACG/songfest/views.py）
import { api } from './client';

export interface Festival {
  id: number;
  name: string;          // 例如 114下期末
  date: string;          // YYYY-MM-DD
  kind: 'hall' | 'ktv';  // 大講堂排歌單 / KTV 當天點歌
  venue: string;
  startTime: string | null; // HH:MM
  endTime: string | null;
  description: string;
  playCount: number;
  setlistPublic: boolean; // 排歌組已經公布排好的歌單
}

export interface Play {
  position: number;
  songSource: string;
  visualSource: string;
  title: string;
  dvdCode: string | null; // 只有剛好對到一支舊曲時才有
  editor: string | null;
  isCredits: boolean;     // 結尾的 5 秒畫面合輯影片
}

export interface PublicSession {
  name: string;
  isTest: boolean;
  startTime: string;
  entries: { position: number; title: string; songSource: string; visualSource: string; label: string }[];
}

export interface FestivalDetail extends Festival {
  plays: Play[];
  sessions: PublicSession[]; // 公布的排好歌單；沒公布是空陣列
}

export interface Track {
  dvdCode: string;
  songSource: string;
  visualSource: string;
  title: string;
  artist: string;
  editor: string;
  duration: number | null; // 秒
  group: string;           // 五十音分類，例如「あ」「特攝」
  playCount: number;       // 以「歌」為單位，同一首歌的不同版本共用
  recentPlayCount: number; // 近 4 年
  lastPlayed: string | null;
}

export interface TrackPage {
  count: number;
  page: number;
  pageCount: number;
  results: Track[];
}

export interface TrackGroup {
  group: string;
  count: number;
}

export interface RankedSong {
  rank: number;
  songSource: string;
  title: string;
  playCount: number;
  lastPlayed: string;
}

export type TrackSort = 'index' | 'newest' | 'popular';

export interface TrackQuery {
  q?: string;
  group?: string;
  sort?: TrackSort;
  page?: number;
  pageSize?: number;
}

export async function fetchFestivals(): Promise<Festival[]> {
  return (await api.get<Festival[]>('/songfest/festivals/')).data;
}

export async function fetchFestival(id: number): Promise<FestivalDetail> {
  return (await api.get<FestivalDetail>(`/songfest/festivals/${id}/`)).data;
}

export async function fetchTracks(query: TrackQuery, signal?: AbortSignal): Promise<TrackPage> {
  const params = {
    q: query.q || undefined,
    group: query.group || undefined,
    sort: query.sort || undefined,
    page: query.page,
    page_size: query.pageSize,
  };
  return (await api.get<TrackPage>('/songfest/tracks/', { params, signal })).data;
}

export async function fetchTrackGroups(): Promise<TrackGroup[]> {
  return (await api.get<TrackGroup[]>('/songfest/tracks/groups/')).data;
}

export async function fetchRanking(years = 4, limit = 10): Promise<RankedSong[]> {
  return (await api.get<RankedSong[]>('/songfest/ranking/', { params: { years, limit } })).data;
}

/** 253 → 4:13 */
export function formatDuration(seconds: number | null): string {
  if (seconds == null) return '–';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

/** 2026-06-14 → 2026/06/14（六）；日期只是日曆上的一天，不做時區換算 */
export function formatDate(iso: string, withWeekday = false): string {
  const [y, m, d] = iso.split('-').map(Number);
  const text = `${y}/${String(m).padStart(2, '0')}/${String(d).padStart(2, '0')}`;
  if (!withWeekday) return text;
  return `${text}（${WEEKDAYS[new Date(y, m - 1, d).getDay()]}）`;
}

/** 今天（本地時間）的 YYYY-MM-DD，用來分出「即將舉辦」與「歷屆」 */
export function todayIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

// ── 新曲投稿（對應後端 NCUACG/songfest/submission_views.py）──────────────────

export type SubmissionSource = 'member' | 'partner' | 'guest';
export type SubmissionStatus = 'reported' | 'uploaded' | 'overdue' | 'withdrawn' | 'rejected';
export type FiveSecStatus = 'none' | 'pending' | 'uploaded' | 'cancelled';

export const STATUS_LABEL: Record<SubmissionStatus, string> = {
  reported: '已報曲',
  uploaded: '已繳交',
  overdue: '逾期未繳交',
  withdrawn: '窗歌',
  rejected: '退件',
};

export const FIVE_SEC_LABEL: Record<FiveSecStatus, string> = {
  none: '不放',
  pending: '待繳',
  uploaded: '已繳',
  cancelled: '取消',
};

export interface SongfestFestival extends Festival {
  reportDeadline: string | null;
  partnerDeadline: string | null;
  withdrawDeadline: string | null;
  uploadDeadline: string | null;
  guestDeadline: string | null;
  reportOpen: { member: boolean; partner: boolean };
  partnerName: string;
  partnerLimit: number;
  rules: string;
  guestFormUrl: string;
  guestInfo: string;
}

export interface ActiveFestival {
  festival: SongfestFestival | null;
  viewer: { banReason: string | null; isStaff: boolean } | null; // 沒登入時是 null
}

export interface SubmissionPublic {
  id: number;
  source: SubmissionSource;
  sourceLabel: string;
  editorName: string;
  songSource: string;
  visualSource: string;
  title: string;
  artist: string;
  attributes: string;
  songLink: string;
  remarks: string;
  restrictedWork: boolean;
  fiveSec: boolean;
  isBackup: boolean; // 合作社團的備曲
  status: SubmissionStatus;
  isMine: boolean;
  commentCount: number;
  createdAt: string;
}

export interface SubmissionPermissions {
  canEditSong: boolean;    // 報曲截止前：可以改歌
  canDelete: boolean;      // 報曲截止前：可以直接刪除
  canWithdraw: boolean;    // 報曲截止後：只能窗歌
  canEditDetails: boolean; // 繳交截止前：可以填檔案、改說明
  withdrawIsLate: boolean; // 現在窗歌會被記罰則
}

export interface MySubmission extends SubmissionPublic {
  fileLink: string;
  duration: number | null;
  uploadedAt: string | null;
  fileUpdatedAt: string | null;
  fiveSecLink: string;
  fiveSecStatus: FiveSecStatus;
  uploadDeadline: string | null;
  extendedUntil: string | null;
  chainWith: number | null;
  withdrawnAt: string | null;
  rejectReason: string;
  permissions: SubmissionPermissions;
}

export interface SubmissionWarning {
  code: string;
  message: string;
}

export interface StaffSubmission extends MySubmission {
  submitterName: string | null;
  contactEmail: string;
  guestMessage: string;
  libraryConsent: boolean;
  fileChecked: boolean;
  penaltyWaived: boolean;
  isOffense: boolean;
  changedAfterUpload: boolean;
  warnings: SubmissionWarning[];
}

export interface ManageSummary {
  active: number;
  bySource: Record<SubmissionSource, number>; // 合作社團只算正選
  partnerBackups: number;
  partnerLimit: number;
  uploaded: number;
  overdue: number;
  withdrawn: number;
  rejected: number;
  fiveSecRequested: number;
  fiveSecUploaded: number;
  totalDuration: number;
  missingDuration: number;
}

export interface ManageOverview {
  festival: SongfestFestival;
  summary: ManageSummary;
  submissions: StaffSubmission[];
}

export interface SubmissionComment {
  id: number;
  username: string;
  content: string;
  createdAt: string;
  canDelete: boolean;
}

/** 送出投稿或修改時的欄位；修改時只送有變的 */
export interface SubmissionInput {
  source?: 'member' | 'partner';
  songSource?: string;
  visualSource?: string;
  title?: string;
  artist?: string;
  attributes?: string;
  songLink?: string;
  remarks?: string;
  restrictedWork?: boolean;
  fiveSec?: boolean;
  isBackup?: boolean;
  chainWith?: number | null;
  fileLink?: string;
  duration?: number | null;
  fiveSecLink?: string;
}

export interface StaffUpdate {
  fileChecked?: boolean;
  extendedUntil?: string | null;
  isRejected?: boolean;
  rejectReason?: string;
  penaltyWaived?: boolean;
  duration?: number | null;
  libraryConsent?: boolean;
}

export async function fetchActiveFestival(): Promise<ActiveFestival> {
  return (await api.get<ActiveFestival>('/songfest/active/')).data;
}

export async function fetchReportThread(festivalId: number): Promise<SubmissionPublic[]> {
  return (await api.get<SubmissionPublic[]>(`/songfest/festivals/${festivalId}/submissions/`)).data;
}

export async function fetchMySubmissions(festivalId: number): Promise<MySubmission[]> {
  return (await api.get<MySubmission[]>(`/songfest/festivals/${festivalId}/my-submissions/`)).data;
}

export async function createSubmission(festivalId: number, input: SubmissionInput): Promise<MySubmission> {
  return (await api.post<MySubmission>(`/songfest/festivals/${festivalId}/submissions/`, input)).data;
}

export async function updateSubmission(id: number, input: SubmissionInput): Promise<MySubmission> {
  return (await api.patch<MySubmission>(`/songfest/submissions/${id}/`, input)).data;
}

export async function deleteSubmission(id: number): Promise<void> {
  await api.delete(`/songfest/submissions/${id}/`);
}

export async function withdrawSubmission(id: number): Promise<MySubmission> {
  return (await api.post<MySubmission>(`/songfest/submissions/${id}/withdraw/`)).data;
}

export async function fetchSubmissionComments(id: number): Promise<SubmissionComment[]> {
  return (await api.get<SubmissionComment[]>(`/songfest/submissions/${id}/comments/`)).data;
}

export async function postSubmissionComment(id: number, content: string): Promise<SubmissionComment> {
  return (await api.post<SubmissionComment>(`/songfest/submissions/${id}/comments/`, { content })).data;
}

export async function deleteSubmissionComment(commentId: number): Promise<void> {
  await api.delete(`/songfest/submission-comments/${commentId}/`);
}

export interface ManageFestival {
  id: number;
  name: string;
  date: string;
}

export async function fetchManageFestivals(): Promise<ManageFestival[]> {
  return (await api.get<ManageFestival[]>('/songfest/manage/festivals/')).data;
}

export async function fetchManageOverview(festivalId: number): Promise<ManageOverview> {
  return (await api.get<ManageOverview>(`/songfest/festivals/${festivalId}/manage/`)).data;
}

export async function staffUpdateSubmission(id: number, input: StaffUpdate): Promise<StaffSubmission> {
  return (await api.patch<StaffSubmission>(`/songfest/manage/submissions/${id}/`, input)).data;
}

/** 下載檔案：要帶登入 token，所以用 axios 拿檔案再交給瀏覽器存檔 */
async function downloadFile(path: string, filename: string, params?: Record<string, string>): Promise<void> {
  const res = await api.get<Blob>(path, { responseType: 'blob', params });
  const url = URL.createObjectURL(res.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function downloadSubmissionCsv(festivalId: number, filename: string): Promise<void> {
  await downloadFile(`/songfest/festivals/${festivalId}/manage/export/`, filename);
}

export async function importGuestForm(festivalId: number, file: File): Promise<{ lines: string[]; warnings: string[] }> {
  const form = new FormData();
  form.append('file', file);
  return (await api.post(`/songfest/festivals/${festivalId}/manage/import-guests/`, form)).data;
}

/** 2026-10-02T21:00:00+08:00 → 10/02（五）21:00 */
export function formatDateTime(iso: string | null, withYear = false): string {
  if (!iso) return '未設定';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  const date = `${withYear ? `${d.getFullYear()}/` : ''}${pad(d.getMonth() + 1)}/${pad(d.getDate())}`;
  return `${date}（${WEEKDAYS[d.getDay()]}）${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function isPast(iso: string | null): boolean {
  return iso !== null && new Date(iso).getTime() < Date.now();
}

/** 「4:25」「1:02:03」或純秒數 → 秒；看不懂回 null */
export function parseDuration(text: string): number | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  if (/^\d+$/.test(trimmed)) return Number(trimmed);
  const parts = trimmed.split(':').map(Number);
  if (parts.some(n => Number.isNaN(n)) || parts.length < 2 || parts.length > 3) return null;
  return parts.reduce((total, n) => total * 60 + n, 0);
}

/** 7213 → 2:00:13 */
export function formatLongDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/** 把 DRF 回的錯誤（{欄位: [訊息]} 或 {detail}）攤平成一句話 */
export function apiErrorMessage(err: unknown, fallback = '送出失敗，請稍後再試'): string {
  const data = (err as { response?: { data?: unknown } })?.response?.data;
  if (data && typeof data === 'object') {
    const messages = Object.values(data as Record<string, unknown>).flatMap(v => (Array.isArray(v) ? v : [v]));
    const text = messages.filter(m => typeof m === 'string').join(' ');
    if (text) return text;
  }
  return fallback;
}

// ── 排歌台（對應後端 NCUACG/songfest/setlist_views.py）──────────────────────

export type EntryKind = 'new' | 'old' | 'custom';
export type CustomType = 'cm' | 'credits' | 'other';

export interface SetlistEntry {
  id: number;
  position: number;
  kind: EntryKind;
  customType: CustomType | '';
  title: string;
  songSource: string;
  visualSource: string;
  editor: string;
  dvdCode: string | null;
  submissionId: number | null;
  source: SubmissionSource | null;
  sourceLabel: string;     // 新曲、舊曲、亂入、健行科大、CM、結尾影片…
  isBackup: boolean;
  duration: number | null;
  endsAt: string;          // 這首播完的時刻 HH:MM:SS（含每首誤差）
  heat: number | null;
  note: string;
  lastPlayed: string | null;
  recentPlayCount: number | null;
  warnings: string[];
}

export interface SetlistSession {
  id: number;
  name: string;
  isTest: boolean;
  startTime: string;
  endTime: string | null;
  targetSeconds: number | null;
  toleranceSeconds: number;
  speechSeconds: number;
  bufferSeconds: number;
  perSongErrorSeconds: number;
  rounds: number;
  ownerId: number | null;
  ownerName: string | null;
  totalSeconds: number;
  errorSeconds: number;
  speechAt: string;
  endAt: string;
  latestEndAt: string;
  over: boolean;
  under: boolean;
  suggestedStart: string | null;
  warnings: string[];
  entries: SetlistEntry[];
}

export interface PoolItem {
  submissionId: number;
  title: string;
  songSource: string;
  visualSource: string;
  editor: string;
  source: SubmissionSource;
  sourceLabel: string;
  isBackup: boolean;
  duration: number | null;
  status: SubmissionStatus;
  chainWith: number | null;
}

export interface SetlistBoard {
  festival: SongfestFestival & { setlistPublic: boolean };
  staff: { id: number; name: string; role: string }[];
  sessions: SetlistSession[];
  pool: PoolItem[];
  warnings: string[];
}

export interface EntryInput {
  kind?: EntryKind;
  submissionId?: number;
  dvdCode?: string;
  customType?: CustomType;
  title?: string;
  source?: string;
  editor?: string;
  duration?: number | null;
  sessionId?: number;
  position?: number;
  heat?: number | null;
  note?: string;
}

export interface SessionInput {
  startTime?: string;
  endTime?: string | null;
  targetSeconds?: number | null;
  speechSeconds?: number;
  bufferSeconds?: number;
  perSongErrorSeconds?: number;
  rounds?: number;
  ownerId?: number | null;
}

export async function fetchSetlist(festivalId: number): Promise<SetlistBoard> {
  return (await api.get<SetlistBoard>(`/songfest/festivals/${festivalId}/setlist/`)).data;
}

export async function autoDistribute(festivalId: number): Promise<SetlistBoard & { placed: number }> {
  return (await api.post(`/songfest/festivals/${festivalId}/setlist/auto/`)).data;
}

export async function updateSession(sessionId: number, input: SessionInput): Promise<SetlistBoard> {
  return (await api.patch<SetlistBoard>(`/songfest/setlist/sessions/${sessionId}/`, input)).data;
}

export async function addEntry(sessionId: number, input: EntryInput): Promise<SetlistBoard> {
  return (await api.post<SetlistBoard>(`/songfest/setlist/sessions/${sessionId}/entries/`, input)).data;
}

export async function updateEntry(entryId: number, input: EntryInput): Promise<SetlistBoard> {
  return (await api.patch<SetlistBoard>(`/songfest/setlist/entries/${entryId}/`, input)).data;
}

export async function deleteEntry(entryId: number): Promise<SetlistBoard> {
  return (await api.delete<SetlistBoard>(`/songfest/setlist/entries/${entryId}/`)).data;
}

export async function fetchFillSuggestions(festivalId: number, seconds: number): Promise<Track[]> {
  return (await api.get<Track[]>(`/songfest/festivals/${festivalId}/setlist/suggest/`, { params: { seconds } })).data;
}

export type SetlistExport = 'public' | 'workspace' | 'order' | 'credits';

export async function downloadSetlist(festivalId: number, type: SetlistExport, filename: string): Promise<void> {
  await downloadFile(`/songfest/festivals/${festivalId}/setlist/export/`, filename, { type });
}

export async function publishSetlist(festivalId: number, isPublic: boolean): Promise<{ setlistPublic: boolean }> {
  return (await api.post(`/songfest/festivals/${festivalId}/setlist/publish/`, { public: isPublic })).data;
}

export async function writePlays(festivalId: number): Promise<{ written: number }> {
  return (await api.post(`/songfest/festivals/${festivalId}/setlist/write-plays/`)).data;
}

export interface LibraryCandidate {
  submissionId: number;
  title: string;
  songSource: string;
  visualSource: string;
  artist: string;
  editor: string;
  source: SubmissionSource;
  duration: number | null;
  libraryConsent: boolean;
  dvdCode: string | null; // 已經收進歌單的話
}

export async function fetchLibraryCandidates(festivalId: number): Promise<LibraryCandidate[]> {
  return (await api.get<LibraryCandidate[]>(`/songfest/festivals/${festivalId}/library/`)).data;
}

export async function addToLibrary(festivalId: number, submissionIds: number[]): Promise<{ added: string[]; candidates: LibraryCandidate[] }> {
  return (await api.post(`/songfest/festivals/${festivalId}/library/add/`, { submissionIds })).data;
}

export async function downloadLibraryCsv(festivalId: number, filename: string): Promise<void> {
  await downloadFile(`/songfest/festivals/${festivalId}/library/export/`, filename);
}

export interface LibraryConsentItem {
  submissionId: number;
  festivalName: string;
  title: string;
  consent: boolean;
}

export async function fetchMyLibraryConsent(): Promise<LibraryConsentItem[]> {
  return (await api.get<LibraryConsentItem[]>('/songfest/library-consent/')).data;
}

export async function setLibraryConsent(submissionId: number, consent: boolean): Promise<void> {
  await api.post(`/songfest/submissions/${submissionId}/library-consent/`, { consent });
}
