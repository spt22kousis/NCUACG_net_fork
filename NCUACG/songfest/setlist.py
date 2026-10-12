# NCUACG/songfest/setlist.py
"""
排歌台的計算：時段預設值、時刻表、提醒、一鍵初排、補位建議、寫入播放紀錄、收進歌單。
規則來自排歌組工作區與「歌謠祭流程及職責分配」的排歌流程：

  - 上午場 1:58、下午一 1:48、下午二 1:58（含結尾影片），各可超過 2 分鐘；再超過就要提早開播。
  - PotPlayer 每首誤差 1 秒；開播前內場負責人講話；預留 4 分鐘錯誤處理。
  - 所有沒窗掉的新曲都必須排上（亂入曲只排入選的；合作社團的備曲正選不足才補）。
  - 同一人的歌盡量分散；前一場播過的舊曲盡量不排；連曲要排在一起。
"""
from __future__ import annotations

import datetime as dt
import math
from collections import Counter, defaultdict

from django.db import transaction
from django.db.models import Max

from .models import Festival, Play, Session, SetlistEntry, Submission, Track
from .submissions import active_submissions, previous_song_keys
from .text import song_key

H, M = 3600, 60

DEFAULT_SESSIONS = [
    dict(name="測試曲", order=0, is_test=True, start_time=dt.time(9, 45), end_time=None, target_seconds=None,
         rounds=2, speech_seconds=0, buffer_seconds=0),
    dict(name="上午場", order=1, start_time=dt.time(10), end_time=dt.time(12), target_seconds=H + 58 * M),
    dict(name="下午一", order=2, start_time=dt.time(13), end_time=dt.time(14, 50), target_seconds=H + 48 * M),
    dict(name="下午二", order=3, start_time=dt.time(15), end_time=dt.time(17), target_seconds=H + 58 * M),
]

# 每張 DVD 放 20 首（D13720 是第 137 片第 20 首）
SONGS_PER_DVD = 20


def ensure_sessions(festival: Festival) -> None:
    if festival.kind == "hall" and not festival.sessions.exists():
        Session.objects.bulk_create([Session(festival=festival, **d) for d in DEFAULT_SESSIONS])


def eligible_submissions(festival: Festival):
    """要排進歌單的新曲：沒窗歌、沒退件（亂入曲沒入選就是退件）。合作社團備曲另外處理。"""
    return active_submissions(festival).select_related("festival")


def _clock(base: dt.time, seconds: int) -> str:
    moment = dt.datetime.combine(dt.date(2000, 1, 1), base) + dt.timedelta(seconds=seconds)
    return moment.strftime("%H:%M:%S")


def _hms(seconds: int) -> str:
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    return f"{sign}{seconds // H}:{seconds % H // M:02d}:{seconds % M:02d}"


def _entries(festival: Festival):
    return list(
        SetlistEntry.objects.filter(session__festival=festival)
        .select_related("session", "submission", "submission__festival", "track")
        .order_by("session__order", "position", "id")
    )


def _entry_key(entry: SetlistEntry) -> str | None:
    """判斷「同一首歌」用；CM、結尾影片不算"""
    if entry.kind == "custom" and entry.custom_type in ("cm", "credits"):
        return None
    return song_key(entry.song_source, entry.title)


def build_board(festival: Festival, track_stats: dict[int, dict]) -> dict:
    """排歌台需要的全部資料：各時段（含時刻表與提醒）、還沒排的新曲、整體提醒。"""
    sessions = list(festival.sessions.select_related("owner"))
    entries = _entries(festival)
    by_session = defaultdict(list)
    for e in entries:
        by_session[e.session_id].append(e)

    previous_keys = previous_song_keys(festival)
    key_places = defaultdict(list)
    for e in entries:
        key = _entry_key(e)
        if key:
            key_places[key].append(e)
    scheduled_subs = {e.submission_id for e in entries if e.submission_id}
    editor_totals = Counter(e.submission.editor_name for e in entries if e.kind == "new")
    main_sessions = [s for s in sessions if not s.is_test]

    session_data = []
    for session in sessions:
        rows = by_session[session.id]
        position_of = {e.submission_id: i for i, e in enumerate(rows) if e.submission_id}
        cumulative = 0
        out_rows = []
        for i, e in enumerate(rows):
            duration = e.duration
            cumulative += (duration or 0) + session.per_song_error_seconds
            warnings = []
            if e.kind == "new":
                status = e.submission.status()
                if status in ("withdrawn", "rejected"):
                    warnings.append("已窗歌或退件，請換一首舊曲補上")
                elif status == "overdue":
                    warnings.append("逾期未繳交")
                partner = e.submission.chain_with_id
                if partner and partner in scheduled_subs and abs(position_of.get(partner, -99) - i) != 1:
                    warnings.append("連曲沒有排在一起")
            key = _entry_key(e)
            if key and e.kind == "old" and key in previous_keys:
                warnings.append("上一場播過")
            if key and len(key_places[key]) > 1:
                others = [o for o in key_places[key] if o.id != e.id]
                warnings.append("重複：" + "、".join(f"{o.session.name}#{o.position}" for o in others))
            if duration is None:
                warnings.append("沒有長度")
            stats = track_stats.get(e.track_id, {}) if e.track_id else {}
            out_rows.append({
                "id": e.id,
                "position": e.position,
                "kind": e.kind,
                "customType": e.custom_type,
                "title": e.title,
                "songSource": e.song_source,
                "visualSource": e.visual_source,
                "editor": e.editor,
                "dvdCode": e.track.dvd_code if e.track_id else None,
                "submissionId": e.submission_id,
                "source": e.submission.source if e.submission_id else None,
                "sourceLabel": _source_label(e),
                "isBackup": bool(e.submission_id and e.submission.is_backup),
                "duration": duration,
                "endsAt": _clock(session.start_time, cumulative),
                "heat": e.heat,
                "note": e.note,
                "lastPlayed": stats.get("lastPlayed"),
                "recentPlayCount": stats.get("recentPlayCount"),
                "warnings": warnings,
            })

        total = sum(e.duration or 0 for e in rows)
        error = session.per_song_error_seconds * len(rows)
        played = (total + error) * session.rounds
        end_at = session.start_time and _clock(session.start_time, played)
        session_warnings = []
        over = under = False
        suggested_start = None
        if session.target_seconds:
            limit = session.target_seconds + session.tolerance_seconds
            if total > limit:
                over = True
                if session.end_time:
                    needed = dt.datetime.combine(dt.date(2000, 1, 1), session.end_time) - dt.timedelta(seconds=total + error)
                    suggested_start = needed.strftime("%H:%M:%S")
                session_warnings.append(
                    f"總長 {_hms(total)}，超過 {_hms(limit)}"
                    + (f"：要提早到 {suggested_start} 開播才能在 {session.end_time:%H:%M} 結束" if suggested_start else "")
                )
            elif total < session.target_seconds - session.tolerance_seconds and rows:
                under = True
                session_warnings.append(f"還差 {_hms(session.target_seconds - total)}，可以再加歌")
        missing = sum(1 for e in rows if e.duration is None)
        if missing:
            session_warnings.append(f"{missing} 首沒有長度，總長不準")
        # 同一人的歌盡量分散：每人在一個時段最多 ceil(總首數 / 時段數) 首
        if not session.is_test and main_sessions:
            here = Counter(e.submission.editor_name for e in rows if e.kind == "new")
            for name, count in here.items():
                allowed = math.ceil(editor_totals[name] / len(main_sessions))
                if count > allowed:
                    session_warnings.append(f"{name} 在這場有 {count} 首（共 {editor_totals[name]} 首，建議分散）")
            chains = Counter(
                e.submission.editor_name for e in rows if e.kind == "new" and e.submission.chain_with_id
            )
            for name, count in chains.items():
                if count > 2:
                    session_warnings.append(f"{name} 在這場有兩組以上連曲（規則是每人每場一次，可以不理）")

        session_data.append({
            "id": session.id,
            "name": session.name,
            "isTest": session.is_test,
            "startTime": session.start_time.strftime("%H:%M"),
            "endTime": session.end_time.strftime("%H:%M") if session.end_time else None,
            "targetSeconds": session.target_seconds,
            "toleranceSeconds": session.tolerance_seconds,
            "speechSeconds": session.speech_seconds,
            "bufferSeconds": session.buffer_seconds,
            "perSongErrorSeconds": session.per_song_error_seconds,
            "rounds": session.rounds,
            "ownerId": session.owner_id,
            "ownerName": session.owner.name if session.owner else None,
            "totalSeconds": total,
            "errorSeconds": error,
            "speechAt": _clock(session.start_time, -session.speech_seconds),
            "endAt": end_at,
            "latestEndAt": session.start_time and _clock(session.start_time, played + session.buffer_seconds),
            "over": over,
            "under": under,
            "suggestedStart": suggested_start,
            "warnings": session_warnings,
            "entries": out_rows,
        })

    # 還沒排的新曲
    pool = []
    regular_partner = 0
    for sub in eligible_submissions(festival):
        if sub.source == "partner" and not sub.is_backup:
            regular_partner += 1
        if sub.id in scheduled_subs:
            continue
        pool.append({
            "submissionId": sub.id,
            "title": sub.title,
            "songSource": sub.song_source,
            "visualSource": sub.visual_source,
            "editor": sub.editor_name,
            "source": sub.source,
            "sourceLabel": festival.partner_name if sub.source == "partner" else sub.get_source_display(),
            "isBackup": sub.is_backup,
            "duration": sub.duration_seconds,
            "status": sub.status(),
            "chainWith": sub.chain_with_id,
        })

    warnings = []
    unscheduled = [p for p in pool if not p["isBackup"]]
    if unscheduled:
        warnings.append(f"還有 {len(unscheduled)} 首新曲沒排（所有沒窗掉的新曲都必須排上）")
    backups = [p for p in pool if p["isBackup"]]
    shortfall = festival.partner_limit - regular_partner
    if backups and shortfall > 0:
        warnings.append(f"{festival.partner_name}正選 {regular_partner}/{festival.partner_limit} 首，可以補 {min(shortfall, len(backups))} 首備曲")
    withdrawn_in_setlist = sum(
        1 for e in entries if e.kind == "new" and e.submission.status() in ("withdrawn", "rejected")
    )
    if withdrawn_in_setlist:
        warnings.append(f"歌單裡有 {withdrawn_in_setlist} 首已經窗歌或退件，請換成舊曲")

    return {"sessions": session_data, "pool": pool, "warnings": warnings}


def _source_label(entry: SetlistEntry) -> str:
    if entry.kind == "old":
        return "舊曲"
    if entry.kind == "custom":
        return entry.get_custom_type_display() or "其他"
    sub = entry.submission
    if sub.source == "guest":
        return "亂入"
    if sub.source == "partner":
        return sub.festival.partner_name + ("備曲" if sub.is_backup else "")
    return "新曲"


# ── 編輯 ────────────────────────────────────────────────────────────────────

def renumber(session: Session) -> None:
    for i, entry in enumerate(session.entries.order_by("position", "id"), start=1):
        if entry.position != i:
            SetlistEntry.objects.filter(pk=entry.pk).update(position=i)


@transaction.atomic
def place(entry: SetlistEntry, session: Session, position: int | None) -> None:
    """把 entry 放到 session 的第 position 個（從 1 開始；None 表示放最後）。"""
    old_session = entry.session if entry.pk else None
    siblings = list(session.entries.exclude(pk=entry.pk).order_by("position", "id"))
    index = len(siblings) if position is None else max(0, min(position - 1, len(siblings)))
    siblings.insert(index, entry)
    entry.session = session
    for i, e in enumerate(siblings, start=1):
        e.position = i
    entry.save()
    for e in siblings:
        if e.pk != entry.pk:
            SetlistEntry.objects.filter(pk=e.pk).update(position=e.position)
    if old_session and old_session.pk != session.pk:
        renumber(old_session)


@transaction.atomic
def auto_distribute(festival: Festival) -> int:
    """
    一鍵初排：把還沒排的新曲（不含備曲）平均分到正式時段，加在各時段最後面。
    依「目前長度 / 目標長度」挑最空的時段；同一人的歌盡量分散；連曲兩首放在一起。
    """
    sessions = [s for s in festival.sessions.all() if not s.is_test and s.target_seconds]
    if not sessions:
        return 0
    entries = _entries(festival)
    scheduled = {e.submission_id for e in entries if e.submission_id}
    load = {s.id: sum(e.duration or 0 for e in entries if e.session_id == s.id) for s in sessions}
    per_editor = defaultdict(Counter)
    for e in entries:
        if e.kind == "new":
            per_editor[e.submission.editor_name][e.session_id] += 1

    subs = [s for s in eligible_submissions(festival) if s.id not in scheduled and not s.is_backup]
    by_id = {s.id: s for s in subs}
    # 連曲當成一組
    units, used = [], set()
    for sub in subs:
        if sub.id in used:
            continue
        group = [sub]
        partner = by_id.get(sub.chain_with_id) if sub.chain_with_id else None
        if partner is None:
            partner = next((s for s in subs if s.chain_with_id == sub.id and s.id not in used), None)
        if partner and partner.id not in used:
            group = [sub, partner]
        used.update(s.id for s in group)
        units.append(group)

    totals = Counter()
    for e in entries:
        if e.kind == "new":
            totals[e.submission.editor_name] += 1
    for group in units:
        totals[group[0].editor_name] += len(group)
    # 歌多的人先排，比較好分散
    units.sort(key=lambda g: (-totals[g[0].editor_name], -sum(s.duration_seconds or 240 for s in g)))

    placed = 0
    for group in units:
        editor = group[0].editor_name
        allowed = math.ceil(totals[editor] / len(sessions))
        candidates = [s for s in sessions if per_editor[editor][s.id] + len(group) <= allowed] or sessions
        duration = sum(s.duration_seconds or 240 for s in group)  # 沒長度先抓 4 分鐘
        target = min(candidates, key=lambda s: (load[s.id] + duration) / s.target_seconds)
        for sub in group:
            place(SetlistEntry(kind="new", submission=sub), target, None)
            placed += 1
        load[target.id] += duration
        per_editor[editor][target.id] += len(group)
    return placed


def suggestions(festival: Festival, seconds: int, window: int = 30, limit: int = 12) -> list[int]:
    """補位用的舊曲：長度接近、上一場沒播過、這場還沒排。回傳 Track id（依長度差距排序）。"""
    taken = {k for k in (_entry_key(e) for e in _entries(festival)) if k}
    avoid = taken | previous_song_keys(festival)
    candidates = Track.objects.filter(
        duration_seconds__gte=seconds - window, duration_seconds__lte=seconds + window
    ).exclude(song_key__in=avoid)
    ranked = sorted(candidates, key=lambda t: abs(t.duration_seconds - seconds))
    return [t.id for t in ranked[:limit]]


# ── 活動後 ──────────────────────────────────────────────────────────────────

@transaction.atomic
def write_plays(festival: Festival) -> int:
    """把排好的歌單寫成播放紀錄（取代這一場原本的紀錄）。CM 不算；結尾影片照試算表的寫法記成「5秒畫面」。"""
    rows = []
    for e in _entries(festival):
        if e.kind == "custom" and e.custom_type == "cm":
            continue
        if e.kind == "new" and e.submission.status() in ("withdrawn", "rejected"):
            continue
        track = e.track if e.kind == "old" else (e.submission.track if e.kind == "new" else None)
        visual = Play.CREDITS_VISUAL if e.custom_type == "credits" else e.visual_source
        rows.append(Play(
            festival=festival, position=len(rows) + 1, song_source=e.song_source, visual_source=visual,
            title=e.title, song_key=song_key(e.song_source, e.title), track=track,
            match_status="matched" if track else "unmatched",
        ))
    Play.objects.filter(festival=festival).delete()
    Play.objects.bulk_create(rows)
    return len(rows)


def library_candidates(festival: Festival):
    """可以收進歌單的新曲：有排進歌單、已繳交、作者同意。"""
    scheduled = SetlistEntry.objects.filter(session__festival=festival, kind="new").values("submission")
    return (
        festival.submissions.filter(pk__in=scheduled, withdrawn_at__isnull=True, is_rejected=False)
        .exclude(file_link="")
        .select_related("track", "festival")
        .order_by("created_at")
    )


def next_dvd_codes(count: int) -> list[str]:
    last = Track.objects.aggregate(m=Max("dvd_sort"))["m"] or 0
    disc, index = divmod(last, 100)
    codes = []
    for _ in range(count):
        index += 1
        if index > SONGS_PER_DVD or disc == 0:
            disc, index = disc + 1, 1
        codes.append(f"D{disc:02d}{index:02d}")
    return codes


@transaction.atomic
def add_to_library(submissions: list[Submission]) -> list[Track]:
    """自動編 DVD 編號、收進舊曲清單。之後社產更新線上歌單試算表，重新匯入時 DVD 編號一樣就會對上。"""
    todo = [s for s in submissions if s.track_id is None]
    created = []
    for sub, code in zip(todo, next_dvd_codes(len(todo))):
        digits = int(code[1:])
        track = Track.objects.create(
            dvd_code=code, song_source=sub.song_source, visual_source=sub.visual_source, title=sub.title,
            artist=sub.artist, editor=sub.editor_name, duration_seconds=sub.duration_seconds,
            index_order=1_000_000 + digits,
        )
        sub.track = track
        sub.save(update_fields=["track", "updated_at"])
        created.append(track)
    return created
