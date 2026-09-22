# NCUACG/event/views.py
from __future__ import annotations

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
    只回傳『現在起、未來 N 天內』的活動（預設 30 天）。
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

    qs = (
        Event.objects
        .filter(is_published=True, start_time__gte=now, start_time__lte=until)
        .order_by("start_time")
    )

    data = [_event_to_dict(e) for e in qs]
    return Response(data)


@api_view(["GET"])
def ping(request):
    """簡易健康檢查用端點。"""
    return JsonResponse({"ok": True, "now": timezone.now().isoformat()})
