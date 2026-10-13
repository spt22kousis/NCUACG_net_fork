# NCUACG/club/tests_photos.py
import datetime as dt
import shutil
import tempfile
from io import BytesIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.tests import auth_client, make_user
from club.models import Course, CourseLead, Lesson, Photo, Work
from songfest.models import Festival, FestivalStaff

TEMP_ROOT = tempfile.mkdtemp()


def image_file(name="photo.jpg", size=(3000, 2000), fmt="JPEG", exif_gps=False):
    buffer = BytesIO()
    image = Image.new("RGB", size, (200, 100, 50))
    kwargs = {}
    if exif_gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (24.0, 58.0, 0.0)}  # GPSInfo
        kwargs["exif"] = exif
    image.save(buffer, format=fmt, **kwargs)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=f"{TEMP_ROOT}/media", PRIVATE_MEDIA_ROOT=f"{TEMP_ROOT}/private")
class PhotoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_ROOT, ignore_errors=True)

    def setUp(self):
        self.lead = make_user("lead@example.test")
        self.staff = make_user("staff@example.test")
        self.member = make_user("member@example.test")
        self.officer = make_user("officer@example.test", is_staff=True)
        CourseLead.objects.create(category="railway", user=self.lead)
        self.festival = Festival.objects.create(name="115上期末", date=dt.date(2026, 12, 20))
        FestivalStaff.objects.create(festival=self.festival, user=self.staff, role="lead")
        self.lesson = Lesson.objects.create(
            category="railway", title="高鐵與捷運", start_time=timezone.make_aware(dt.datetime(2026, 10, 19, 18)),
        )

    def upload(self, user, **data):
        return auth_client(user).post("/api/club/photos/", {"image": image_file(), **data}, format="multipart")

    def test_lead_uploads_lesson_photo_resized_with_thumbnail(self):
        res = self.upload(self.lead, kind="lesson", category="railway", lesson=self.lesson.id)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["takenOn"], "2026-10-19")  # 沒填日期就用那堂課的日期
        self.assertEqual(res.data["groupLabel"], "鐵道社課")
        self.assertEqual((res.data["width"], res.data["height"]), (1920, 1280))
        photo = Photo.objects.get()
        with photo.thumbnail.open("rb") as f:
            self.assertLessEqual(max(Image.open(f).size), 480)

    def test_gps_exif_is_removed(self):
        res = auth_client(self.lead).post(
            "/api/club/photos/", {"image": image_file(exif_gps=True), "kind": "lesson", "category": "railway"},
            format="multipart",
        )
        self.assertEqual(res.status_code, 201, res.data)
        with Photo.objects.get().image.open("rb") as f:
            self.assertNotIn(0x8825, Image.open(f).getexif())

    def test_who_can_upload_what(self):
        self.assertEqual(self.upload(self.lead, kind="lesson", category="art").status_code, 400)
        self.assertEqual(self.upload(self.lead, kind="songfest", festival=self.festival.id).status_code, 400)
        self.assertEqual(self.upload(self.staff, kind="songfest", festival=self.festival.id).status_code, 201)
        self.assertEqual(self.upload(self.staff, kind="daily", topic="社遊").status_code, 400)
        self.assertEqual(self.upload(self.officer, kind="daily", topic="社遊").status_code, 201)
        self.assertEqual(self.upload(self.member, kind="daily", topic="社遊").status_code, 403)

    def test_required_fields_per_kind(self):
        self.assertEqual(self.upload(self.officer, kind="lesson").status_code, 400)
        self.assertEqual(self.upload(self.officer, kind="songfest").status_code, 400)
        self.assertEqual(self.upload(self.officer, kind="daily", topic=" ").status_code, 400)
        res = self.upload(self.officer, kind="lesson", category="art", lesson=self.lesson.id)
        self.assertEqual(res.status_code, 400)  # 那堂是鐵道的

    def test_not_an_image(self):
        res = auth_client(self.lead).post(
            "/api/club/photos/",
            {"image": SimpleUploadedFile("x.jpg", b"not an image"), "kind": "lesson", "category": "railway"},
            format="multipart",
        )
        self.assertEqual(res.status_code, 400)

    def test_list_needs_login_and_filters(self):
        self.upload(self.lead, kind="lesson", category="railway", lesson=self.lesson.id)
        self.upload(self.staff, kind="songfest", festival=self.festival.id)
        self.upload(self.officer, kind="daily", topic="社遊")
        self.assertEqual(APIClient().get("/api/club/photos/").status_code, 401)

        client = auth_client(self.member)
        res = client.get("/api/club/photos/")
        self.assertEqual(res.data["total"], 3)
        self.assertIsNone(res.data["upload"])
        self.assertEqual(res.data["topics"], ["社遊"])
        self.assertFalse(any(p["canEdit"] for p in res.data["photos"]))
        self.assertEqual(client.get(f"/api/club/photos/?lesson={self.lesson.id}").data["total"], 1)
        self.assertEqual(client.get(f"/api/club/photos/?festival={self.festival.id}").data["total"], 1)
        self.assertEqual(client.get("/api/club/photos/?kind=daily&topic=社遊").data["total"], 1)

        res = auth_client(self.staff).get("/api/club/photos/")
        self.assertEqual([f["name"] for f in res.data["upload"]["festivals"]], ["115上期末"])
        self.assertFalse(res.data["upload"]["daily"])

    def test_signed_file_url(self):
        res = self.upload(self.lead, kind="lesson", category="railway")
        client = APIClient()  # <img> 不會帶登入資訊，靠網址上的簽章
        file_res = client.get(res.data["thumbUrl"])
        self.assertEqual(file_res.status_code, 200)
        self.assertEqual(file_res["Content-Type"], "image/jpeg")
        self.assertIn("private", file_res["Cache-Control"])

        self.assertEqual(client.get(res.data["url"][:-3] + "xx/").status_code, 404)  # 改過的簽章
        with mock.patch("club.photo_views.time.time", return_value=timezone.now().timestamp() + 3 * 86400):
            self.assertEqual(client.get(res.data["url"]).status_code, 404)  # 過期

    def test_edit_and_delete_removes_files(self):
        photo_id = self.upload(self.lead, kind="lesson", category="railway").data["id"]
        url = f"/api/club/photos/{photo_id}/"
        self.assertEqual(auth_client(self.member).patch(url, {"caption": "x"}, format="json").status_code, 403)
        res = auth_client(self.lead).patch(url, {"caption": "大家在看地圖", "lesson": self.lesson.id}, format="json")
        self.assertEqual(res.data["caption"], "大家在看地圖")
        self.assertEqual(res.data["lesson"]["id"], self.lesson.id)
        # 負責人不能把照片改成日常
        self.assertEqual(auth_client(self.lead).patch(url, {"kind": "daily", "topic": "社遊"}, format="json").status_code, 400)

        photo = Photo.objects.get()
        storage, name = photo.image.storage, photo.image.name
        self.assertTrue(storage.exists(name))
        self.assertEqual(auth_client(self.lead).delete(url).status_code, 204)
        self.assertFalse(storage.exists(name))

    def test_officer_moves_photo_to_daily_and_lesson_fields_are_cleared(self):
        photo_id = self.upload(self.lead, kind="lesson", category="railway", lesson=self.lesson.id).data["id"]
        res = auth_client(self.officer).patch(
            f"/api/club/photos/{photo_id}/", {"kind": "daily", "topic": "社博"}, format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        photo = Photo.objects.get()
        self.assertEqual((photo.kind, photo.topic, photo.category, photo.lesson), ("daily", "社博", "", None))


@override_settings(MEDIA_ROOT=f"{TEMP_ROOT}/media", PRIVATE_MEDIA_ROOT=f"{TEMP_ROOT}/private")
class WorkManageTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_ROOT, ignore_errors=True)

    def setUp(self):
        self.lead = make_user("lead@example.test")
        self.member = make_user("member@example.test")
        CourseLead.objects.create(category="railway", user=self.lead)
        self.course = Course.objects.create(slug="railway-115a", name="115上", category="railway")
        self.other = Course.objects.create(slug="art-115a", name="115上", category="art")
        self.lesson = Lesson.objects.create(category="railway", title="高鐵與捷運", start_time=timezone.now())

    def post(self, user, **data):
        return auth_client(user).post("/api/club/works/manage/", data, format="multipart")

    def test_lead_uploads_image_work_with_thumbnail_and_lesson(self):
        res = self.post(self.lead, course="railway-115a", title="路線圖", author="lead", type="image",
                        file=image_file(), lesson=self.lesson.id)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNotNone(res.data["thumbnail"])
        self.assertEqual(res.data["lesson"]["title"], "高鐵與捷運")
        public = APIClient().get(f"/api/club/works/?lesson={self.lesson.id}").data
        self.assertEqual([w["title"] for w in public], ["路線圖"])

    def test_youtube_link_is_embedded(self):
        res = self.post(self.lead, course="railway-115a", title="影片", type="video",
                        externalUrl="https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["embedUrl"], "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")
        self.assertIn("img.youtube.com/vi/dQw4w9WgXcQ", res.data["thumbnail"])

    def test_video_file_rules(self):
        res = self.post(self.lead, course="railway-115a", title="影片", type="video",
                        file=SimpleUploadedFile("a.exe", b"x"))
        self.assertEqual(res.status_code, 400)
        res = self.post(self.lead, course="railway-115a", title="影片", type="video",
                        file=SimpleUploadedFile("a.mp4", b"x" * 10, content_type="video/mp4"))
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["url"].endswith(".mp4"))

    def test_needs_file_or_link(self):
        self.assertEqual(self.post(self.lead, course="railway-115a", title="空", type="image").status_code, 400)

    def test_only_own_categories(self):
        res = self.post(self.lead, course="art-115a", title="x", type="video", externalUrl="https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(auth_client(self.member).get("/api/club/works/manage/").status_code, 403)
        work = Work.objects.create(course=self.other, title="別人的", external_url="https://example.com/a.mp4")
        res = auth_client(self.lead).patch(f"/api/club/works/manage/{work.id}/", {"title": "x"}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_manage_list_edit_and_delete(self):
        work = Work.objects.create(course=self.course, title="舊", external_url="https://example.com/a.mp4",
                                   is_published=False)
        data = auth_client(self.lead).get("/api/club/works/manage/").data
        self.assertEqual([w["title"] for w in data["works"]], ["舊"])  # 下架的也看得到
        self.assertEqual([c["id"] for c in data["courses"]], ["railway-115a"])
        url = f"/api/club/works/manage/{work.id}/"
        res = auth_client(self.lead).patch(url, {"title": "新", "isPublished": True}, format="json")
        self.assertEqual((res.data["title"], res.data["isPublished"]), ("新", True))
        self.assertEqual(auth_client(self.lead).delete(url).status_code, 204)

    def test_lead_creates_course(self):
        res = auth_client(self.lead).post("/api/club/courses/manage/", {"category": "railway", "name": "115下"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["id"].startswith("railway-"))
        res = auth_client(self.lead).post("/api/club/courses/manage/", {"category": "art", "name": "115下"}, format="json")
        self.assertEqual(res.status_code, 403)
