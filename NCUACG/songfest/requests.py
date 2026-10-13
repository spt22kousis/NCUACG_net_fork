# NCUACG/songfest/requests.py
"""
點歌的規則與狀態計算。API 在 request_views.py。

- 每一場各自一份點歌清單，只有大講堂場（KTV 場是當天點歌）。
- 同一首歌（歌曲出處 + 曲名）在同一場只有一筆：別人再點就是 +1，不同 DVD 版本也算同一首。
- 點的歌在舊曲清單裡找得到就連到舊曲；找不到就是「徵剪輯」。
- 每人每場最多點 festival.request_limit 首（+1 不算）。
"""
from __future__ import annotations

from collections import defaultdict

from django.db import IntegrityError, transaction
from django.db.models import Count

from . import setlist as sl
from .models import Festival, SongRequest, SongRequestVote, Submission, Track
from .text import song_key


class RequestError(Exception):
    """點歌失敗的原因，直接顯示給使用者看。"""


def my_request_count(user, festival: Festival) -> int:
    return SongRequest.objects.filter(festival=festival, requested_by=user).count()


def find_track(source: str, title: str) -> Track | None:
    """同一首歌的舊曲（有好幾個版本時取最新的一支）。"""
    return Track.objects.filter(song_key=song_key(source, title)).order_by("-dvd_sort").first()


@transaction.atomic
def create_request(user, festival: Festival, *, track: Track | None = None, song_source: str = "",
                   visual_source: str = "", title: str = "", link: str = "", note: str = "") -> tuple[SongRequest, bool]:
    """
    點歌。已經有人點過同一首就幫他 +1。
    回傳（點歌, 是不是新的一筆）。超過上限或已經截止時丟 RequestError。
    """
    if not festival.is_request_open():
        raise RequestError("這一場已經不能點歌了")
    if track is None:
        # 歌單裡其實有這首歌：直接連到舊曲
        track = find_track(song_source, title)
    if track is not None:
        song_source, visual_source, title = track.song_source, track.visual_source, track.title

    existing = SongRequest.objects.filter(festival=festival, song_key=song_key(song_source, title)).first()
    if existing is not None:
        SongRequestVote.objects.get_or_create(request=existing, user=user)
        return existing, False

    limit = festival.request_limit
    if my_request_count(user, festival) >= limit:
        raise RequestError(f"每人每場最多點 {limit} 首（幫別人 +1 不算）")
    try:
        with transaction.atomic():
            request = SongRequest.objects.create(
                festival=festival, track=track, song_source=song_source, visual_source=visual_source,
                title=title, link=link, note=note, requested_by=user,
            )
    except IntegrityError:
        # 兩個人同時點同一首：另一個人先建好了，改成 +1
        request = SongRequest.objects.get(festival=festival, song_key=song_key(song_source, title))
        SongRequestVote.objects.get_or_create(request=request, user=user)
        return request, False
    SongRequestVote.objects.create(request=request, user=user)
    return request, True


def scheduled_sessions(festival: Festival) -> dict[str, list[str]]:
    """這場排歌台上每首歌排在哪些時段（song_key → 時段名稱）。"""
    places = defaultdict(list)
    for entry in sl._entries(festival):
        key = sl._entry_key(entry)
        if key and entry.session.name not in places[key]:
            places[key].append(entry.session.name)
    return places


def submitted_keys(keys) -> set[str]:
    """有人報了（還沒窗歌、沒被退件）的歌。"""
    return set(
        Submission.objects.filter(song_key__in=keys, withdrawn_at__isnull=True, is_rejected=False)
        .values_list("song_key", flat=True)
    )


def votes_by_key(festival: Festival) -> dict[str, int]:
    """排歌台用：每首歌在這場有幾票。"""
    return dict(
        SongRequest.objects.filter(festival=festival)
        .annotate(n=Count("votes"))
        .values_list("song_key", "n")
    )


def open_wishes(limit: int = 100) -> list[dict]:
    """
    歷屆累積的「徵剪輯」：還沒人剪過、也還沒人報的歌，依總票數排序。
    同一首歌在好幾場都被點，票數合併計算（同一個人只算一次）。
    """
    wishes = SongRequest.objects.filter(track__isnull=True).select_related("festival")
    keys = set(wishes.values_list("song_key", flat=True))
    done = set(Track.objects.filter(song_key__in=keys).values_list("song_key", flat=True)) | submitted_keys(keys)

    voters = defaultdict(set)
    for key, user_id in SongRequestVote.objects.filter(request__in=wishes).values_list("request__song_key", "user_id"):
        voters[key].add(user_id)

    latest: dict[str, SongRequest] = {}
    for wish in wishes.order_by("festival__date", "created_at"):
        if wish.song_key not in done:
            latest[wish.song_key] = wish  # 留最近一場的資料（連結、備註可能比較新）

    rows = [
        {
            "songSource": w.song_source,
            "visualSource": w.visual_source,
            "title": w.title,
            "link": w.link,
            "note": w.note,
            "votes": len(voters[key]),
            "lastFestival": w.festival.name,
        }
        for key, w in latest.items()
    ]
    rows.sort(key=lambda r: (-r["votes"], r["songSource"], r["title"]))
    return rows[:limit]
