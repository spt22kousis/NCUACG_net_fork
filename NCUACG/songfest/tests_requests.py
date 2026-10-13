# NCUACG/songfest/tests_requests.py
"""點歌：點舊曲、徵剪輯、+1、上限、截止、刪除、排歌台的點歌清單與採用數。"""
import datetime as dt

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.tests import auth_client, make_user
from songfest.models import Festival, FestivalStaff, SongRequest, Submission, Track

DAY = dt.timedelta(days=1)


class RequestTests(TestCase):
    def setUp(self):
        self.festival = Festival.objects.create(name="115上期末", date=timezone.localdate() + 30 * DAY, request_limit=2)
        self.alice = make_user("alice@example.test")
        self.bob = make_user("bob@example.test")
        self.staffer = make_user("staffer@example.test")
        FestivalStaff.objects.create(festival=self.festival, user=self.staffer, role="lead")
        self.old = Track.objects.create(dvd_code="D0713", song_source="おたくのビデオ", visual_source="おたくのビデオ",
                                        title="戦え!おたキング", editor="公式MTV", duration_seconds=220)
        # 同一首歌的另一個剪輯版本
        Track.objects.create(dvd_code="D9000", song_source="おたくのビデオ", visual_source="別的畫面",
                             title="戦え!おたキング", editor="別人", duration_seconds=230)

    def request(self, user, **data):
        return auth_client(user).post("/api/songfest/requests/", {"festival": self.festival.id, **data}, format="json")

    def listing(self, user=None):
        client = auth_client(user) if user else APIClient()
        return client.get(f"/api/songfest/requests/?festival={self.festival.id}").data

    def test_request_old_song_by_dvd_code(self):
        res = self.request(self.alice, dvdCode="d0713", note="想在下午二聽")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["created"])
        row = res.data["request"]
        self.assertEqual((row["kind"], row["dvdCode"], row["votes"], row["voted"]), ("old", "D0713", 1, True))
        self.assertEqual(res.data["festival"]["myCount"], 1)

    def test_same_song_becomes_plus_one(self):
        self.request(self.alice, dvdCode="D0713")
        # 另一個版本、或自己打字打成全形，都算同一首
        res = self.request(self.bob, songSource="おたくのビデオ", title="戦え！おたキング")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["created"])
        self.assertEqual(res.data["request"]["votes"], 2)
        self.assertEqual(res.data["festival"]["myCount"], 0)  # +1 不算在上限裡
        self.assertEqual(SongRequest.objects.count(), 1)

    def test_typed_song_that_is_in_library_links_to_track(self):
        res = self.request(self.alice, songSource="おたくのビデオ", title="戦え!おたキング")
        self.assertEqual(res.data["request"]["kind"], "old")
        self.assertEqual(res.data["request"]["dvdCode"], "D9000")  # 最新的版本

    def test_wish_for_song_nobody_cut(self):
        res = self.request(self.alice, songSource="ぼっち・ざ・ろっく！", title="星座になれたら", link="https://youtu.be/x")
        self.assertEqual(res.data["request"]["kind"], "wish")
        wishes = APIClient().get("/api/songfest/requests/wishes/").data
        self.assertEqual([(w["title"], w["votes"]) for w in wishes], [("星座になれたら", 1)])

    def test_wish_disappears_once_someone_reports_it(self):
        self.request(self.alice, songSource="作品X", title="想聽的歌")
        Submission.objects.create(festival=self.festival, editor_name="bob", song_source="作品X", visual_source="作品X",
                                  title="想聽的歌")
        self.assertEqual(self.listing()["requests"][0]["submitted"], True)
        self.assertEqual(APIClient().get("/api/songfest/requests/wishes/").data, [])

    def test_wish_votes_merge_across_festivals(self):
        later = Festival.objects.create(name="115下期初", date=timezone.localdate() + 120 * DAY)
        self.request(self.alice, songSource="作品X", title="想聽的歌")
        auth_client(self.bob).post("/api/songfest/requests/", {"festival": later.id, "songSource": "作品X", "title": "想聽的歌"}, format="json")
        auth_client(self.alice).post("/api/songfest/requests/", {"festival": later.id, "songSource": "作品X", "title": "想聽的歌"}, format="json")
        wishes = APIClient().get("/api/songfest/requests/wishes/").data
        self.assertEqual((wishes[0]["votes"], wishes[0]["lastFestival"]), (2, "115下期初"))

    def test_limit_per_person(self):
        self.request(self.alice, dvdCode="D0713")
        self.request(self.alice, songSource="作品X", title="一")
        res = self.request(self.alice, songSource="作品X", title="二")
        self.assertEqual(res.status_code, 400)
        self.assertIn("最多點 2 首", res.data["detail"])

    def test_closed_after_deadline_and_for_ktv(self):
        self.festival.request_deadline = timezone.now() - DAY
        self.festival.save()
        self.assertEqual(self.request(self.alice, dvdCode="D0713").status_code, 400)
        self.assertFalse(self.listing()["festival"]["open"])

        ktv = Festival.objects.create(name="KTV", date=timezone.localdate() + 5 * DAY, kind="ktv")
        self.assertFalse(ktv.is_request_open())
        self.festival.request_deadline = None
        self.festival.date = timezone.localdate()  # 活動當天就不能點了
        self.festival.save()
        self.assertFalse(self.festival.is_request_open())

    def test_requires_login_and_valid_input(self):
        self.assertEqual(APIClient().post("/api/songfest/requests/", {"dvdCode": "D0713"}, format="json").status_code, 401)
        self.assertEqual(self.request(self.alice, dvdCode="D9999").status_code, 400)
        self.assertEqual(self.request(self.alice, title="只有曲名").status_code, 400)

    def test_default_festival_is_the_active_one(self):
        res = auth_client(self.alice).post("/api/songfest/requests/", {"dvdCode": "D0713"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(APIClient().get("/api/songfest/requests/").data["festival"]["id"], self.festival.id)

    def test_vote_and_unvote(self):
        req_id = self.request(self.alice, dvdCode="D0713").data["request"]["id"]
        url = f"/api/songfest/requests/{req_id}/vote/"
        self.assertEqual(auth_client(self.bob).post(url).data, {"votes": 2, "voted": True})
        self.assertEqual(auth_client(self.bob).post(url).data["votes"], 2)  # 重複按不會多算
        self.assertEqual(auth_client(self.bob).delete(url).data, {"votes": 1, "voted": False})
        self.assertEqual(auth_client(self.alice).delete(url).status_code, 400)  # 點歌的人不能收回

    def test_list_sorted_by_votes_with_my_vote(self):
        first = self.request(self.alice, songSource="作品X", title="一票").data["request"]["id"]
        second = self.request(self.alice, dvdCode="D0713").data["request"]["id"]
        auth_client(self.bob).post(f"/api/songfest/requests/{second}/vote/")
        rows = self.listing(self.bob)["requests"]
        self.assertEqual([r["id"] for r in rows], [second, first])
        self.assertEqual([r["voted"] for r in rows], [True, False])
        self.assertEqual(rows[0]["requestedBy"], "alice")
        self.assertEqual(self.listing()["requests"][0]["recentPlayCount"], 0)

    def test_delete_rules(self):
        req_id = self.request(self.alice, dvdCode="D0713").data["request"]["id"]
        url = f"/api/songfest/requests/{req_id}/"
        self.assertEqual(auth_client(self.bob).delete(url).status_code, 403)
        auth_client(self.bob).post(f"/api/songfest/requests/{req_id}/vote/")
        self.assertEqual(auth_client(self.alice).delete(url).status_code, 400)  # 已經有人 +1
        self.assertEqual(auth_client(self.staffer).delete(url).status_code, 204)  # 排歌組可以刪

    def test_setlist_board_shows_requests_and_adoption(self):
        self.request(self.alice, dvdCode="D0713")
        self.request(self.bob, songSource="作品X", title="徵剪輯")
        client = auth_client(self.staffer)
        board = client.get(f"/api/songfest/festivals/{self.festival.id}/setlist/").data
        self.assertEqual(board["requestStats"], {"adopted": 0, "total": 2})
        session = next(s for s in board["sessions"] if s["name"] == "上午場")
        client.post(f"/api/songfest/setlist/sessions/{session['id']}/entries/", {"kind": "old", "dvdCode": "D9000"}, format="json")

        board = client.get(f"/api/songfest/festivals/{self.festival.id}/setlist/").data
        self.assertEqual(board["requestStats"]["adopted"], 1)  # 排了另一個版本也算採用
        entry = next(s for s in board["sessions"] if s["name"] == "上午場")["entries"][0]
        self.assertEqual(entry["requestVotes"], 1)
        old = next(r for r in board["requests"] if r["kind"] == "old")
        self.assertEqual(old["scheduledIn"], ["上午場"])
        # 歌單還沒公布前，一般社員看不到排在哪一場
        self.assertEqual(self.listing(self.alice)["requests"][0]["scheduledIn"], [])
