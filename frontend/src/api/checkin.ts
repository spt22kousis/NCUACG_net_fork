// frontend/src/api/checkin.ts
// 活動簽到的管理 API（對應後端 NCUACG/checkin/views.py）。掃描頁是 public/scan/index.html，自己呼叫 API。
import { api } from './client';

export interface CheckinSlot {
  id: number;
  name: string;
  startsAt: string;
  endsAt: string;
  opensAt: string;   // 開放簽到
  closesAt: string;  // 停止簽到
  count: number;
}

export interface CheckinEvent {
  id: number;
  title: string;
  kind: 'songfest' | 'lesson' | 'other';
  festivalId: number | null;
  lessonId: number | null;
  date: string | null;
  slots: CheckinSlot[];
  total: number;    // 簽到筆數
  people: number;   // 不重複人數
  scanKey?: string; // 只有詳細資料才有
}

export interface CheckinRecord {
  id: number;
  slotId: number;
  slotName: string;
  studentId: string;
  source: string;
  scannedAt: string;
  device: string;
}

export interface CheckinEventDetail extends CheckinEvent {
  scanKey: string;
  records: CheckinRecord[];
}

export interface CheckinSources {
  festivals: { id: number; name: string; date: string }[];
  lessons: { id: number; title: string; date: string }[];
  custom: boolean; // 自訂活動只有幹部能建
}

export interface SlotInput {
  name?: string;
  startsAt?: string;
  endsAt?: string;
  opensAt?: string;
  closesAt?: string;
}

export async function fetchCheckinEvents(): Promise<{ events: CheckinEvent[]; sources: CheckinSources }> {
  return (await api.get('/checkin/events/')).data;
}

export async function createCheckinEvent(
  input: { festival: number } | { lesson: number } | { title: string; slots: SlotInput[] },
): Promise<CheckinEvent> {
  return (await api.post<CheckinEvent>('/checkin/events/', input)).data;
}

export async function fetchCheckinEvent(id: number): Promise<CheckinEventDetail> {
  return (await api.get<CheckinEventDetail>(`/checkin/events/${id}/`)).data;
}

export async function deleteCheckinEvent(id: number): Promise<void> {
  await api.delete(`/checkin/events/${id}/`);
}

export async function resetScanKey(id: number): Promise<string> {
  return (await api.post<{ scanKey: string }>(`/checkin/events/${id}/reset-key/`)).data.scanKey;
}

export async function addCheckinSlot(eventId: number, input: SlotInput): Promise<CheckinEvent> {
  return (await api.post<CheckinEvent>(`/checkin/events/${eventId}/slots/`, input)).data;
}

export async function updateCheckinSlot(slotId: number, input: SlotInput): Promise<CheckinEvent> {
  return (await api.patch<CheckinEvent>(`/checkin/slots/${slotId}/`, input)).data;
}

export async function deleteCheckinSlot(slotId: number): Promise<CheckinEvent> {
  return (await api.delete<CheckinEvent>(`/checkin/slots/${slotId}/`)).data;
}

export async function deleteCheckinRecord(recordId: number): Promise<void> {
  await api.delete(`/checkin/records/${recordId}/`);
}

async function downloadFile(path: string, filename: string, params?: Record<string, string>): Promise<void> {
  const res = await api.get<Blob>(path, { responseType: 'blob', params });
  const url = URL.createObjectURL(res.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/** 明細或彙整 CSV，欄位跟 barcoder demo 一樣 */
export async function downloadCheckinCsv(event: CheckinEvent, type: 'detail' | 'summary'): Promise<void> {
  const label = type === 'detail' ? '明細' : '彙整';
  await downloadFile(`/checkin/events/${event.id}/export/`, `${event.title}簽到_${label}.csv`, { type });
}

/** 所有活動的人數統計（不含學號） */
export async function downloadCheckinStats(): Promise<void> {
  await downloadFile('/checkin/events/export/', '活動簽到人數統計.csv');
}

/** 給外場志工的掃描連結 */
export function scanUrl(event: { id: number; scanKey?: string }): string {
  return `${window.location.origin}/scan/index.html?event=${event.id}&key=${encodeURIComponent(event.scanKey ?? '')}`;
}
