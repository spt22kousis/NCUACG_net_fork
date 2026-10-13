// frontend/src/pages/club/Calendar.tsx
// 行事曆：活動公告、社課、歌謠祭放在同一個月曆。桌機是月曆格子，手機改成依日期的清單。
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { fetchCalendar, isoDay, type CalendarItem } from '../../api/club';
import ClubLayout from './ClubLayout';

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];
const KIND_LABEL: Record<CalendarItem['kind'], string> = { event: '活動', lesson: '社課', songfest: '歌謠祭' };
const pad = (n: number) => String(n).padStart(2, '0');

function timeOf(item: CalendarItem): string {
  if (item.allDay) return '';
  const d = new Date(item.start);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** 這個項目佔到哪幾天（跨日活動每天都列） */
function daysOf(item: CalendarItem): string[] {
  const start = new Date(item.start);
  const end = item.end ? new Date(item.end) : start;
  const days: string[] = [];
  for (const d = new Date(start.getFullYear(), start.getMonth(), start.getDate()); d <= end; d.setDate(d.getDate() + 1)) {
    days.push(isoDay(d));
    if (days.length > 62) break;
  }
  return days;
}

function ItemLink({ item, withTime = true }: { item: CalendarItem; withTime?: boolean }) {
  const time = withTime ? timeOf(item) : '';
  return (
    <Link to={item.link} className={`calendar-item is-${item.kind}`} title={item.location ? `${item.title}（${item.location}）` : item.title}>
      {time && <span className="calendar-time">{time}</span>}
      {item.title}
    </Link>
  );
}

export default function Calendar() {
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [items, setItems] = useState<CalendarItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 月曆格子從當月 1 號那週的星期日排到最後一週的星期六
  const { gridStart, gridEnd, cells } = useMemo(() => {
    const start = new Date(month);
    start.setDate(1 - start.getDay());
    const last = new Date(month.getFullYear(), month.getMonth() + 1, 0);
    const end = new Date(last);
    end.setDate(last.getDate() + (6 - last.getDay()) + 1);
    const list: Date[] = [];
    for (const d = new Date(start); d < end; d.setDate(d.getDate() + 1)) list.push(new Date(d));
    return { gridStart: start, gridEnd: end, cells: list };
  }, [month]);

  useEffect(() => {
    setItems(null);
    setError(null);
    fetchCalendar(isoDay(gridStart), isoDay(gridEnd))
      .then(setItems)
      .catch(() => setError('載入失敗，請稍後再試'));
  }, [gridStart, gridEnd]);

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarItem[]>();
    for (const item of items ?? []) {
      for (const day of daysOf(item)) map.set(day, [...(map.get(day) ?? []), item]);
    }
    return map;
  }, [items]);

  const today = isoDay(new Date());
  const shift = (n: number) => setMonth(new Date(month.getFullYear(), month.getMonth() + n, 1));
  // 手機清單只列當月、有東西的日子
  const monthDays = cells.filter(d => d.getMonth() === month.getMonth() && byDay.has(isoDay(d)));

  return (
    <ClubLayout>
      <div className="calendar-toolbar">
        <button type="button" className="sf-button" onClick={() => shift(-1)} aria-label="上個月">←</button>
        <h2 className="calendar-month">{month.getFullYear()} 年 {month.getMonth() + 1} 月</h2>
        <button type="button" className="sf-button" onClick={() => shift(1)} aria-label="下個月">→</button>
        <button
          type="button"
          className="sf-button"
          onClick={() => setMonth(new Date(new Date().getFullYear(), new Date().getMonth(), 1))}
        >
          今天
        </button>
        <span className="calendar-legend">
          {(Object.keys(KIND_LABEL) as CalendarItem['kind'][]).map(kind => (
            <span key={kind} className={`calendar-item is-${kind}`}>{KIND_LABEL[kind]}</span>
          ))}
        </span>
      </div>

      {error && <p className="sf-error" role="alert">{error}</p>}

      <div className="sf-card calendar-grid" aria-busy={items === null}>
        {WEEKDAYS.map(w => <div key={w} className="calendar-weekday">{w}</div>)}
        {cells.map(d => {
          const key = isoDay(d);
          const outside = d.getMonth() !== month.getMonth();
          return (
            <div key={key} className={`calendar-cell${outside ? ' is-outside' : ''}${key === today ? ' is-today' : ''}`}>
              <span className="calendar-date">{d.getDate()}</span>
              {(byDay.get(key) ?? []).map(item => <ItemLink key={item.id} item={item} />)}
            </div>
          );
        })}
      </div>

      <div className="calendar-list">
        {items !== null && monthDays.length === 0 && <p className="sf-card sf-empty">這個月還沒有活動或社課。</p>}
        {monthDays.map(d => {
          const key = isoDay(d);
          return (
            <section key={key} className={`sf-card calendar-list-day${key === today ? ' is-today' : ''}`}>
              <h3>{d.getMonth() + 1}/{d.getDate()}（{WEEKDAYS[d.getDay()]}）</h3>
              {(byDay.get(key) ?? []).map(item => (
                <div key={item.id} className="calendar-list-row">
                  <ItemLink item={item} />
                  {item.location && <span className="sf-muted">{item.location}</span>}
                </div>
              ))}
            </section>
          );
        })}
      </div>
    </ClubLayout>
  );
}
