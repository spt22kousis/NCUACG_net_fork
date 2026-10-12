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

export interface FestivalDetail extends Festival {
  plays: Play[];
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
