# NCUACG/event/tests.py
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from event.models import Event


class UpcomingEventsTests(TestCase):
    def titles(self):
        return [e["title"] for e in APIClient().get("/api/event/upcoming/").data]

    def test_filters(self):
        now = timezone.now()
        Event.objects.create(title="未來", start_time=now + timedelta(days=1))
        Event.objects.create(title="進行中", start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=1))
        Event.objects.create(title="已結束", start_time=now - timedelta(hours=3), end_time=now - timedelta(hours=1))
        Event.objects.create(title="未發布", start_time=now + timedelta(days=1), is_published=False)
        Event.objects.create(title="太遠", start_time=now + timedelta(days=60))

        self.assertEqual(self.titles(), ["進行中", "未來"])


class CalendarTests(TestCase):
    def test_merges_events_lessons_and_songfest(self):
        from club.models import Lesson
        from songfest.models import Festival

        tz = timezone.get_current_timezone()
        day = lambda d, h=12: timezone.datetime(2026, 10, d, h, tzinfo=tz)  # noqa: E731
        Event.objects.create(title="社員大會", start_time=day(5))
        Event.objects.create(title="跨月活動", start_time=day(1) - timedelta(days=2), end_time=day(1, 18))
        Event.objects.create(title="上個月", start_time=day(1) - timedelta(days=5))
        Lesson.objects.create(category="railway", title="高鐵與捷運", start_time=day(12, 18))
        Lesson.objects.create(category="railway", title="草稿", start_time=day(13), is_published=False)
        Festival.objects.create(name="115上期中", date=timezone.datetime(2026, 10, 20).date())

        res = APIClient().get("/api/event/calendar/?from=2026-10-01&to=2026-11-01")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            [(item["kind"], item["title"]) for item in res.data],
            [("event", "跨月活動"), ("event", "社員大會"), ("lesson", "鐵道社課：高鐵與捷運"),
             ("songfest", "中央歌謠祭 115上期中")],
        )
        self.assertTrue(res.data[-1]["allDay"])

    def test_range_is_required_and_limited(self):
        self.assertEqual(APIClient().get("/api/event/calendar/").status_code, 400)
        self.assertEqual(APIClient().get("/api/event/calendar/?from=2026-01-01&to=2026-12-01").status_code, 400)
