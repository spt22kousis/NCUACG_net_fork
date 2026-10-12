# NCUACG/songfest/views.py
"""
歌謠祭 API（掛在 /api/songfest/ 之下，全部公開唯讀）

  GET festivals/                         所有公開場次（新到舊），含播放紀錄筆數
  GET festivals/<id>/                    單一場次與播放紀錄
  GET tracks/?q=&group=&sort=&page=      舊曲清單（每頁 50 首）
        sort=index（預設，五十音）| newest（DVD 編號新到舊）| popular（近 4 年最常播）
  GET tracks/groups/                     五十音分類與各分類首數
  GET ranking/?years=4&limit=20          最常播的歌（years=0 表示不限時間）

輸出欄位用 camelCase，對齊 frontend/src/api/songfest.ts 的型別。
"""
from __future__ import annotations

import datetime as dt

from django.core.paginator import Paginator
from django.db.models import Count, IntegerField, Max, Min, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Festival, Play, Track
from .text import normalize

PAGE_SIZE = 50
# 排歌組看的是「4 年內播放次數」：差不多一屆學生在學的期間
RECENT_YEARS = 4


def _years_ago(years: int) -> dt.date:
    today = timezone.localdate()
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # 2/29
        return today.replace(year=today.year - years, day=28)


def _int_param(request, name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(request.GET.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


# ── 輸出格式 ────────────────────────────────────────────────────────────────

def _festival_to_dict(f: Festival) -> dict:
    return {
        "id": f.id,
        "name": f.name,
        "date": f.date.isoformat(),
        "kind": f.kind,
        "venue": f.venue,
        "startTime": f.start_time.strftime("%H:%M") if f.start_time else None,
        "endTime": f.end_time.strftime("%H:%M") if f.end_time else None,
        "description": f.description,
        "playCount": getattr(f, "play_count", 0),
    }


def _track_to_dict(t: Track) -> dict:
    last_played = getattr(t, "last_played", None)
    return {
        "dvdCode": t.dvd_code,
        "songSource": t.song_source,
        "visualSource": t.visual_source,
        "title": t.title,
        "artist": t.artist,
        "editor": t.editor,
        "duration": t.duration_seconds,
        "group": t.index_label,
        # 以「歌」為單位計算（同一首歌的不同剪輯版本共用），見 text.song_key
        "playCount": getattr(t, "play_count", 0),
        "recentPlayCount": getattr(t, "recent_play_count", 0),
        "lastPlayed": last_played.isoformat() if last_played else None,
    }


def _play_to_dict(p: Play) -> dict:
    track = p.track
    return {
        "position": p.position,
        "songSource": p.song_source,
        "visualSource": p.visual_source,
        "title": p.title,
        # 播放紀錄沒有 DVD 編號，只有剛好對到一支舊曲時才有這兩個欄位
        "dvdCode": track.dvd_code if track else None,
        "editor": track.editor if track else None,
        "isCredits": p.visual_source == Play.CREDITS_VISUAL,
    }


def _counted_plays():
    """計入播放次數與排行榜的紀錄：公開場次、不含結尾的 Credits 影片。"""
    return Play.objects.filter(festival__is_published=True).exclude(visual_source=Play.CREDITS_VISUAL)


def _tracks_with_stats():
    """帶好播放次數、近 4 年播放次數、上次播放日期，用子查詢避免 N+1。"""
    plays = _counted_plays().filter(song_key=OuterRef("song_key"))

    def count_of(qs):
        counted = qs.order_by().values("song_key").annotate(n=Count("id")).values("n")
        return Coalesce(Subquery(counted, output_field=IntegerField()), Value(0))

    return Track.objects.annotate(
        play_count=count_of(plays),
        recent_play_count=count_of(plays.filter(festival__date__gte=_years_ago(RECENT_YEARS))),
        last_played=Subquery(plays.order_by("-festival__date").values("festival__date")[:1]),
    )


# ── API ─────────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def festival_list(request):
    festivals = Festival.objects.filter(is_published=True).annotate(play_count=Count("plays"))
    return Response([_festival_to_dict(f) for f in festivals])


@api_view(["GET"])
@permission_classes([AllowAny])
def festival_detail(request, festival_id: int):
    festival = get_object_or_404(
        Festival.objects.annotate(play_count=Count("plays")), pk=festival_id, is_published=True
    )
    plays = festival.plays.select_related("track")
    return Response({**_festival_to_dict(festival), "plays": [_play_to_dict(p) for p in plays]})


@api_view(["GET"])
@permission_classes([AllowAny])
def track_list(request):
    tracks = _tracks_with_stats()

    q = normalize(request.GET.get("q", "").strip())
    if q:
        # search_text 也經過 normalize，所以全形半形、大小寫、標點不同也找得到
        tracks = tracks.filter(search_text__contains=q)

    group = request.GET.get("group")
    if group:
        tracks = tracks.filter(index_group=group)

    sort = request.GET.get("sort", "index")
    if sort == "newest":
        tracks = tracks.order_by("-dvd_sort")
    elif sort == "popular":
        tracks = tracks.order_by("-recent_play_count", "-play_count", "index_order")
    else:
        tracks = tracks.order_by("index_order", "dvd_sort")

    page_size = _int_param(request, "page_size", PAGE_SIZE, 1, 100)
    paginator = Paginator(tracks, page_size)
    page = paginator.get_page(request.GET.get("page"))
    return Response({
        "count": paginator.count,
        "page": page.number,
        "pageCount": paginator.num_pages,
        "results": [_track_to_dict(t) for t in page.object_list],
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def track_groups(request):
    groups = (
        Track.objects.exclude(index_group="")
        .values("index_group")
        .annotate(count=Count("id"), first=Min("index_order"))
        .order_by("first")
    )
    return Response([{"group": g["index_group"], "count": g["count"]} for g in groups])


@api_view(["GET"])
@permission_classes([AllowAny])
def ranking(request):
    """最常播的歌：以歌為單位，同一首歌的不同版本合併計算。"""
    years = _int_param(request, "years", RECENT_YEARS, 0, 50)
    limit = _int_param(request, "limit", 20, 1, 100)

    plays = _counted_plays()
    if years:
        plays = plays.filter(festival__date__gte=_years_ago(years))
    top = list(
        plays.values("song_key")
        .annotate(count=Count("id"), last=Max("festival__date"))
        .order_by("-count", "-last")[:limit]
    )
    if not top:
        return Response([])

    # 每首歌拿最近一次播放的寫法當作顯示名稱
    names = {}
    for p in (
        Play.objects.filter(song_key__in=[t["song_key"] for t in top])
        .order_by("song_key", "-festival__date")
        .values("song_key", "song_source", "title")
    ):
        names.setdefault(p["song_key"], p)

    return Response([
        {
            "rank": i,
            "songSource": names[t["song_key"]]["song_source"],
            "title": names[t["song_key"]]["title"],
            "playCount": t["count"],
            "lastPlayed": t["last"].isoformat(),
        }
        for i, t in enumerate(top, start=1)
    ])
