# NCUACG/checkin/views.py
"""
活動簽到 API（掛在 /api/checkin/ 之下）。權限與場次產生在 rules.py。

管理（幹部、該場排歌組、該社課負責人；學號只有這些人看得到）
  GET    events/                        我能管的簽到活動（含各場人數）與可以建立簽到的歌謠祭、社課
  POST   events/                        {festival} / {lesson} / {title, slots: [{name, startsAt, endsAt}]}
  GET    events/export/                 所有活動的人數統計（CSV，寫評鑑資料用）
  GET    events/<id>/                   活動、場次、掃描密鑰與全部紀錄
  PATCH  events/<id>/                   {title}
  DELETE events/<id>/                   連同紀錄一起刪除
  POST   events/<id>/reset-key/         重設掃描連結（舊連結立刻失效）
  POST   events/<id>/slots/             新增場次
  PATCH  slots/<id>/                    改場次名稱、時間、簽到時段
  DELETE slots/<id>/
  DELETE records/<id>/                  刪掉掃錯的一筆
  GET    events/<id>/export/?type=detail|summary   明細／彙整 CSV（格式同 barcoder demo）

掃描頁（frontend/public/scan/，靠網址上的 key，不用登入）
  GET    scan/<id>/?key=                活動名稱、場次與各場人數
  POST   scan/<id>/records/?key=        {device, records: [{cid, slot, sid, raw, src, ts}]}
                                        一次送一批，cid 重複的當作已收到；回傳每筆結果與最新人數
"""
from __future__ import annotations

import csv
import datetime as dt
import secrets
from io import StringIO
from urllib.parse import quote

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from club.models import Lesson
from songfest.models import Festival

from . import rules
from .models import Checkin, CheckinEvent, CheckinSlot

SOURCE_LABEL = dict(Checkin.SOURCE_CHOICES)
MAX_BATCH = 200


def _iso(value):
    return value.isoformat() if value else None


def _local(value) -> dt.datetime:
    return timezone.localtime(value)


def _counts(event: CheckinEvent) -> dict[int, int]:
    return dict(
        CheckinSlot.objects.filter(event=event).annotate(n=Count("checkins")).values_list("id", "n")
    )


def _slot_dict(slot: CheckinSlot, counts: dict[int, int]) -> dict:
    return {
        "id": slot.id,
        "name": slot.name,
        "startsAt": _iso(slot.starts_at),
        "endsAt": _iso(slot.ends_at),
        "opensAt": _iso(slot.opens_at),
        "closesAt": _iso(slot.closes_at),
        "count": counts.get(slot.id, 0),
    }


def _event_dict(event: CheckinEvent, with_key=False) -> dict:
    counts = _counts(event)
    slots = list(event.slots.all())
    data = {
        "id": event.id,
        "title": event.title,
        "kind": event.kind,
        "festivalId": event.festival_id,
        "lessonId": event.lesson_id,
        "date": _local(slots[0].starts_at).date().isoformat() if slots else None,
        "slots": [_slot_dict(s, counts) for s in slots],
        "total": sum(counts.values()),
        # 不重複人數：同一個人簽了好幾場只算一次
        "people": Checkin.objects.filter(slot__event=event).values("student_id").distinct().count(),
    }
    if with_key:
        data["scanKey"] = event.scan_key
    return data


def _forbidden():
    return Response({"detail": "只有幹部、該場排歌組或該社課負責人可以管理這個簽到"}, status=status.HTTP_403_FORBIDDEN)


def _managed_event(request, event_id) -> CheckinEvent | None:
    event = get_object_or_404(CheckinEvent.objects.select_related("lesson"), pk=event_id)
    return event if rules.can_manage(request.user, event) else None


# ── 管理 ────────────────────────────────────────────────────────────────────

class SlotInput(serializers.Serializer):
    name = serializers.CharField(max_length=50, required=False)
    startsAt = serializers.DateTimeField(required=False)
    endsAt = serializers.DateTimeField(required=False)
    opensAt = serializers.DateTimeField(required=False)
    closesAt = serializers.DateTimeField(required=False)


class EventInput(serializers.Serializer):
    festival = serializers.PrimaryKeyRelatedField(queryset=Festival.objects.all(), required=False)
    lesson = serializers.PrimaryKeyRelatedField(queryset=Lesson.objects.all(), required=False)
    title = serializers.CharField(max_length=100, required=False)
    slots = SlotInput(many=True, required=False)


def _apply_slot(slot: CheckinSlot, data: dict) -> None:
    for field, attr in (("name", "name"), ("startsAt", "starts_at"), ("endsAt", "ends_at"),
                        ("opensAt", "opens_at"), ("closesAt", "closes_at")):
        if field in data:
            setattr(slot, attr, data[field])
    # 沒給簽到時段就用整場
    slot.opens_at = slot.opens_at or slot.starts_at
    slot.closes_at = slot.closes_at or slot.ends_at


def _validate_slot(slot: CheckinSlot) -> str | None:
    if not (slot.name and slot.starts_at and slot.ends_at):
        return "場次要有名稱、開始與結束時間"
    if slot.ends_at <= slot.starts_at:
        return f"「{slot.name}」的結束時間要晚於開始時間"
    if slot.closes_at <= slot.opens_at:
        return f"「{slot.name}」的停止簽到要晚於開放簽到"
    return None


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def event_list(request):
    if not rules.can_use_checkin(request.user):
        return _forbidden()

    if request.method == "GET":
        events = rules.manageable_events(request.user).prefetch_related("slots").order_by("-created_at")
        rows = sorted((_event_dict(e) for e in events), key=lambda e: e["date"] or "", reverse=True)
        return Response({"events": rows, "sources": rules.creatable_sources(request.user)})

    ser = EventInput(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    sources = rules.creatable_sources(request.user)
    if data.get("festival"):
        festival = data["festival"]
        if not any(f["id"] == festival.id for f in sources["festivals"]):
            return Response({"detail": "這場歌謠祭已經有簽到，或你不是這場的排歌組"}, status=status.HTTP_400_BAD_REQUEST)
        event = rules.create_for_festival(festival, request.user)
    elif data.get("lesson"):
        lesson = data["lesson"]
        if not any(l["id"] == lesson.id for l in sources["lessons"]):
            return Response({"detail": "這堂社課已經有簽到，或你不是這個社課的負責人"}, status=status.HTTP_400_BAD_REQUEST)
        event = rules.create_for_lesson(lesson, request.user)
    else:
        if not sources["custom"]:
            return _forbidden()
        if not data.get("title") or not data.get("slots"):
            return Response({"detail": "自訂活動要有名稱和至少一個場次"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            event = CheckinEvent.objects.create(title=data["title"].strip(), created_by=request.user)
            for order, slot_data in enumerate(data["slots"]):
                slot = CheckinSlot(event=event, order=order)
                _apply_slot(slot, slot_data)
                error = _validate_slot(slot)
                if error:
                    transaction.set_rollback(True)
                    return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
                slot.save()
    return Response(_event_dict(event, with_key=True), status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def event_detail(request, event_id: int):
    event = _managed_event(request, event_id)
    if event is None:
        return _forbidden()
    if request.method == "DELETE":
        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    if request.method == "PATCH":
        title = str(request.data.get("title", "")).strip()
        if title:
            event.title = title[:100]
            event.save(update_fields=["title"])

    data = _event_dict(event, with_key=True)
    records = Checkin.objects.filter(slot__event=event).select_related("slot").order_by("-scanned_at")
    data["records"] = [
        {"id": r.id, "slotId": r.slot_id, "slotName": r.slot.name, "studentId": r.student_id,
         "source": SOURCE_LABEL.get(r.source, r.source), "scannedAt": _iso(r.scanned_at), "device": r.device}
        for r in records
    ]
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reset_key(request, event_id: int):
    event = _managed_event(request, event_id)
    if event is None:
        return _forbidden()
    event.scan_key = secrets.token_urlsafe(18)
    event.save(update_fields=["scan_key"])
    return Response({"scanKey": event.scan_key})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def slot_create(request, event_id: int):
    event = _managed_event(request, event_id)
    if event is None:
        return _forbidden()
    ser = SlotInput(data=request.data)
    ser.is_valid(raise_exception=True)
    slot = CheckinSlot(event=event, order=event.slots.count())
    _apply_slot(slot, ser.validated_data)
    error = _validate_slot(slot)
    if error:
        return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
    slot.save()
    return Response(_event_dict(event, with_key=True), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def slot_detail(request, slot_id: int):
    slot = get_object_or_404(CheckinSlot.objects.select_related("event", "event__lesson"), pk=slot_id)
    if not rules.can_manage(request.user, slot.event):
        return _forbidden()
    if request.method == "DELETE":
        slot.delete()
    else:
        ser = SlotInput(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        _apply_slot(slot, ser.validated_data)
        error = _validate_slot(slot)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        slot.save()
    return Response(_event_dict(slot.event, with_key=True))


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def record_detail(request, record_id: int):
    record = get_object_or_404(Checkin.objects.select_related("slot__event", "slot__event__lesson"), pk=record_id)
    if not rules.can_manage(request.user, record.slot.event):
        return _forbidden()
    record.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ── 匯出 ────────────────────────────────────────────────────────────────────

def _csv_cell(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text  # 避免 Excel 當成公式


def _csv_response(rows: list[list], filename: str) -> HttpResponse:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    for row in rows:
        writer.writerow([_csv_cell(v) for v in row])
    # 加 BOM，Excel 開中文才不會亂碼（跟 barcoder demo 一樣）
    response = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def event_export(request, event_id: int):
    """明細與彙整，欄位跟 barcoder demo 匯出的 CSV 一樣。"""
    event = _managed_event(request, event_id)
    if event is None:
        return _forbidden()
    slots = list(event.slots.all())
    records = list(Checkin.objects.filter(slot__event=event).select_related("slot").order_by("scanned_at"))
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")

    if request.GET.get("type") == "summary":
        dates = sorted({_local(s.starts_at).date() for s in slots})
        label = (lambda s: f"{_local(s.starts_at).date()} {s.name}") if len(dates) > 1 else (lambda s: s.name)
        attended: dict[str, set[int]] = {}
        for r in records:
            attended.setdefault(r.student_id, set()).add(r.slot_id)
        rows = [["學號", *[label(s) for s in slots], "簽到場數"]]
        for sid in sorted(attended):
            rows.append([sid, *["有" if s.id in attended[sid] else "無" for s in slots], len(attended[sid])])
        return _csv_response(rows, f"{event.title}簽到_彙整_{stamp}.csv")

    rows = [["學號", "日期", "時間", "場次", "來源", "原始條碼"]]
    for r in records:
        local = _local(r.scanned_at)
        rows.append([r.student_id, local.date().isoformat(), local.strftime("%H:%M:%S"), r.slot.name,
                     SOURCE_LABEL.get(r.source, r.source), r.raw])
    return _csv_response(rows, f"{event.title}簽到_明細_{stamp}.csv")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def events_export(request):
    """每個活動、每個場次的人數，學期末寫評鑑資料用。不含學號。"""
    if not rules.can_use_checkin(request.user):
        return _forbidden()
    rows = [["日期", "活動", "種類", "場次", "簽到人數"]]
    kinds = {"songfest": "歌謠祭", "lesson": "社課", "other": "其他"}
    slots = (
        CheckinSlot.objects.filter(event__in=rules.manageable_events(request.user))
        .select_related("event").annotate(n=Count("checkins")).order_by("starts_at")
    )
    for s in slots:
        rows.append([_local(s.starts_at).date().isoformat(), s.event.title, kinds[s.event.kind], s.name, s.n])
    return _csv_response(rows, f"活動簽到人數統計_{timezone.localdate():%Y%m%d}.csv")


# ── 掃描頁 ──────────────────────────────────────────────────────────────────

def _scan_event(request, event_id) -> CheckinEvent | None:
    key = request.GET.get("key", "")
    event = CheckinEvent.objects.filter(pk=event_id).first()
    if event is None or not key or not secrets.compare_digest(key, event.scan_key):
        return None
    return event


def _scan_info(event: CheckinEvent) -> dict:
    counts = _counts(event)
    return {
        "event": {"id": event.id, "title": event.title},
        "slots": [_slot_dict(s, counts) for s in event.slots.all()],
        # 掃描頁用來提醒「這台裝置的時間不準」
        "serverTime": _iso(timezone.now()),
    }


@api_view(["GET"])
@authentication_classes([])  # 只看網址上的 key，不管有沒有登入
@permission_classes([AllowAny])
def scan_info(request, event_id: int):
    event = _scan_event(request, event_id)
    if event is None:
        return Response({"detail": "掃描連結無效或已經重設，請跟負責人要新的連結"}, status=status.HTTP_403_FORBIDDEN)
    return Response(_scan_info(event))


class ScanRecord(serializers.Serializer):
    cid = serializers.CharField(max_length=64)
    slot = serializers.IntegerField()
    sid = serializers.CharField(max_length=40)
    raw = serializers.CharField(max_length=200, required=False, allow_blank=True)
    src = serializers.ChoiceField(choices=list(SOURCE_LABEL), required=False, default="camera")
    ts = serializers.IntegerField(help_text="裝置上的掃描時間（毫秒）")


class ScanBatch(serializers.Serializer):
    device = serializers.CharField(max_length=64, required=False, allow_blank=True)
    records = ScanRecord(many=True)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def scan_records(request, event_id: int):
    event = _scan_event(request, event_id)
    if event is None:
        return Response({"detail": "掃描連結無效或已經重設，請跟負責人要新的連結"}, status=status.HTTP_403_FORBIDDEN)
    ser = ScanBatch(data=request.data)
    ser.is_valid(raise_exception=True)
    batch = ser.validated_data["records"][:MAX_BATCH]
    device = ser.validated_data.get("device", "")
    slot_ids = set(event.slots.values_list("id", flat=True))

    results = {}
    for item in batch:
        cid = item["cid"]
        if Checkin.objects.filter(client_id=cid).exists():
            results[cid] = "ok"  # 同一筆重送：之前已經收到了
            continue
        sid = rules.normalize_student_id(item["sid"])
        if item["slot"] not in slot_ids or not rules.STUDENT_ID.match(sid):
            results[cid] = "invalid"
            continue
        try:
            scanned_at = dt.datetime.fromtimestamp(item["ts"] / 1000, tz=dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            results[cid] = "invalid"
            continue
        try:
            with transaction.atomic():
                Checkin.objects.create(
                    slot_id=item["slot"], student_id=sid, raw=item.get("raw", "")[:64], source=item["src"],
                    scanned_at=scanned_at, client_id=cid, device=device,
                )
            results[cid] = "ok"
        except IntegrityError:
            # 別台裝置已經掃過這個人（同一場只留第一筆）
            results[cid] = "dup"
    return Response({"results": results, **_scan_info(event)})

