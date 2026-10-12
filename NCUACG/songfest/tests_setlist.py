# NCUACG/songfest/tests_setlist.py
"""排歌台：時段、時刻表、提醒、一鍵初排、匯出、公布、寫入播放紀錄、收進歌單。"""
import datetime as dt

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.tests import auth_client, make_user
from songfest.models import Festival, FestivalStaff, Play, Session, SetlistEntry, Submission, Track

DAY = dt.timedelta(days=1)


class SetlistTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        self.previous = Festival.objects.create(name="上一場", date=timezone.localdate() - 60 * DAY)
        self.festival = Festival.objects.create(
            name="115上期末", date=timezone.localdate() + 10 * DAY, partner_limit=2,
            report_deadline=now - 5 * DAY, withdraw_deadline=now + DAY, upload_deadline=now + 2 * DAY,
        )
        self.staffer = make_user("staffer@example.test")
        FestivalStaff.objects.create(festival=self.festival, user=self.staffer, role="lead")
        self.client = auth_client(self.staffer)

        self.otaking = Track.objects.create(dvd_code="D0713", song_source="おたくのビデオ", visual_source="おたくのビデオ",
                                            title="戦え!おたキング", editor="公式MTV", duration_seconds=220)
        self.recent = Track.objects.create(dvd_code="D13720", song_source="作品A", visual_source="作品A",
                                           title="上一場的歌", editor="x", duration_seconds=230)
        self.near = Track.objects.create(dvd_code="D13719", song_source="作品B", visual_source="作品B",
                                         title="長度接近", editor="y", duration_seconds=245)
        Play.objects.create(festival=self.previous, position=1, song_source="作品A", visual_source="作品A", title="上一場的歌")

        def sub(editor, title, duration=240, **extra):
            return Submission.objects.create(
                festival=self.festival, editor_name=editor, song_source=f"作品{title}", visual_source=f"作品{title}",
                title=title, duration_seconds=duration, file_link="https://drive.example/x",
                uploaded_at=now - DAY, **extra,
            )

        self.alice_songs = [sub("影蒙", f"影蒙{i}") for i in range(4)]
        self.bob1 = sub("監督", "監督1", 300)
        self.bob2 = sub("監督", "監督2", 280, chain_with=self.bob1)
        self.guest = sub("よるば", "亂入入選", 200, source="guest")
        self.guest_out = sub("よるば", "亂入未入選", 200, source="guest", is_rejected=True)
        self.partner = sub("健行A", "社外正選", 250, source="partner")
        self.backup = sub("健行B", "社外備曲", 250, source="partner", is_backup=True)
        self.withdrawn = sub("影蒙", "窗掉的", 240, withdrawn_at=now - DAY)

    def board(self):
        res = self.client.get(f"/api/songfest/festivals/{self.festival.id}/setlist/")
        self.assertEqual(res.status_code, 200)
        return res.data

    def session(self, name):
        return Session.objects.get(festival=self.festival, name=name)

    def add(self, session_name, **data):
        res = self.client.post(f"/api/songfest/setlist/sessions/{self.session(session_name).id}/entries/", data, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        return res.data

    def find(self, board, session_name):
        return next(s for s in board["sessions"] if s["name"] == session_name)


class BoardTests(SetlistTestCase):
    def test_default_sessions(self):
        data = self.board()
        self.assertEqual([s["name"] for s in data["sessions"]], ["測試曲", "上午場", "下午一", "下午二"])
        targets = {s["name"]: s["targetSeconds"] for s in data["sessions"]}
        self.assertEqual(targets, {"測試曲": None, "上午場": 7080, "下午一": 6480, "下午二": 7080})
        self.assertEqual(self.find(data, "測試曲")["rounds"], 2)

    def test_only_staff(self):
        self.assertEqual(auth_client(make_user()).get(f"/api/songfest/festivals/{self.festival.id}/setlist/").status_code, 403)

    def test_pool_and_global_warnings(self):
        data = self.board()
        titles = {p["title"] for p in data["pool"]}
        # 窗歌、亂入未入選不在候選；備曲在候選但另外標示
        self.assertNotIn("窗掉的", titles)
        self.assertNotIn("亂入未入選", titles)
        self.assertIn("社外備曲", titles)
        self.assertTrue(any("還有 8 首新曲沒排" in w for w in data["warnings"]))
        self.assertTrue(any("可以補 1 首備曲" in w for w in data["warnings"]))

    def test_timetable_counts_one_second_per_song(self):
        self.board()
        self.add("上午場", kind="old", dvdCode="D0713")
        data = self.add("上午場", kind="custom", customType="cm", title="CM1", duration=330)
        morning = self.find(data, "上午場")
        self.assertEqual([e["title"] for e in morning["entries"]], ["戦え!おたキング", "CM1"])
        self.assertEqual(morning["entries"][0]["endsAt"], "10:03:41")  # 220 秒 + 1 秒誤差
        self.assertEqual(morning["entries"][1]["endsAt"], "10:09:12")
        self.assertEqual((morning["totalSeconds"], morning["errorSeconds"]), (550, 2))
        self.assertEqual(morning["speechAt"], "09:59:00")
        self.assertEqual(morning["latestEndAt"], "10:13:12")  # 預計結束 + 4 分鐘
        self.assertTrue(morning["under"])

    def test_over_time_suggests_earlier_start(self):
        self.board()
        data = self.add("上午場", kind="custom", customType="other", title="很長", duration=7300)
        morning = self.find(data, "上午場")
        self.assertTrue(morning["over"])
        self.assertEqual(morning["suggestedStart"], "09:58:19")  # 12:00 - (7300 + 1)
        self.assertIn("提早到 09:58:19", morning["warnings"][0])

    def test_within_two_minutes_is_fine(self):
        self.board()
        data = self.add("上午場", kind="custom", customType="other", title="剛好", duration=7200)  # 2:00:00
        morning = self.find(data, "上午場")
        self.assertFalse(morning["over"])
        self.assertEqual(morning["warnings"], [])

    def test_test_session_rounds(self):
        self.board()
        data = self.add("測試曲", kind="old", dvdCode="D0713")
        test = self.find(data, "測試曲")
        self.assertEqual(test["endAt"], "09:52:22")  # (220 + 1) × 2 輪

    def test_entry_warnings(self):
        self.board()
        self.add("上午場", kind="old", dvdCode="D13720")
        self.add("下午一", kind="old", dvdCode="D13720")
        data = self.add("下午二", kind="new", submissionId=self.withdrawn.id)
        morning = self.find(data, "上午場")["entries"][0]["warnings"]
        self.assertIn("上一場播過", morning)
        self.assertTrue(any(w.startswith("重複") for w in morning))
        self.assertIn("已窗歌或退件，請換一首舊曲補上", self.find(data, "下午二")["entries"][0]["warnings"])

    def test_new_song_only_once(self):
        self.board()
        self.add("上午場", kind="new", submissionId=self.guest.id)
        res = self.client.post(f"/api/songfest/setlist/sessions/{self.session('下午一').id}/entries/",
                               {"kind": "new", "submissionId": self.guest.id}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_unknown_dvd_code(self):
        self.board()
        res = self.client.post(f"/api/songfest/setlist/sessions/{self.session('上午場').id}/entries/",
                               {"kind": "old", "dvdCode": "D99999"}, format="json")
        self.assertEqual(res.status_code, 400)


class EditTests(SetlistTestCase):
    def test_move_between_sessions_and_reorder(self):
        self.board()
        self.add("上午場", kind="old", dvdCode="D0713")
        data = self.add("上午場", kind="old", dvdCode="D13719")
        first, second = self.find(data, "上午場")["entries"]
        res = self.client.patch(f"/api/songfest/setlist/entries/{second['id']}/", {"position": 1}, format="json")
        self.assertEqual([e["dvdCode"] for e in self.find(res.data, "上午場")["entries"]], ["D13719", "D0713"])

        res = self.client.patch(f"/api/songfest/setlist/entries/{first['id']}/",
                                {"sessionId": self.session("下午二").id}, format="json")
        self.assertEqual([e["position"] for e in self.find(res.data, "上午場")["entries"]], [1])
        self.assertEqual(self.find(res.data, "下午二")["entries"][0]["dvdCode"], "D0713")

    def test_replace_withdrawn_with_old_song(self):
        self.board()
        data = self.add("上午場", kind="new", submissionId=self.withdrawn.id)
        entry = self.find(data, "上午場")["entries"][0]
        suggestions = self.client.get(f"/api/songfest/festivals/{self.festival.id}/setlist/suggest/", {"seconds": 240}).data
        codes = [t["dvdCode"] for t in suggestions]
        self.assertEqual(codes[0], "D13719")  # 245 秒最接近
        self.assertNotIn("D13720", codes)     # 上一場播過
        res = self.client.patch(f"/api/songfest/setlist/entries/{entry['id']}/", {"dvdCode": "D13719"}, format="json")
        row = self.find(res.data, "上午場")["entries"][0]
        self.assertEqual((row["kind"], row["dvdCode"], row["position"]), ("old", "D13719", 1))

    def test_heat_note_and_delete(self):
        self.board()
        data = self.add("上午場", kind="old", dvdCode="D0713")
        entry = self.find(data, "上午場")["entries"][0]
        res = self.client.patch(f"/api/songfest/setlist/entries/{entry['id']}/", {"heat": 5, "note": "壓軸"}, format="json")
        row = self.find(res.data, "上午場")["entries"][0]
        self.assertEqual((row["heat"], row["note"]), (5, "壓軸"))
        res = self.client.delete(f"/api/songfest/setlist/entries/{entry['id']}/")
        self.assertEqual(self.find(res.data, "上午場")["entries"], [])

    def test_session_settings(self):
        self.board()
        res = self.client.patch(f"/api/songfest/setlist/sessions/{self.session('下午一').id}/",
                                {"startTime": "13:05", "ownerId": self.staffer.id}, format="json")
        afternoon = self.find(res.data, "下午一")
        self.assertEqual((afternoon["startTime"], afternoon["ownerName"]), ("13:05", self.staffer.name))


class AutoDistributeTests(SetlistTestCase):
    def test_places_every_new_song_and_spreads_editors(self):
        self.board()
        res = self.client.post(f"/api/songfest/festivals/{self.festival.id}/setlist/auto/")
        self.assertEqual(res.data["placed"], 8)  # 影蒙 4 + 監督 2 + 亂入入選 1 + 社外正選 1
        self.assertEqual([p["title"] for p in res.data["pool"]], ["社外備曲"])
        for session in res.data["sessions"]:
            names = [e["editor"] for e in session["entries"]]
            self.assertLessEqual(names.count("影蒙"), 2)  # 4 首分到 3 場，每場最多 2 首
        # 連曲排在一起
        for session in res.data["sessions"]:
            titles = [e["title"] for e in session["entries"]]
            if "監督1" in titles:
                self.assertEqual(abs(titles.index("監督1") - titles.index("監督2")), 1)
        self.assertEqual(self.find(res.data, "測試曲")["entries"], [])

    def test_run_twice_does_not_duplicate(self):
        self.board()
        self.client.post(f"/api/songfest/festivals/{self.festival.id}/setlist/auto/")
        res = self.client.post(f"/api/songfest/festivals/{self.festival.id}/setlist/auto/")
        self.assertEqual(res.data["placed"], 0)


class ExportAndPublishTests(SetlistTestCase):
    def setUp(self):
        super().setUp()
        self.board()
        self.add("測試曲", kind="old", dvdCode="D0713")
        self.add("上午場", kind="custom", customType="cm", title="CM1", duration=300)
        self.add("上午場", kind="new", submissionId=self.alice_songs[0].id)
        self.add("上午場", kind="new", submissionId=self.withdrawn.id)
        self.add("下午二", kind="new", submissionId=self.guest.id)
        self.add("下午二", kind="custom", customType="credits", title="春日影", source="BanG Dream! It's MyGO!!!!!", duration=264)
        Submission.objects.filter(pk=self.alice_songs[0].pk).update(
            five_sec=True, five_sec_link="https://drive.example/5", five_sec_uploaded_at=timezone.now())

    def export(self, kind):
        res = self.client.get(f"/api/songfest/festivals/{self.festival.id}/setlist/export/", {"type": kind})
        self.assertEqual(res.status_code, 200)
        return res.content.decode("utf-8")

    def test_exports(self):
        public = self.export("public")
        self.assertIn("影蒙0", public)
        self.assertNotIn("窗掉的", public)
        self.assertIn("亂入", public)
        order = self.export("order")
        self.assertIn("[作品影蒙0][影蒙0][影蒙]", order)  # 投稿規則的檔名格式
        self.assertIn("D0713", order)
        credits = self.export("credits")
        self.assertIn("【新曲剪輯】\n影蒙", credits)
        self.assertIn("【亂入曲】\nよるば", credits)
        self.assertIn("影蒙：1 段（5 秒）", credits)
        self.assertIn("影蒙0", self.export("workspace"))

    def test_publish(self):
        url = f"/api/songfest/festivals/{self.festival.id}/"
        self.assertEqual(APIClient().get(url).data["sessions"], [])
        self.client.post(f"/api/songfest/festivals/{self.festival.id}/setlist/publish/", {"public": True}, format="json")
        sessions = APIClient().get(url).data["sessions"]
        morning = next(s for s in sessions if s["name"] == "上午場")
        self.assertEqual([(e["title"], e["label"]) for e in morning["entries"]], [("CM1", "CM"), ("影蒙0", "新曲")])

    def test_write_plays(self):
        res = self.client.post(f"/api/songfest/festivals/{self.festival.id}/setlist/write-plays/")
        self.assertEqual(res.data["written"], 4)  # 測試曲、影蒙0、亂入、結尾影片；不含 CM 與窗掉的
        plays = list(Play.objects.filter(festival=self.festival))
        self.assertEqual(plays[0].track, self.otaking)
        self.assertEqual(plays[-1].visual_source, Play.CREDITS_VISUAL)
        # 重寫一次不會重複
        self.client.post(f"/api/songfest/festivals/{self.festival.id}/setlist/write-plays/")
        self.assertEqual(Play.objects.filter(festival=self.festival).count(), 4)


class LibraryTests(SetlistTestCase):
    def setUp(self):
        super().setUp()
        self.board()
        self.member = make_user("member@example.test")
        Submission.objects.filter(pk=self.alice_songs[0].pk).update(submitter=self.member)
        self.add("上午場", kind="new", submissionId=self.alice_songs[0].id)
        self.add("上午場", kind="new", submissionId=self.guest.id)
        Submission.objects.filter(pk=self.guest.pk).update(library_consent=True)

    def test_member_consent_opens_after_festival(self):
        member = auth_client(self.member)
        url = f"/api/songfest/submissions/{self.alice_songs[0].id}/library-consent/"
        self.assertEqual(member.get("/api/songfest/library-consent/").data, [])
        self.assertEqual(member.post(url, {"consent": True}, format="json").status_code, 400)

        Festival.objects.filter(pk=self.festival.pk).update(date=timezone.localdate())
        self.assertEqual(len(member.get("/api/songfest/library-consent/").data), 1)
        self.assertTrue(member.post(url, {"consent": True}, format="json").data["consent"])

    def test_add_to_library_assigns_next_dvd_codes(self):
        Submission.objects.filter(pk=self.alice_songs[0].pk).update(library_consent=True)
        res = self.client.post(f"/api/songfest/festivals/{self.festival.id}/library/add/",
                               {"submissionIds": [self.alice_songs[0].id, self.guest.id]}, format="json")
        # 最大的是 D13720（第 137 片第 20 首），下一首換到第 138 片
        self.assertEqual(res.data["added"], ["D13801", "D13802"])
        track = Track.objects.get(dvd_code="D13801")
        self.assertEqual((track.title, track.editor), ("影蒙0", "影蒙"))
        # 再按一次不會重複收
        res = self.client.post(f"/api/songfest/festivals/{self.festival.id}/library/add/",
                               {"submissionIds": [self.alice_songs[0].id]}, format="json")
        self.assertEqual(res.data["added"], [])
        csv_text = self.client.get(f"/api/songfest/festivals/{self.festival.id}/library/export/").content.decode("utf-8")
        self.assertIn("D13801", csv_text)

    def test_without_consent_is_not_added(self):
        res = self.client.post(f"/api/songfest/festivals/{self.festival.id}/library/add/",
                               {"submissionIds": [self.alice_songs[0].id]}, format="json")
        self.assertEqual(res.data["added"], [])
