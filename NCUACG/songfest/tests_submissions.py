# NCUACG/songfest/tests_submissions.py
"""新曲投稿：對照「歌謠祭曲目投稿規則」逐條測。"""
import datetime as dt

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.tests import auth_client, make_user
from songfest.models import Festival, FestivalStaff, Play, Submission
from songfest.tests import XLSX, workbook_bytes

DAY = dt.timedelta(days=1)


def song(**overrides):
    data = {
        "songSource": "ヤニねこ",
        "visualSource": "ヤニねこ",
        "title": "なんもねえ",
        "artist": "忘れらんねえよ",
        "attributes": "喜劇",
        "songLink": "https://example.com/song",
        "fiveSec": True,
    }
    data.update(overrides)
    return data


class SubmissionTestCase(TestCase):
    def setUp(self):
        now = timezone.now()
        self.festival = Festival.objects.create(
            name="115上期末", date=timezone.localdate() + 20 * DAY,
            report_deadline=now + 5 * DAY, withdraw_deadline=now + 10 * DAY, upload_deadline=now + 12 * DAY,
            guest_deadline=now + 8 * DAY, partner_limit=2,
        )
        self.alice = make_user("alice@example.test")
        self.bob = make_user("bob@example.test")
        self.staffer = make_user("staffer@example.test")
        FestivalStaff.objects.create(festival=self.festival, user=self.staffer, role="lead")
        self.officer = make_user("officer@example.test", is_staff=True)

    def set_deadlines(self, **offsets):
        """把截止時間改成「現在 ± 幾天」，例如 report=-1 表示報曲已經截止一天"""
        now = timezone.now()
        names = {"report": "report_deadline", "withdraw": "withdraw_deadline", "upload": "upload_deadline",
                 "guest": "guest_deadline"}
        Festival.objects.filter(pk=self.festival.pk).update(
            **{names[k]: now + v * DAY for k, v in offsets.items()}
        )
        self.festival.refresh_from_db()

    def report(self, user, **overrides):
        return auth_client(user).post(f"/api/songfest/festivals/{self.festival.id}/submissions/", song(**overrides), format="json")

    def patch(self, user, sub_id, data):
        return auth_client(user).patch(f"/api/songfest/submissions/{sub_id}/", data, format="json")


class ReportTests(SubmissionTestCase):
    def test_active_festival_and_viewer(self):
        res = APIClient().get("/api/songfest/active/")
        self.assertEqual(res.data["festival"]["id"], self.festival.id)
        self.assertTrue(res.data["festival"]["reportOpen"]["member"])
        self.assertIsNone(res.data["viewer"])
        res = auth_client(self.staffer).get("/api/songfest/active/")
        self.assertEqual(res.data["viewer"], {"banReason": None, "isStaff": True})

    def test_report_uses_account_name_and_requires_fields(self):
        res = self.report(self.alice)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["editorName"], "alice")
        self.assertEqual(res.data["status"], "reported")
        res = self.report(self.alice, title="別首", attributes="", songLink="")
        self.assertEqual(res.status_code, 400)
        self.assertNotIn("attributes", res.data)  # 畫面屬性不必填
        self.assertIn("songLink", res.data)
        self.assertEqual(self.report(self.alice, title="別首", attributes="").status_code, 201)

    def test_two_people_cannot_report_the_same_song(self):
        self.report(self.alice, songSource="とある科学の超電磁砲", title="only my railgun")
        # 全形、大小寫、空白不同也算同一首
        res = self.report(self.bob, songSource="とある科学の超電磁砲", title="ＯＮＬＹ　ＭＹ　ＲＡＩＬＧＵＮ")
        self.assertEqual(res.status_code, 400)
        self.assertIn("alice", res.data["title"][0])
        # 同曲名但歌曲出處不同，是不同首歌
        self.assertEqual(self.report(self.bob, songSource="別的作品", title="only my railgun").status_code, 201)

    def test_member_keeps_priority_over_partner(self):
        """社外投稿規則：社內跟社外撞曲時，優先保留社內作品"""
        self.report(self.bob, source="partner")  # 社外先報
        self.assertEqual(self.report(self.alice).status_code, 201)  # 社內照樣可以報
        res = self.report(make_user("carol@example.test"), source="partner")
        self.assertEqual(res.status_code, 400)  # 社外不能報社內已經報過的歌
        self.assertIn("優先保留社內", res.data["title"][0])

        rows = {r["source"]: r for r in auth_client(self.staffer).get(
            f"/api/songfest/festivals/{self.festival.id}/manage/").data["submissions"]}
        self.assertIn("優先保留社內", rows["partner"]["warnings"][0]["message"])

    def test_withdrawn_song_can_be_reported_again(self):
        self.report(self.alice)
        self.set_deadlines(report=-1)
        sub = Submission.objects.get()
        auth_client(self.alice).post(f"/api/songfest/submissions/{sub.id}/withdraw/")
        self.set_deadlines(report=1)
        self.assertEqual(self.report(self.bob).status_code, 201)

    def test_partner_limit(self):
        for i in range(2):
            self.assertEqual(self.report(self.bob, source="partner", title=f"曲{i}").status_code, 201)
        res = self.report(self.bob, source="partner", title="第三首")
        self.assertEqual(res.status_code, 400)
        self.assertIn("source", res.data)

    def test_partner_backup_songs_do_not_count_toward_limit(self):
        for i in range(2):
            self.report(self.bob, source="partner", title=f"正選{i}")
        res = self.report(self.bob, source="partner", title="備曲", isBackup=True)
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["isBackup"])
        self.assertEqual(self.report(self.alice, title="社內備曲", isBackup=True).status_code, 400)
        summary = auth_client(self.staffer).get(f"/api/songfest/festivals/{self.festival.id}/manage/").data["summary"]
        self.assertEqual((summary["bySource"]["partner"], summary["partnerBackups"]), (2, 1))

    def test_report_deadline_applies_to_partner_too(self):
        # 社外投稿規則：合作社團的期限跟社內相同
        self.set_deadlines(report=-1)
        self.assertEqual(self.report(self.alice).status_code, 400)
        self.assertEqual(self.report(self.alice, source="partner").status_code, 400)

    def test_edit_and_delete_before_deadline(self):
        sub_id = self.report(self.alice).data["id"]
        res = self.patch(self.alice, sub_id, {"title": "改歌"})
        self.assertEqual((res.status_code, res.data["title"]), (200, "改歌"))
        self.assertEqual(self.patch(self.bob, sub_id, {"title": "x"}).status_code, 404)  # 別人的投稿
        res = auth_client(self.alice).delete(f"/api/songfest/submissions/{sub_id}/")
        self.assertEqual(res.status_code, 204)

    def test_after_report_deadline_song_is_locked(self):
        sub_id = self.report(self.alice).data["id"]
        self.set_deadlines(report=-1)
        self.assertEqual(self.patch(self.alice, sub_id, {"title": "換歌"}).status_code, 400)
        self.assertEqual(self.patch(self.alice, sub_id, {"fiveSec": False}).status_code, 400)
        res = self.patch(self.alice, sub_id, {"remarks": "補充說明"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(auth_client(self.alice).delete(f"/api/songfest/submissions/{sub_id}/").status_code, 400)
        self.assertTrue(res.data["permissions"]["canWithdraw"])
        self.assertFalse(res.data["permissions"]["withdrawIsLate"])


class WithdrawAndPenaltyTests(SubmissionTestCase):
    def next_festival(self):
        return Festival.objects.create(
            name="115下期初", date=self.festival.date + 100 * DAY, report_deadline=timezone.now() + 3 * DAY,
        )

    def test_withdraw_before_withdraw_deadline_has_no_penalty(self):
        sub_id = self.report(self.alice).data["id"]
        self.set_deadlines(report=-1)
        res = auth_client(self.alice).post(f"/api/songfest/submissions/{sub_id}/withdraw/")
        self.assertEqual(res.data["status"], "withdrawn")
        self.assertFalse(Submission.objects.get().is_offense())

    def test_late_withdraw_bans_next_festival(self):
        sub_id = self.report(self.alice).data["id"]
        self.set_deadlines(report=-3, withdraw=-1)
        mine = auth_client(self.alice).get(f"/api/songfest/festivals/{self.festival.id}/my-submissions/").data
        self.assertTrue(mine[0]["permissions"]["withdrawIsLate"])
        auth_client(self.alice).post(f"/api/songfest/submissions/{sub_id}/withdraw/")

        nxt = self.next_festival()
        res = auth_client(self.alice).post(f"/api/songfest/festivals/{nxt.id}/submissions/", song(), format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("不能報曲", res.data["detail"][0])
        # 只禁下一場，別人不受影響
        self.assertEqual(
            auth_client(self.bob).post(f"/api/songfest/festivals/{nxt.id}/submissions/", song(), format="json").status_code,
            201,
        )

    def test_overdue_upload_counts_as_late_withdraw_and_can_be_waived(self):
        self.report(self.alice)
        self.set_deadlines(report=-5, withdraw=-3, upload=-1)
        sub = Submission.objects.get()
        self.assertEqual(sub.status(), "overdue")
        self.assertEqual(sub.five_sec_status(), "cancelled")  # 歌逾期，5 秒畫面也取消
        nxt = self.next_festival()
        url = f"/api/songfest/festivals/{nxt.id}/submissions/"
        self.assertEqual(auth_client(self.alice).post(url, song(), format="json").status_code, 400)

        auth_client(self.staffer).patch(f"/api/songfest/manage/submissions/{sub.id}/", {"penaltyWaived": True}, format="json")
        self.assertEqual(auth_client(self.alice).post(url, song(), format="json").status_code, 201)

    def test_extension_moves_upload_deadline(self):
        self.report(self.alice)
        self.set_deadlines(report=-5, withdraw=-3, upload=-1)
        sub = Submission.objects.get()
        extended = (timezone.now() + DAY).isoformat()
        auth_client(self.staffer).patch(f"/api/songfest/manage/submissions/{sub.id}/", {"extendedUntil": extended}, format="json")
        sub.refresh_from_db()
        self.assertEqual(sub.status(), "reported")
        res = self.patch(self.alice, sub.id, {"fileLink": "https://drive.example/x", "duration": 200})
        self.assertEqual(res.data["status"], "uploaded")


class UploadTests(SubmissionTestCase):
    def test_upload_needs_duration_and_records_time(self):
        sub_id = self.report(self.alice).data["id"]
        res = self.patch(self.alice, sub_id, {"fileLink": "https://drive.example/a"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("duration", res.data)

        res = self.patch(self.alice, sub_id, {"fileLink": "https://drive.example/a", "duration": 191})
        self.assertEqual(res.data["status"], "uploaded")
        self.assertIsNotNone(res.data["uploadedAt"])
        self.assertIsNone(res.data["fileUpdatedAt"])

    def test_changing_file_after_upload_is_flagged_for_staff(self):
        sub_id = self.report(self.alice).data["id"]
        self.patch(self.alice, sub_id, {"fileLink": "https://drive.example/a", "duration": 191})
        Submission.objects.filter(pk=sub_id).update(file_checked=True, uploaded_at=timezone.now() - DAY)
        self.patch(self.alice, sub_id, {"duration": 200})
        sub = Submission.objects.get(pk=sub_id)
        self.assertTrue(sub.changed_after_upload)
        self.assertFalse(sub.file_checked)  # 要請排歌組重新確認

    def test_no_changes_after_upload_deadline(self):
        sub_id = self.report(self.alice).data["id"]
        self.set_deadlines(report=-3, withdraw=-2, upload=-1)
        res = self.patch(self.alice, sub_id, {"fileLink": "https://drive.example/a", "duration": 191})
        self.assertEqual(res.status_code, 400)

    def test_five_sec_upload(self):
        sub_id = self.report(self.alice, fiveSec=False).data["id"]
        self.assertEqual(self.patch(self.alice, sub_id, {"fiveSecLink": "https://drive.example/5"}).status_code, 400)
        other_id = self.report(self.alice, title="另一首").data["id"]
        res = self.patch(self.alice, other_id, {"fiveSecLink": "https://drive.example/5"})
        self.assertEqual(res.data["fiveSecStatus"], "uploaded")

    def test_chain_rules(self):
        a = self.report(self.alice, title="一").data["id"]
        b = self.report(self.alice, title="二").data["id"]
        c = self.report(self.alice, title="三").data["id"]
        bobs = self.report(self.bob, title="鮑伯的歌").data["id"]
        self.assertEqual(self.patch(self.alice, a, {"chainWith": bobs}).status_code, 400)
        self.assertEqual(self.patch(self.alice, a, {"chainWith": a}).status_code, 400)
        self.assertEqual(self.patch(self.alice, a, {"chainWith": b}).status_code, 200)
        self.assertEqual(self.patch(self.alice, c, {"chainWith": b}).status_code, 400)  # 至多 2 首
        self.assertEqual(self.patch(self.alice, b, {"chainWith": c}).status_code, 400)


class ReportThreadTests(SubmissionTestCase):
    def test_thread_lists_member_and_partner_but_not_guests(self):
        self.report(self.alice)
        self.report(self.bob, source="partner", title="社外的歌")
        Submission.objects.create(festival=self.festival, source="guest", editor_name="外人", song_source="x",
                                  visual_source="x", title="亂入", contact_email="guest@example.test")
        url = f"/api/songfest/festivals/{self.festival.id}/submissions/"
        self.assertEqual(APIClient().get(url).status_code, 401)
        rows = auth_client(self.alice).get(url).data
        self.assertEqual([r["title"] for r in rows], ["なんもねえ", "社外的歌"])
        self.assertEqual([r["isMine"] for r in rows], [True, False])
        self.assertNotIn("fileLink", rows[0])
        self.assertNotIn("contactEmail", rows[0])

    def test_rejected_is_only_visible_to_owner(self):
        sub_id = self.report(self.alice).data["id"]
        Submission.objects.filter(pk=sub_id).update(is_rejected=True)
        url = f"/api/songfest/festivals/{self.festival.id}/submissions/"
        self.assertEqual(len(auth_client(self.bob).get(url).data), 0)
        self.assertEqual(auth_client(self.alice).get(url).data[0]["status"], "rejected")

    def test_comments(self):
        sub_id = self.report(self.alice).data["id"]
        url = f"/api/songfest/submissions/{sub_id}/comments/"
        res = auth_client(self.bob).post(url, {"content": "二話不說先舉報"}, format="json")
        self.assertEqual(res.status_code, 201)
        comment_id = res.data["id"]
        rows = auth_client(self.alice).get(url).data
        self.assertEqual((rows[0]["username"], rows[0]["canDelete"]), ("bob", False))
        self.assertEqual(
            auth_client(self.alice).get(f"/api/songfest/festivals/{self.festival.id}/submissions/").data[0]["commentCount"], 1
        )
        delete_url = f"/api/songfest/submission-comments/{comment_id}/"
        self.assertEqual(auth_client(self.alice).delete(delete_url).status_code, 403)
        self.assertEqual(auth_client(self.staffer).delete(delete_url).status_code, 204)


class ManageTests(SubmissionTestCase):
    def setUp(self):
        super().setUp()
        previous = Festival.objects.create(name="115上期初", date=timezone.localdate() - 30 * DAY)
        Play.objects.create(festival=previous, position=1, song_source="カラオケ行こ！", title="HOWL")
        self.report(self.alice, fileLink="https://drive.example/a", duration=400)
        self.report(self.bob, source="partner", title="別首", songSource="ヤニねこ", visualSource="ヤニねこ")
        Submission.objects.create(festival=self.festival, source="guest", editor_name="よるば", song_source="ヤニねこ",
                                  visual_source="ヤニねこ", title="なんもねえ", contact_email="yoruba@example.test")
        Submission.objects.create(festival=self.festival, source="guest", editor_name="よるば",
                                  song_source="カラオケ行こ！", visual_source="カラオケ行こ！", title="HOWL")
        self.url = f"/api/songfest/festivals/{self.festival.id}/manage/"

    def test_only_staff_can_manage(self):
        self.assertEqual(auth_client(self.alice).get(self.url).status_code, 403)
        self.assertEqual(auth_client(self.staffer).get(self.url).status_code, 200)
        self.assertEqual(auth_client(self.officer).get(self.url).status_code, 200)

    def test_summary_and_warnings(self):
        data = auth_client(self.staffer).get(self.url).data
        summary = data["summary"]
        self.assertEqual(summary["active"], 4)
        self.assertEqual(summary["bySource"], {"member": 1, "partner": 1, "guest": 2})
        self.assertEqual(summary["uploaded"], 1)
        self.assertEqual(summary["fiveSecRequested"], 2)

        rows = {(r["source"], r["title"]): r for r in data["submissions"]}
        codes = lambda key: {w["code"] for w in rows[key]["warnings"]}  # noqa: E731
        self.assertIn("songCollision", codes(("member", "なんもねえ")))   # 跟亂入曲撞曲
        self.assertIn("workCollision", codes(("partner", "別首")))       # 社外跟社內同作品
        self.assertIn("playedLastTime", codes(("guest", "HOWL")))        # 亂入曲上一場播過
        self.assertEqual(rows[("guest", "HOWL")]["contactEmail"], "")
        self.assertEqual(rows[("guest", "なんもねえ")]["contactEmail"], "yoruba@example.test")

    def test_staff_actions(self):
        sub = Submission.objects.get(source="partner")
        url = f"/api/songfest/manage/submissions/{sub.id}/"
        self.assertEqual(auth_client(self.alice).patch(url, {"isRejected": True}, format="json").status_code, 403)
        res = auth_client(self.staffer).patch(url, {"isRejected": True, "rejectReason": "非 ACGN"}, format="json")
        self.assertEqual((res.data["status"], res.data["rejectReason"]), ("rejected", "非 ACGN"))
        res = auth_client(self.staffer).patch(url, {"isRejected": False, "duration": 250, "fileChecked": True}, format="json")
        self.assertEqual((res.data["status"], res.data["rejectReason"], res.data["duration"]), ("reported", "", 250))

    def test_chain_too_long_warning(self):
        a = Submission.objects.get(source="member")
        b = self.report(self.alice, title="連曲", fileLink="https://drive.example/b", duration=250).data["id"]
        self.patch(self.alice, b, {"chainWith": a.id})
        rows = {r["id"]: r for r in auth_client(self.staffer).get(self.url).data["submissions"]}
        self.assertIn("chainTooLong", {w["code"] for w in rows[b]["warnings"]})

    def test_export_csv(self):
        res = auth_client(self.staffer).get(f"{self.url}export/")
        self.assertEqual(res.status_code, 200)
        text = res.content.decode("utf-8")
        self.assertTrue(text.startswith("﻿來源,狀態"))
        self.assertIn("なんもねえ", text)
        self.assertIn("6:40", text)

    def test_manage_festival_list(self):
        self.assertEqual([f["id"] for f in auth_client(self.staffer).get("/api/songfest/manage/festivals/").data],
                         [self.festival.id])
        self.assertEqual(auth_client(self.alice).get("/api/songfest/manage/festivals/").data, [])
        self.assertIn(self.festival.id, [f["id"] for f in auth_client(self.officer).get("/api/songfest/manage/festivals/").data])

    def test_officer_assigns_staff_in_admin(self):
        self.client.force_login(self.officer)
        res = self.client.post(f"/admin/songfest/festival/{self.festival.id}/change/", {
            "name": self.festival.name, "date": self.festival.date.isoformat(), "kind": "hall", "is_published": "on",
            "partner_name": "健行科大", "partner_limit": 10, "request_limit": 3,
            "staff-TOTAL_FORMS": 2, "staff-INITIAL_FORMS": 1, "staff-MIN_NUM_FORMS": 0, "staff-MAX_NUM_FORMS": 1000,
            "staff-0-id": FestivalStaff.objects.get().id, "staff-0-festival": self.festival.id,
            "staff-0-user": self.staffer.id, "staff-0-role": "lead",
            "staff-1-festival": self.festival.id, "staff-1-user": self.bob.id, "staff-1-role": "player",
        })
        self.assertEqual(res.status_code, 302, res.content[:2000])
        self.assertTrue(FestivalStaff.objects.filter(user=self.bob, role="player").exists())

    def test_me_reports_songfest_staff(self):
        self.assertTrue(auth_client(self.staffer).get("/api/me/").data["songfestStaff"])
        self.assertFalse(auth_client(self.alice).get("/api/me/").data["songfestStaff"])


class GuestImportTests(SubmissionTestCase):
    HEADER = ["時間戳記", "投稿人", "電子信箱", "歌曲出處", "畫面出處", "歌曲名稱", "作品檔案上傳", "備註",
              "是否加入中央動畫社歌單?", "是否投稿5秒畫面?", "5秒檔案上傳", "想對我們說的話"]

    def setUp(self):
        super().setUp()
        # 時間只算一次：同一份表單匯入兩次，時間戳記要一樣才會被當成同一筆回覆
        now = dt.datetime.now().replace(microsecond=0)
        self.early = now - 2 * DAY
        self.late = now + 9 * DAY  # 超過亂入截止

    def form_file(self):
        early, late = self.early, self.late
        data = workbook_bytes({
            "表單回覆 2": [
                self.HEADER,
                [early, "飯糰", "rice@example.test", "一般曲", "淡島百景", "踊り子", "https://drive.example/1",
                 "MAD", "是", "是", "https://drive.example/5", "請多指教"],
                [late, "cloud", "cloud@example.test", "無職転生", "無職転生", "祈り、終われば", "", None, "否", "否", None, None],
            ],
            # 排歌組自己整理的分頁，欄位不同，要略過
            "亂入曲投稿整理": [["序列", "歌曲出處", "畫面出處", "曲名"], [1, "a", "b", "c"]],
        })
        return SimpleUploadedFile("亂入曲.xlsx", data, content_type=XLSX)

    def test_import_and_reimport(self):
        url = f"/api/songfest/festivals/{self.festival.id}/manage/import-guests/"
        self.assertEqual(auth_client(self.alice).post(url, {"file": self.form_file()}).status_code, 403)
        res = auth_client(self.staffer).post(url, {"file": self.form_file()})
        self.assertEqual(res.status_code, 200)
        self.assertIn("亂入曲：新增 2 首、更新 0 首", res.data["lines"])

        rice = Submission.objects.get(title="踊り子")
        self.assertEqual((rice.source, rice.editor_name, rice.contact_email), ("guest", "飯糰", "rice@example.test"))
        self.assertEqual(rice.status(), "uploaded")
        self.assertTrue(rice.library_consent and rice.five_sec)
        self.assertEqual(rice.five_sec_status(), "uploaded")

        # 排歌組填的長度不會被重新匯入蓋掉
        Submission.objects.filter(pk=rice.pk).update(duration_seconds=222)
        res = auth_client(self.staffer).post(url, {"file": self.form_file()})
        self.assertIn("亂入曲：新增 0 首、更新 2 首", res.data["lines"])
        self.assertEqual(Submission.objects.get(pk=rice.pk).duration_seconds, 222)

        rows = {r["title"]: r for r in auth_client(self.staffer).get(
            f"/api/songfest/festivals/{self.festival.id}/manage/").data["submissions"]}
        self.assertIn("afterGuestDeadline", {w["code"] for w in rows["祈り、終われば"]["warnings"]})

    def test_guest_limit_and_five_sec_per_person(self):
        for i in range(6):
            Submission.objects.create(
                festival=self.festival, source="guest", editor_name="很會剪", contact_email="many@example.test",
                song_source="x", visual_source="x", title=f"曲{i}", five_sec=True,
                five_sec_link="https://drive.example/5", five_sec_uploaded_at=timezone.now(),
            )
        data = auth_client(self.staffer).get(f"/api/songfest/festivals/{self.festival.id}/manage/").data
        self.assertIn("guestLimit", {w["code"] for w in data["submissions"][0]["warnings"]})
        # 亂入曲 5 秒畫面每人最多一段
        self.assertEqual((data["summary"]["fiveSecRequested"], data["summary"]["fiveSecUploaded"]), (1, 1))

    def test_bad_file(self):
        url = f"/api/songfest/festivals/{self.festival.id}/manage/import-guests/"
        bad = SimpleUploadedFile("x.xlsx", workbook_bytes({"a": [["x", "y"]]}), content_type=XLSX)
        res = auth_client(self.staffer).post(url, {"file": bad})
        self.assertEqual(res.status_code, 400)
        self.assertIn("時間戳記", res.data["file"][0])
