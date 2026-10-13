# NCUACG/event/views.py
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Event
from .serializers import EventSerializer


def _event_to_dict(e: Event) -> dict:
    """輸出前端好用的扁平 JSON（ISO 8601 時間字串）。"""
    return {
        "id": e.id,
        "title": e.title,
        "description": e.description,
        "location": e.location,
        "start_time": e.start_time.isoformat() if e.start_time else None,
        "end_time": e.end_time.isoformat() if getattr(e, "end_time", None) else None,
    }


@api_view(["GET"])
def upcoming_events(request):
    """
    回傳「還沒結束、而且在未來 N 天內開始」的活動（預設 30 天）。
    進行中的活動也會回傳：有結束時間就看結束時間，沒有結束時間才看開始時間。
    GET 參數:
      - days: int，可選，預設 30
    回傳:
      - 依 start_time 遞增排序的活動列表
    """
    now = timezone.now()
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30

    until = now + timezone.timedelta(days=days)

    # 原本只看 start_time >= now，進行中的活動會在開始的那一秒就從公告消失
    not_ended = Q(end_time__gte=now) | Q(end_time__isnull=True, start_time__gte=now)

    qs = (
        Event.objects
        .filter(not_ended, is_published=True, start_time__lte=until)
        .order_by("start_time")
    )

    data = [_event_to_dict(e) for e in qs]
    return Response(data)


@api_view(["GET"])
def ping(request):
    """簡易健康檢查用端點。"""
    return JsonResponse({"ok": True, "now": timezone.now().isoformat()})


# 行事曆一次最多抓的天數（一個月的格子含前後週，大約 42 天）
CALENDAR_MAX_DAYS = 62


@api_view(["GET"])
def calendar(request):
    """
    行事曆：把活動公告、社課堂次、歌謠祭放在同一份清單。
    GET 參數:
      - from, to: YYYY-MM-DD，to 不含；最多相隔 62 天
    回傳:
      - [{id, kind: event|lesson|songfest, title, start, end, allDay, location, category, link}]，依開始時間排序
    """
    from club.lessons import CATEGORY_NAMES
    from club.models import Lesson
    from songfest.models import Festival

    try:
        start_day = timezone.datetime.fromisoformat(request.GET["from"]).date()
        end_day = timezone.datetime.fromisoformat(request.GET["to"]).date()
    except (KeyError, ValueError):
        return Response({"detail": "請用 from=YYYY-MM-DD&to=YYYY-MM-DD 指定期間"}, status=400)
    if end_day <= start_day or (end_day - start_day).days > CALENDAR_MAX_DAYS:
        return Response({"detail": f"期間最多 {CALENDAR_MAX_DAYS} 天"}, status=400)

    tz = timezone.get_current_timezone()
    start = timezone.datetime.combine(start_day, timezone.datetime.min.time(), tzinfo=tz)
    end = timezone.datetime.combine(end_day, timezone.datetime.min.time(), tzinfo=tz)
    # 跨進這段期間的也算：開始在期間結束前，而且結束（沒有結束時間就看開始）在期間開始後
    overlaps = Q(start_time__lt=end) & (Q(end_time__gte=start) | Q(end_time__isnull=True, start_time__gte=start))

    items = []
    for e in Event.objects.filter(overlaps, is_published=True):
        items.append({
            "id": f"event-{e.id}", "kind": "event", "title": e.title,
            "start": e.start_time.isoformat(), "end": e.end_time.isoformat() if e.end_time else None,
            "allDay": False, "location": e.location, "category": None, "link": "/announcement",
        })
    for lesson in Lesson.objects.filter(overlaps, is_published=True):
        name = CATEGORY_NAMES.get(lesson.category, lesson.category)
        items.append({
            "id": f"lesson-{lesson.id}", "kind": "lesson", "title": f"{name}社課：{lesson.title}",
            "start": lesson.start_time.isoformat(),
            "end": lesson.end_time.isoformat() if lesson.end_time else None,
            "allDay": False, "location": lesson.location, "category": lesson.category,
            "link": f"/club/lessons/{lesson.id}",
        })
    for f in Festival.objects.filter(is_published=True, date__gte=start_day, date__lt=end_day):
        items.append({
            "id": f"songfest-{f.id}", "kind": "songfest", "title": f"中央歌謠祭 {f.name}",
            "start": timezone.datetime.combine(f.date, timezone.datetime.min.time(), tzinfo=tz).isoformat(),
            "end": None, "allDay": True, "location": f.venue, "category": None, "link": "/songfest",
        })
    items.sort(key=lambda item: item["start"])
    return Response(items)
