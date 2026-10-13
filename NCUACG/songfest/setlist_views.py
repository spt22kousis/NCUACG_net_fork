# NCUACG/songfest/setlist_views.py
"""
排歌台 API（掛在 /api/songfest/ 之下）。計算都在 setlist.py。

排歌組（幹部或該場排歌組成員）
  GET    festivals/<id>/setlist/                    各時段、時刻表、提醒、還沒排的新曲
  POST   festivals/<id>/setlist/auto/               一鍵初排
  GET    festivals/<id>/setlist/suggest/?seconds=   補位用的舊曲
  GET    festivals/<id>/setlist/export/?type=       public 對外公開歌單 | workspace 工作區 | order 播放順序 | credits 結尾名單
  POST   festivals/<id>/setlist/publish/            {"public": true} 公開到歌單瀏覽
  POST   festivals/<id>/setlist/write-plays/        活動後：寫入播放紀錄
  PATCH  setlist/sessions/<id>/                     改時段設定、負責人
  POST   setlist/sessions/<id>/entries/             加一首（新曲、舊曲或其他）
  PATCH  setlist/entries/<id>/                      移動、改熱度與備註、換成舊曲
  DELETE setlist/entries/<id>/
  GET    festivals/<id>/library/                    活動後：可以收進歌單的新曲
  POST   festivals/<id>/library/add/                自動編 DVD 編號並收進舊曲
  GET    festivals/<id>/library/export/            收進歌單名單（CSV，欄位同線上歌單）

投稿者
  GET    library-consent/                           我可以回報收進歌單的投稿
  POST   submissions/<id>/library-consent/          {"consent": true}
"""
from __future__ import annotations

import csv
import datetime as dt
from collections import Counter, OrderedDict
from io import StringIO
from urllib.parse import quote

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import requests as rq
from . import setlist as sl
from .models import Festival, FestivalStaff, Session, SetlistEntry, Submission, Track
from .submission_views import festival_info
from .submissions import is_staff_for
from .views import _track_to_dict, _tracks_with_stats


def _forbidden():
    return Response({"detail": "只有這一場的排歌組或幹部可以使用"}, status=status.HTTP_403_FORBIDDEN)


def _staff_festival(request, festival_id):
    festival = get_object_or_404(Festival, pk=festival_id)
    return festival if is_staff_for(request.user, festival) else None


def _track_stats(festival: Festival) -> dict[int, dict]:
    ids = SetlistEntry.objects.filter(session__festival=festival, track__isnull=False).values("track")
    return {
        t.id: {"lastPlayed": t.last_played.isoformat() if t.last_played else None,
               "recentPlayCount": t.recent_play_count}
        for t in _tracks_with_stats().filter(pk__in=ids)
    }


def _board_requests(festival: Festival) -> dict:
    """點歌清單（工作區的「線上點歌」）與採用數：排進任一時段就算採用。"""
    from .request_views import _request_dicts, _requests_queryset

    qs = _requests_queryset().filter(festival=festival).order_by("-vote_count", "created_at")
    rows = _request_dicts(festival, None, qs, staff=True)
    return {
        "requests": rows,
        "requestStats": {"adopted": sum(1 for r in rows if r["scheduledIn"]), "total": len(rows)},
    }


def _board(festival: Festival) -> dict:
    sl.ensure_sessions(festival)
    staff = FestivalStaff.objects.filter(festival=festival).select_related("user")
    return {
        "festival": {**festival_info(festival), "setlistPublic": festival.setlist_public},
        "staff": [{"id": s.user_id, "name": s.user.name, "role": s.get_role_display()} for s in staff],
        **sl.build_board(festival, _track_stats(festival), rq.votes_by_key(festival)),
        **_board_requests(festival),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def board(request, festival_id: int):
    festival = _staff_festival(request, festival_id)
    if festival is None:
        return _forbidden()
    return Response(_board(festival))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def auto(request, festival_id: int):
    festival = _staff_festival(request, festival_id)
    if festival is None:
        return _forbidden()
    sl.ensure_sessions(festival)
    placed = sl.auto_distribute(festival)
    return Response({"placed": placed, **_board(festival)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def suggest(request, festival_id: int):
    festival = _staff_festival(request, festival_id)
    if festival is None:
        return _forbidden()
    try:
        seconds = int(request.GET.get("seconds", 240))
    except ValueError:
        seconds = 240
    ids = sl.suggestions(festival, seconds)
    tracks = {t.id: t for t in _tracks_with_stats().filter(pk__in=ids)}
    return Response([_track_to_dict(tracks[i]) for i in ids if i in tracks])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def publish(request, festival_id: int):
    festival = _staff_festival(request, festival_id)
    if festival is None:
        return _forbidden()
    festival.setlist_public = bool(request.data.get("public"))
    festival.save(update_fields=["setlist_public", "updated_at"])
    return Response({"setlistPublic": festival.setlist_public})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def write_plays(request, festival_id: int):
    festival = _staff_festival(request, festival_id)
    if festival is None:
        return _forbidden()
    count = sl.write_plays(festival)
    return Response({"written": count})


# ── 時段與項目 ──────────────────────────────────────────────────────────────

class SessionInput(serializers.Serializer):
    name = serializers.CharField(max_length=20, required=False)
    startTime = serializers.TimeField(required=False)
    endTime = serializers.TimeField(required=False, allow_null=True)
    targetSeconds = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    speechSeconds = serializers.IntegerField(min_value=0, required=False)
    bufferSeconds = serializers.IntegerField(min_value=0, required=False)
    perSongErrorSeconds = serializers.IntegerField(min_value=0, max_value=60, required=False)
    rounds = serializers.IntegerField(min_value=1, max_value=10, required=False)
    ownerId = serializers.IntegerField(required=False, allow_null=True)

    FIELDS = {
        "name": "name", "startTime": "start_time", "endTime": "end_time", "targetSeconds": "target_seconds",
        "speechSeconds": "speech_seconds", "bufferSeconds": "buffer_seconds",
        "perSongErrorSeconds": "per_song_error_seconds", "rounds": "rounds", "ownerId": "owner_id",
    }


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def session_detail(request, session_id: int):
    session = get_object_or_404(Session.objects.select_related("festival"), pk=session_id)
    if not is_staff_for(request.user, session.festival):
        return _forbidden()
    form = SessionInput(data=request.data, partial=True)
    form.is_valid(raise_exception=True)
    for key, attr in SessionInput.FIELDS.items():
        if key in form.validated_data:
            setattr(session, attr, form.validated_data[key])
    session.save()
    return Response(_board(session.festival))


class EntryInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["new", "old", "custom"], required=False)
    submissionId = serializers.IntegerField(required=False)
    dvdCode = serializers.CharField(max_length=10, required=False)
    customType = serializers.ChoiceField(choices=["cm", "credits", "other"], required=False)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    source = serializers.CharField(max_length=255, required=False, allow_blank=True)
    editor = serializers.CharField(max_length=100, required=False, allow_blank=True)
    duration = serializers.IntegerField(min_value=0, max_value=3 * 3600, required=False, allow_null=True)
    sessionId = serializers.IntegerField(required=False)
    position = serializers.IntegerField(min_value=1, required=False)
    heat = serializers.IntegerField(min_value=0, max_value=10, required=False, allow_null=True)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)


def _apply_custom(entry: SetlistEntry, data: dict) -> None:
    for key, attr in {"customType": "custom_type", "title": "custom_title", "source": "custom_source",
                      "editor": "custom_editor", "duration": "custom_duration"}.items():
        if key in data:
            setattr(entry, attr, data[key])


def _find_track(code: str) -> Track:
    track = Track.objects.filter(dvd_code__iexact=code.strip()).first()
    if track is None:
        raise serializers.ValidationError({"dvdCode": f"歌單裡找不到 {code}"})
    return track


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def entry_create(request, session_id: int):
    session = get_object_or_404(Session.objects.select_related("festival"), pk=session_id)
    festival = session.festival
    if not is_staff_for(request.user, festival):
        return _forbidden()
    form = EntryInput(data=request.data)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    kind = data.get("kind")
    entry = SetlistEntry(kind=kind or "custom", heat=data.get("heat"), note=data.get("note", ""))

    if kind == "new":
        sub = get_object_or_404(Submission, pk=data.get("submissionId"), festival=festival)
        if SetlistEntry.objects.filter(submission=sub).exists():
            return Response({"detail": f"〈{sub.title}〉已經排進歌單了"}, status=status.HTTP_400_BAD_REQUEST)
        entry.submission = sub
    elif kind == "old":
        entry.track = _find_track(data.get("dvdCode", ""))
    elif kind == "custom":
        if not data.get("title"):
            return Response({"title": ["請填名稱"]}, status=status.HTTP_400_BAD_REQUEST)
        _apply_custom(entry, data)
        entry.custom_type = data.get("customType", "other")
    else:
        return Response({"kind": ["請選擇新曲、舊曲或其他"]}, status=status.HTTP_400_BAD_REQUEST)

    sl.place(entry, session, data.get("position"))
    return Response(_board(festival), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def entry_detail(request, entry_id: int):
    entry = get_object_or_404(SetlistEntry.objects.select_related("session__festival"), pk=entry_id)
    festival = entry.session.festival
    if not is_staff_for(request.user, festival):
        return _forbidden()
    if request.method == "DELETE":
        session = entry.session
        entry.delete()
        sl.renumber(session)
        return Response(_board(festival))

    form = EntryInput(data=request.data, partial=True)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    for key in ("heat", "note"):
        if key in data:
            setattr(entry, key, data[key])
    if entry.kind == "custom":
        _apply_custom(entry, data)
    # 補位：把窗掉的新曲換成舊曲
    if data.get("dvdCode"):
        entry.kind, entry.submission, entry.track = "old", None, _find_track(data["dvdCode"])
    entry.save()
    if "sessionId" in data or "position" in data:
        target = get_object_or_404(Session, pk=data.get("sessionId", entry.session_id), festival=festival)
        sl.place(entry, target, data.get("position"))
    return Response(_board(festival))


# ── 匯出 ────────────────────────────────────────────────────────────────────

def _download(text: str, filename: str, content_type="text/csv") -> HttpResponse:
    response = HttpResponse("﻿" + text, content_type=f"{content_type}; charset=utf-8")
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response


def _csv(rows: list[list]) -> str:
    buf = StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def _mmss(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}" if seconds else ""


def _played(entry: dict) -> bool:
    """窗掉、退件的新曲不出現在匯出的歌單"""
    return not (entry["kind"] == "new" and any("窗歌或退件" in w for w in entry["warnings"]))


def _credits_text(festival: Festival, board: dict) -> str:
    members, partners, guests = OrderedDict(), OrderedDict(), OrderedDict()
    five_sec = Counter()
    guest_five = set()
    subs = {s.id: s for s in festival.submissions.all()}
    for session in board["sessions"]:
        for e in session["entries"]:
            if e["kind"] != "new" or not _played(e):
                continue
            sub = subs[e["submissionId"]]
            {"member": members, "partner": partners, "guest": guests}[sub.source][sub.editor_name] = True
            if sub.five_sec_status() == "uploaded":
                if sub.source == "guest":
                    guest_five.add(sub.editor_name)  # 亂入曲每人最多 5 秒
                else:
                    five_sec[sub.editor_name] += 1
    for name in guest_five:
        five_sec[name] += 1
    lines = [f"{festival.name}歌謠祭 結尾名單", ""]
    lines += ["【新曲剪輯】", "、".join(members) or "（無）", ""]
    if guests:
        lines += ["【亂入曲】", "、".join(guests), ""]
    if partners:
        lines += [f"【特別感謝 {festival.partner_name}】", "、".join(partners), ""]
    lines += ["【5 秒畫面】"] + [f"{name}：{count} 段（{count * 5} 秒）" for name, count in five_sec.items()]
    lines += ["", f"共 {sum(five_sec.values())} 段、{sum(five_sec.values()) * 5} 秒"]
    return "\n".join(lines)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export(request, festival_id: int):
    festival = _staff_festival(request, festival_id)
    if festival is None:
        return _forbidden()
    board_data = _board(festival)
    kind = request.GET.get("type", "public")

    if kind == "credits":
        return _download(_credits_text(festival, board_data), f"{festival.name}_結尾名單.txt", "text/plain")

    if kind == "order":
        lines = []
        for s in board_data["sessions"]:
            lines.append(f"【{s['name']}】{s['startTime']} 開播" + (f"（輪播 {s['rounds']} 輪）" if s["rounds"] > 1 else ""))
            for e in filter(_played, s["entries"]):
                if e["kind"] == "new":
                    name = f"[{e['visualSource']}][{e['title']}][{e['editor']}]"  # 投稿規則的檔名格式
                elif e["kind"] == "old":
                    name = f"{e['dvdCode']} {e['songSource']} - {e['title']}"
                else:
                    name = f"{e['sourceLabel']}：{e['title']}"
                lines.append(f"{e['position']:02d}. [{e['sourceLabel']}] {name}  {_mmss(e['duration'])}")
            lines.append("")
        return _download("\n".join(lines), f"{festival.name}_播放順序.txt", "text/plain")

    if kind == "workspace":
        rows = [["場次", "序列", "作品名", "曲名", "DVD/製作者", "實際時間長度", "播完時刻", "上次播放",
                 "4年內播放次數", "熱度", "類別", "備註", "提醒"]]
        for s in board_data["sessions"]:
            for e in s["entries"]:
                rows.append([
                    s["name"], e["position"], e["songSource"], e["title"], e["dvdCode"] or e["editor"],
                    _mmss(e["duration"]), e["endsAt"], e["lastPlayed"] or "", e["recentPlayCount"] or "",
                    e["heat"] if e["heat"] is not None else "", e["sourceLabel"], e["note"], "；".join(e["warnings"]),
                ])
            rows.append(["", "", "", "", "總時", "", dt.timedelta(seconds=s["totalSeconds"]), "預計結束", s["endAt"]])
        return _download(_csv(rows), f"{festival.name}_排歌工作區.csv")

    # 對外公開用：照原本工作表「對外公開用」的欄位，類別取代顏色
    rows = [["場次/順序", "歌曲出處", "畫面出處", "曲名", "類別"]]
    for s in board_data["sessions"]:
        rows.append([f"{s['name']} {s['startTime']}~{s['endTime'] or ''}".strip("~ ")])
        for e in filter(_played, s["entries"]):
            rows.append([e["position"], e["songSource"], e["visualSource"], e["title"], e["sourceLabel"]])
    return _download(_csv(rows), f"{festival.name}_對外公開歌單.csv")


# ── 收進歌單 ────────────────────────────────────────────────────────────────

def _candidate_dict(sub: Submission) -> dict:
    return {
        "submissionId": sub.id,
        "title": sub.title,
        "songSource": sub.song_source,
        "visualSource": sub.visual_source,
        "artist": sub.artist,
        "editor": sub.editor_name,
        "source": sub.source,
        "duration": sub.duration_seconds,
        "libraryConsent": sub.library_consent,
        "dvdCode": sub.track.dvd_code if sub.track_id else None,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def library(request, festival_id: int):
    festival = _staff_festival(request, festival_id)
    if festival is None:
        return _forbidden()
    return Response([_candidate_dict(s) for s in sl.library_candidates(festival)])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def library_add(request, festival_id: int):
    festival = _staff_festival(request, festival_id)
    if festival is None:
        return _forbidden()
    ids = request.data.get("submissionIds") or []
    subs = list(sl.library_candidates(festival).filter(pk__in=ids, library_consent=True))
    created = sl.add_to_library(subs)
    return Response({
        "added": [t.dvd_code for t in created],
        "candidates": [_candidate_dict(s) for s in sl.library_candidates(festival)],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def library_export(request, festival_id: int):
    """欄位照「中央動畫社線上歌單」的 DVD編號 分頁，社產可以直接貼上。"""
    festival = _staff_festival(request, festival_id)
    if festival is None:
        return _forbidden()
    rows = [["歌曲出處", "畫面出處", "曲名", "歌手", "DVD編號", "長度", "製作者"]]
    for sub in sl.library_candidates(festival).filter(library_consent=True):
        rows.append([sub.song_source, sub.visual_source, sub.title, sub.artist,
                     sub.track.dvd_code if sub.track_id else "", _mmss(sub.duration_seconds), sub.editor_name])
    return _download(_csv(rows), f"{festival.name}_收進歌單.csv")


# ── 投稿者：收進歌單回報 ────────────────────────────────────────────────────

def _consent_open(sub: Submission) -> bool:
    """活動結束後才開放回報；有排進歌單、已繳交、還沒收進歌單的才能回報"""
    return (
        sub.festival.date <= timezone.localdate()
        and sub.is_active and sub.is_uploaded and sub.track_id is None
        and SetlistEntry.objects.filter(submission=sub).exists()
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_library_consent(request):
    since = timezone.localdate() - dt.timedelta(days=90)
    subs = Submission.objects.filter(
        submitter=request.user, festival__date__lte=timezone.localdate(), festival__date__gte=since
    ).select_related("festival")
    return Response([
        {"submissionId": s.id, "festivalName": s.festival.name, "title": s.title, "consent": s.library_consent}
        for s in subs if _consent_open(s)
    ])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def library_consent(request, submission_id: int):
    sub = get_object_or_404(Submission.objects.select_related("festival"), pk=submission_id, submitter=request.user)
    if not _consent_open(sub):
        return Response({"detail": "這首現在不能回報收進歌單"}, status=status.HTTP_400_BAD_REQUEST)
    sub.library_consent = bool(request.data.get("consent"))
    sub.save(update_fields=["library_consent", "updated_at"])
    return Response({"submissionId": sub.id, "consent": sub.library_consent})
