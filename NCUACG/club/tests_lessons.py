# NCUACG/club/tests_lessons.py
import datetime as dt

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.tests import auth_client, make_user
from club.lessons import discord_text
from club.models import CourseLead, Lesson

TZ = timezone.get_current_timezone()


def at(month, day, hour, minute=0, year=2026):
    return dt.datetime(year, month, day, hour, minute, tzinfo=TZ)


class DiscordTextTests(TestCase):
    def test_matches_the_usual_announcement(self):
        first = Lesson.objects.create(category="railway", number=1, title="鐵道基本知識", start_time=at(9, 28, 18))
        second = Lesson.objects.create(category="railway", number=2, title="台灣鐵道", start_time=at(10, 5, 18))
        lesson = Lesson.objects.create(
            category="railway", number=3, title="高鐵與捷運",
            start_time=at(10, 12, 18), end_time=at(10, 12, 20),
            content="鐵道社課第三堂課，我們要來認識高鐵與捷運。\n歡迎對這個主題有興趣的各位來參加！！",
            notes="負責人在準備段考，可能ppt做得有點隨便\n敬請見諒",
            prerequisites="搭乘過台灣高鐵與台北捷運",
            discord_role="@鐵道社課通知",
        )
        lesson.requires.set([second, first])

        self.assertEqual(discord_text(lesson), "\n".join([
            "【鐵道社課】",
            "時間：10/12 18:00~20:00",
            "地點：社辦",
            "內容：高鐵與捷運",
            "鐵道社課第三堂課，我們要來認識高鐵與捷運。",
            "歡迎對這個主題有興趣的各位來參加！！",
            "-" * 72,
            "負責人在準備段考，可能ppt做得有點隨便",
            "敬請見諒",
            "建議具備",
            "搭乘過台灣高鐵與台北捷運",
            "參加過前面的社課（《鐵道基本知識》、《台灣鐵道》）",
            "@鐵道社課通知",
        ]))

    def test_minimal_lesson_has_no_divider(self):
        lesson = Lesson.objects.create(category="art", title="速寫", start_time=at(10, 13, 19))
        self.assertEqual(discord_text(lesson), "【繪畫社課】\n時間：10/13 19:00\n地點：社辦\n內容：速寫")

    def test_end_on_another_day_shows_the_date(self):
        lesson = Lesson.objects.create(
            category="trpg", title="通宵團", start_time=at(10, 17, 20), end_time=at(10, 18, 2),
        )
        self.assertIn("時間：10/17 20:00~10/18 02:00", discord_text(lesson))


class LessonApiTests(TestCase):
    def setUp(self):
        self.lead = make_user("lead@example.test")
        self.member = make_user("member@example.test")
        self.officer = make_user("officer@example.test", is_staff=True)
        CourseLead.objects.create(category="railway", user=self.lead)
        now = timezone.now()
        self.upcoming = Lesson.objects.create(category="railway", title="下一堂", start_time=now + dt.timedelta(days=2))
        self.past = Lesson.objects.create(category="railway", title="上一堂", start_time=now - dt.timedelta(days=5))
        self.hidden = Lesson.objects.create(
            category="railway", title="草稿", start_time=now + dt.timedelta(days=9), is_published=False,
        )
        self.other = Lesson.objects.create(category="art", title="繪畫課", start_time=now + dt.timedelta(days=3))

    def payload(self, **extra):
        return {
            "category": "railway", "title": "高鐵與捷運",
            "startTime": "2026-10-12T18:00:00+08:00", "endTime": "2026-10-12T20:00:00+08:00", **extra,
        }

    def test_public_list_by_category_includes_past_but_not_hidden(self):
        res = APIClient().get("/api/club/lessons/?category=railway")
        self.assertEqual([lesson["title"] for lesson in res.data], ["上一堂", "下一堂"])
        self.assertNotIn("discordText", res.data[0])

    def test_upcoming_list_for_notice_board(self):
        res = APIClient().get("/api/club/lessons/?days=30")
        self.assertEqual([lesson["title"] for lesson in res.data], ["下一堂", "繪畫課"])

    def test_range_is_limited(self):
        self.assertEqual(APIClient().get("/api/club/lessons/?from=2026-01-01&to=2026-12-31").status_code, 400)
        self.assertEqual(APIClient().get("/api/club/lessons/?from=2026-10-01&to=2026-11-01").status_code, 200)

    def test_hidden_lesson_is_visible_only_to_its_leads(self):
        url = f"/api/club/lessons/{self.hidden.id}/"
        self.assertEqual(APIClient().get(url).status_code, 404)
        self.assertEqual(auth_client(self.member).get(url).status_code, 404)
        res = auth_client(self.lead).get(url)
        self.assertEqual(res.status_code, 200)
        self.assertIn("discordText", res.data)

    def test_manage_lists_only_my_categories(self):
        res = auth_client(self.lead).get("/api/club/lessons/manage/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["categories"], [{"id": "railway", "name": "鐵道"}])
        self.assertEqual({lesson["title"] for lesson in res.data["lessons"]}, {"下一堂", "上一堂", "草稿"})
        self.assertEqual(res.data["defaults"]["railway"]["discordRole"], "@鐵道社課通知")

    def test_members_cannot_manage(self):
        self.assertEqual(auth_client(self.member).get("/api/club/lessons/manage/").status_code, 403)
        res = auth_client(self.member).post("/api/club/lessons/manage/", self.payload(), format="json")
        self.assertEqual(res.status_code, 403)
        res = auth_client(self.member).patch(f"/api/club/lessons/{self.upcoming.id}/", {"title": "x"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_lead_creates_and_edits_own_category_only(self):
        client = auth_client(self.lead)
        res = client.post("/api/club/lessons/manage/", self.payload(requires=[self.past.id]), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["discordText"].startswith("【鐵道社課】\n時間：10/12 18:00~20:00"))
        self.assertEqual(Lesson.objects.get(pk=res.data["id"]).created_by, self.lead)

        res = client.post("/api/club/lessons/manage/", self.payload(category="art"), format="json")
        self.assertEqual(res.status_code, 400)
        res = client.patch(f"/api/club/lessons/{self.other.id}/", {"title": "x"}, format="json")
        self.assertEqual(res.status_code, 403)
        # 改成別的社課也不行
        res = client.patch(f"/api/club/lessons/{self.upcoming.id}/", {"category": "art"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_requires_must_be_same_category_and_not_itself(self):
        client = auth_client(self.lead)
        res = client.post("/api/club/lessons/manage/", self.payload(requires=[self.other.id]), format="json")
        self.assertEqual(res.status_code, 400)
        res = client.patch(f"/api/club/lessons/{self.past.id}/", {"requires": [self.past.id]}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_end_before_start_is_rejected(self):
        res = auth_client(self.lead).post(
            "/api/club/lessons/manage/", self.payload(endTime="2026-10-12T17:00:00+08:00"), format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_lead_adds_slides_after_class_and_deletes(self):
        client = auth_client(self.lead)
        url = f"/api/club/lessons/{self.past.id}/"
        res = client.patch(url, {"slidesUrl": "https://example.com/slides"}, format="json")
        self.assertEqual(res.data["slidesUrl"], "https://example.com/slides")
        self.assertEqual(client.delete(url).status_code, 204)

    def test_officer_manages_every_category(self):
        res = auth_client(self.officer).get("/api/club/lessons/manage/")
        self.assertEqual(len(res.data["categories"]), 8)
        res = auth_client(self.officer).patch(f"/api/club/lessons/{self.other.id}/", {"title": "改"}, format="json")
        self.assertEqual(res.status_code, 200)

    def test_profile_flag(self):
        self.assertTrue(auth_client(self.lead).get("/api/me/").data["courseLead"])
        self.assertFalse(auth_client(self.member).get("/api/me/").data["courseLead"])
        self.assertTrue(auth_client(self.officer).get("/api/me/").data["courseLead"])
