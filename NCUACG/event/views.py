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
