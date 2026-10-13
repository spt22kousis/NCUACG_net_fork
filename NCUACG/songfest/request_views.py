# NCUACG/songfest/request_views.py
"""
點歌 API（掛在 /api/songfest/ 之下）。規則在 requests.py。

任何人
  GET    requests/?festival=<id>        某一場的點歌清單（沒帶就是目前在準備的那一場），依票數排序
  GET    requests/wishes/               歷屆累積、還沒人剪的「徵剪輯」清單

登入的社員
  POST   requests/                      點歌：{festival, dvdCode} 點舊曲，或 {festival, songSource, title, visualSource?, link?, note?}
                                        已經有人點過同一首就變成 +1
  POST   requests/<id>/vote/            +1
  DELETE requests/<id>/vote/            收回 +1（點歌的人不能收回自己那票，要收回請刪掉）
  DELETE requests/<id>/                 刪除：點歌的人在沒有別人 +1 時可以刪；排歌組與幹部隨時可以刪
"""
from __future__ import annotations

from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from . import requests as rq
from .models import Festival, SongRequest, SongRequestVote, Track
from .submissions import is_staff_for
from .views import _tracks_with_stats


def _festival_dict(festival: Festival, user) -> dict:
    data = {
        "id": festival.id,
        "name": festival.name,
        "date": festival.date.isoformat(),
        "open": festival.is_request_open(),
        "deadline": festival.request_deadline.isoformat() if festival.request_deadline else None,
        "limit": festival.request_limit,
        "myCount": 0,
        "isStaff": False,
    }
    if user.is_authenticated:
        data["myCount"] = rq.my_request_count(user, festival)
        data["isStaff"] = is_staff_for(user, festival)
    return data


def _request_dicts(festival: Festival, user, requests, staff: bool | None = None) -> list[dict]:
    """staff 沒給就看 user 是不是這場的排歌組（排歌台呼叫時直接給 True）。"""
    requests = list(requests)
    keys = [r.song_key for r in requests]
    places = rq.scheduled_sessions(festival)
    submitted = rq.submitted_keys(keys)
    stats = {t.id: t for t in _tracks_with_stats().filter(pk__in=[r.track_id for r in requests if r.track_id])}
    if staff is None:
        staff = user.is_authenticated and is_staff_for(user, festival)

    rows = []
    for r in requests:
        track = stats.get(r.track_id)
        votes = r.vote_count
        is_mine = bool(user and user.is_authenticated and r.requested_by_id == user.id)
        rows.append({
            "id": r.id,
            "kind": "old" if r.track_id else "wish",
            "dvdCode": track.dvd_code if track else None,
            "songSource": r.song_source,
            "visualSource": r.visual_source,
            "title": r.title,
            "editor": track.editor if track else "",
            "duration": track.duration_seconds if track else None,
            "lastPlayed": track.last_played.isoformat() if track and track.last_played else None,
            "recentPlayCount": track.recent_play_count if track else 0,
            "link": r.link,
            "note": r.note,
            "requestedBy": r.requested_by.name if r.requested_by else "",
            "votes": votes,
            "voted": bool(getattr(r, "voted", False)),
            "isMine": is_mine,
            "canDelete": staff or (is_mine and votes <= 1),
            # 排進哪些時段（排歌台公布前只有排歌組看得到，免得大家以為定案了）
            "scheduledIn": places.get(r.song_key, []) if (staff or festival.setlist_public) else [],
            "submitted": r.song_key in submitted,
            "createdAt": r.created_at.isoformat(),
        })
    return rows


def _requests_queryset(user=None):
    qs = SongRequest.objects.select_related("requested_by").annotate(vote_count=Count("votes"))
    if user is not None and user.is_authenticated:
        qs = qs.annotate(voted=Exists(SongRequestVote.objects.filter(request=OuterRef("pk"), user=user)))
    return qs


class RequestInput(serializers.Serializer):
    festival = serializers.PrimaryKeyRelatedField(queryset=Festival.objects.all(), required=False)
    dvdCode = serializers.CharField(required=False, allow_blank=True)
    songSource = serializers.CharField(max_length=255, required=False, allow_blank=True)
    visualSource = serializers.CharField(max_length=255, required=False, allow_blank=True)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    link = serializers.URLField(required=False, allow_blank=True)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs.get("dvdCode"):
            try:
                attrs["track"] = Track.objects.get(dvd_code=attrs["dvdCode"].strip().upper())
            except Track.DoesNotExist:
                raise serializers.ValidationError({"dvdCode": "找不到這個 DVD 編號"})
        elif not (attrs.get("songSource", "").strip() and attrs.get("title", "").strip()):
            raise serializers.ValidationError({"title": "請填歌曲出處與曲名，或從舊曲清單選一首"})
        return attrs


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedOrReadOnly])
def request_list(request):
    if request.method == "POST":
        ser = RequestInput(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        festival = data.get("festival") or Festival.active()
        if festival is None:
            return Response({"detail": "目前沒有可以點歌的歌謠祭"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            song_request, created = rq.create_request(
                request.user, festival, track=data.get("track"),
                song_source=data.get("songSource", "").strip(), visual_source=data.get("visualSource", "").strip(),
                title=data.get("title", "").strip(), link=data.get("link", ""), note=data.get("note", "").strip(),
            )
        except rq.RequestError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        row = _request_dicts(festival, request.user, _requests_queryset(request.user).filter(pk=song_request.pk))[0]
        return Response({"request": row, "created": created, "festival": _festival_dict(festival, request.user)},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    festival_id = request.GET.get("festival")
    festival = get_object_or_404(Festival, pk=festival_id) if festival_id else Festival.active()
    if festival is None:
        return Response({"festival": None, "requests": []})
    qs = _requests_queryset(request.user).filter(festival=festival).order_by("-vote_count", "created_at")
    return Response({
        "festival": _festival_dict(festival, request.user),
        "requests": _request_dicts(festival, request.user, qs),
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def wish_list(request):
    return Response(rq.open_wishes())


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def request_vote(request, request_id: int):
    song_request = get_object_or_404(SongRequest.objects.select_related("festival"), pk=request_id)
    if request.method == "POST":
        if not song_request.festival.is_request_open():
            return Response({"detail": "這一場已經不能點歌了"}, status=status.HTTP_400_BAD_REQUEST)
        SongRequestVote.objects.get_or_create(request=song_request, user=request.user)
    else:
        if song_request.requested_by_id == request.user.id:
            return Response({"detail": "點歌的人不能收回自己那票；不想點了可以直接刪掉"}, status=status.HTTP_400_BAD_REQUEST)
        SongRequestVote.objects.filter(request=song_request, user=request.user).delete()
    return Response({"votes": song_request.votes.count(), "voted": request.method == "POST"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def request_detail(request, request_id: int):
    song_request = get_object_or_404(SongRequest.objects.select_related("festival"), pk=request_id)
    staff = is_staff_for(request.user, song_request.festival)
    mine = song_request.requested_by_id == request.user.id
    if not staff:
        if not mine:
            return Response({"detail": "只能刪自己點的歌"}, status=status.HTTP_403_FORBIDDEN)
        if song_request.votes.exclude(user=request.user).exists():
            return Response({"detail": "已經有人 +1 了，不能刪；有問題請找排歌組"}, status=status.HTTP_400_BAD_REQUEST)
    song_request.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
