# NCUACG/club/tests.py
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.tests import auth_client, make_user
from club.models import Comment, Course, Work


class ClubApiTests(TestCase):
    def setUp(self):
        cache.clear()  # 瀏覽數節流記在 cache
        self.course = Course.objects.create(slug="test-course", name="測試社課", category="seiyuu", order=100)
        self.work = Work.objects.create(course=self.course, title="作品", external_url="https://example.com/a.mp4")
        self.alice = make_user("alice@example.test")
        self.bob = make_user("bob@example.test")
        self.officer = make_user("officer@example.test", is_admin=True)

    def test_courses_include_published_work_count(self):
        Work.objects.create(course=self.course, title="下架", external_url="https://example.com/b.mp4", is_published=False)
        res = APIClient().get("/api/club/courses/?category=seiyuu")
        course = next(c for c in res.data if c["id"] == "test-course")
        self.assertEqual(course["workCount"], 1)

    def test_works_require_course(self):
        self.assertEqual(APIClient().get("/api/club/works/").status_code, 400)

    def test_works_list_has_comment_count_not_comments(self):
        Comment.objects.create(work=self.work, user=self.alice, content="hi")
        res = APIClient().get("/api/club/works/?course=test-course")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data[0]["commentCount"], 1)
        self.assertNotIn("comments", res.data[0])

    def test_like_is_idempotent(self):
        client = auth_client(self.alice)
        for _ in range(2):
            res = client.post(f"/api/club/works/{self.work.id}/like/")
        self.assertEqual(res.data, {"likes": 1, "isLiked": True})
        res = client.delete(f"/api/club/works/{self.work.id}/like/")
        self.assertEqual(res.data, {"likes": 0, "isLiked": False})

    def test_like_requires_login(self):
        self.assertEqual(APIClient().post(f"/api/club/works/{self.work.id}/like/").status_code, 401)

    def test_view_count_is_throttled_per_viewer(self):
        client = APIClient()
        self.assertEqual(client.post(f"/api/club/works/{self.work.id}/view/").status_code, 200)
        self.assertEqual(client.post(f"/api/club/works/{self.work.id}/view/").status_code, 429)
        self.work.refresh_from_db()
        self.assertEqual(self.work.views, 1)

    def test_anyone_can_read_comments_but_posting_needs_login(self):
        url = f"/api/club/works/{self.work.id}/comments/"
        self.assertEqual(APIClient().get(url).status_code, 200)
        self.assertEqual(APIClient().post(url, {"content": "x"}, format="json").status_code, 401)
        res = auth_client(self.alice).post(url, {"content": "hello"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["canDelete"])

    def test_can_delete_flag(self):
        Comment.objects.create(work=self.work, user=self.alice, content="by alice")
        res = auth_client(self.bob).get(f"/api/club/works/{self.work.id}/comments/")
        self.assertFalse(res.data[0]["canDelete"])
        res = auth_client(self.officer).get(f"/api/club/works/{self.work.id}/comments/")
        self.assertTrue(res.data[0]["canDelete"])

    def test_delete_comment_permissions(self):
        comment = Comment.objects.create(work=self.work, user=self.alice, content="by alice")
        url = f"/api/club/comments/{comment.id}/"
        self.assertEqual(APIClient().delete(url).status_code, 401)
        self.assertEqual(auth_client(self.bob).delete(url).status_code, 403)
        self.assertEqual(auth_client(self.alice).delete(url).status_code, 204)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_officer_can_delete_any_comment(self):
        comment = Comment.objects.create(work=self.work, user=self.alice, content="by alice")
        res = auth_client(self.officer).delete(f"/api/club/comments/{comment.id}/")
        self.assertEqual(res.status_code, 204)
