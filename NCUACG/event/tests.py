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
