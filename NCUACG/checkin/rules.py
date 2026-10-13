# NCUACG/checkin/rules.py
"""活動簽到的權限、學號格式與場次產生。API 在 views.py。"""
from __future__ import annotations

import datetime as dt
import re

from django.db.models import Q
from django.utils import timezone

from club.lessons import CATEGORY_NAMES, is_officer, lead_categories
from club.models import Lesson
from songfest import setlist as sl
from songfest.models import Festival, FestivalStaff

from .models import CheckinEvent, CheckinSlot

# 學號 9 碼數字。學生證條碼是 Code 128 的 10 碼數字＝9 碼學號＋1 碼卡片序號（跟 barcoder demo 一樣）
STUDENT_ID = re.compile(r"^\d{9}$")


def normalize_student_id(raw: str) -> str:
    """去掉空白、控制字元、Code 39 的 * 起訖符號並轉大寫；10 碼數字只取前 9 碼。"""
    text = re.sub(r"[\s\x00-\x1f\x7f]", "", str(raw or "")).strip("*").upper()
    return text[:9] if re.fullmatch(r"\d{10}", text) else text


# ── 權限 ────────────────────────────────────────────────────────────────────

def can_manage(user, event: CheckinEvent) -> bool:
    """幹部；歌謠祭由該場排歌組、社課由該社課負責人管理；自訂活動由建立者管理。學號只有這些人看得到。"""
    if not (user and user.is_authenticated):
        return False
    if is_officer(user) or event.created_by_id == user.id:
        return True
    if event.festival_id:
        return FestivalStaff.objects.filter(festival_id=event.festival_id, user=user).exists()
    if event.lesson_id:
        return event.lesson.category in lead_categories(user)
    return False


def manageable_events(user):
    if is_officer(user):
        return CheckinEvent.objects.all()
    festivals = FestivalStaff.objects.filter(user=user).values("festival")
    return CheckinEvent.objects.filter(
        Q(created_by=user) | Q(festival__in=festivals) | Q(lesson__category__in=lead_categories(user))
    )


def can_use_checkin(user) -> bool:
    """側邊欄要不要顯示「活動簽到」。"""
    if not (user and user.is_authenticated):
        return False
    return is_officer(user) or bool(lead_categories(user)) or FestivalStaff.objects.filter(user=user).exists()


def creatable_sources(user) -> dict:
    """可以建立簽到的歌謠祭與社課：前後一段時間內、還沒建立過簽到的。自訂活動只有幹部能建。"""
    today = timezone.localdate()
    festivals = Festival.objects.filter(
        kind="hall", date__gte=today - dt.timedelta(days=30), date__lte=today + dt.timedelta(days=120),
        checkin_event__isnull=True,
    )
    lessons = Lesson.objects.filter(
        start_time__date__gte=today - dt.timedelta(days=30), start_time__date__lte=today + dt.timedelta(days=60),
        checkin_event__isnull=True,
    )
    if not is_officer(user):
        festivals = festivals.filter(staff__user=user)
        lessons = lessons.filter(category__in=lead_categories(user))
    return {
        "festivals": [{"id": f.id, "name": f.name, "date": f.date.isoformat()} for f in festivals.order_by("date")],
        "lessons": [
            {"id": l.id, "title": f"{CATEGORY_NAMES.get(l.category, l.category)}社課：{l.title}",
             "date": timezone.localtime(l.start_time).date().isoformat()}
            for l in lessons.order_by("start_time")
        ],
        "custom": is_officer(user),
    }


# ── 場次 ────────────────────────────────────────────────────────────────────

def _at(day: dt.date, time: dt.time) -> dt.datetime:
    return timezone.make_aware(dt.datetime.combine(day, time))


def create_for_festival(festival: Festival, user) -> CheckinEvent:
    """歌謠祭：用排歌台的時段（不含測試曲），簽到時段預設整場。"""
    sl.ensure_sessions(festival)
    event = CheckinEvent.objects.create(title=f"歌謠祭 {festival.name}", festival=festival, created_by=user)
    for order, session in enumerate(festival.sessions.filter(is_test=False).order_by("order")):
        start = _at(festival.date, session.start_time)
        end = _at(festival.date, session.end_time) if session.end_time else start + dt.timedelta(hours=2)
        CheckinSlot.objects.create(event=event, name=session.name, order=order,
                                   starts_at=start, ends_at=end, opens_at=start, closes_at=end)
    return event


def create_for_lesson(lesson: Lesson, user) -> CheckinEvent:
    """社課：一個場次，沒有結束時間就算兩小時。"""
    title = f"{CATEGORY_NAMES.get(lesson.category, lesson.category)}社課：{lesson.title}"
    event = CheckinEvent.objects.create(title=title, lesson=lesson, created_by=user)
    end = lesson.end_time or lesson.start_time + dt.timedelta(hours=2)
    CheckinSlot.objects.create(event=event, name=lesson.title[:50], starts_at=lesson.start_time, ends_at=end,
                               opens_at=lesson.start_time, closes_at=end)
    return event
