# NCUACG/checkin/tests.py
import datetime as dt

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.tests import auth_client, make_user
from checkin.models import Checkin, CheckinEvent, CheckinSlot
from checkin.rules import normalize_student_id
from club.models import CourseLead, Lesson
from songfest.models import Festival, FestivalStaff

TZ = timezone.get_current_timezone()
DAY = dt.timedelta(days=1)


def ms(value: dt.datetime) -> int:
    return int(value.timestamp() * 1000)


class CheckinTestCase(TestCase):
    def setUp(self):
        self.officer = make_user("officer@example.test", is_staff=True)
        self.staffer = make_user("staffer@example.test")
        self.lead = make_user("lead@example.test")
        self.member = make_user("member@example.test")
        self.festival = Festival.objects.create(name="115上期末", date=timezone.localdate() + 5 * DAY)
        FestivalStaff.objects.create(festival=self.festival, user=self.staffer, role="lead")
        CourseLead.objects.create(category="railway", user=self.lead)
        start = timezone.now() + DAY
        self.lesson = Lesson.objects.create(category="railway", title="高鐵與捷運", start_time=start,
                                            end_time=start + dt.timedelta(hours=2))

    def create(self, user, **data):
        return auth_client(user).post("/api/checkin/events/", data, format="json")

    def scan(self, event, records, key=None, device="phone-1"):
        url = f"/api/checkin/scan/{event['id']}/records/?key={key or event['scanKey']}"
        return APIClient().post(url, {"device": device, "records": records}, format="json")


class NormalizeTests(TestCase):
    def test_student_card_barcode(self):
        self.assertEqual(normalize_student_id("1131021230"), "113102123")  # 10 碼取前 9 碼
        self.assertEqual(normalize_student_id(" *113102123*\r\n"), "113102123")
        self.assertEqual(normalize_student_id("abc"), "ABC")


class EventTests(CheckinTestCase):
    def test_festival_event_uses_setlist_sessions(self):
        res = self.create(self.staffer, festival=self.festival.id)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual([s["name"] for s in res.data["slots"]], ["上午場", "下午一", "下午二"])  # 不含測試曲
        first = res.data["slots"][0]
        start = dt.datetime.fromisoformat(first["startsAt"]).astimezone(TZ)
        self.assertEqual((start.date(), start.hour), (self.festival.date, 10))
        self.assertEqual(first["opensAt"], first["startsAt"])  # 預設整場都能簽
        # 同一場不能建兩次
        self.assertEqual(self.create(self.staffer, festival=self.festival.id).status_code, 400)

    def test_lesson_event(self):
        res = self.create(self.lead, lesson=self.lesson.id)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["title"], "鐵道社課：高鐵與捷運")
        self.assertEqual(len(res.data["slots"]), 1)

    def test_who_can_create_what(self):
        self.assertEqual(self.create(self.member, festival=self.festival.id).status_code, 403)
        self.assertEqual(self.create(self.lead, festival=self.festival.id).status_code, 400)
        self.assertEqual(self.create(self.staffer, lesson=self.lesson.id).status_code, 400)
        start = timezone.now() + DAY
        custom = {"title": "社員大會", "slots": [{"name": "大會", "startsAt": start.isoformat(),
                                                   "endsAt": (start + dt.timedelta(hours=1)).isoformat()}]}
        self.assertEqual(self.create(self.lead, **custom).status_code, 403)  # 自訂活動只有幹部能建
        self.assertEqual(self.create(self.officer, **custom).status_code, 201)

    def test_list_and_sources(self):
        data = auth_client(self.staffer).get("/api/checkin/events/").data
        self.assertEqual([f["name"] for f in data["sources"]["festivals"]], ["115上期末"])
        self.assertEqual(data["sources"]["lessons"], [])
        self.create(self.staffer, festival=self.festival.id)
        data = auth_client(self.staffer).get("/api/checkin/events/").data
        self.assertEqual(len(data["events"]), 1)
        self.assertEqual(data["sources"]["festivals"], [])  # 已經建過就不再列出
        self.assertEqual(auth_client(self.lead).get("/api/checkin/events/").data["events"], [])

    def test_edit_slot_window(self):
        event = self.create(self.staffer, festival=self.festival.id).data
        slot = event["slots"][0]
        opens = dt.datetime.fromisoformat(slot["startsAt"]) - dt.timedelta(minutes=10)
        res = auth_client(self.staffer).patch(f"/api/checkin/slots/{slot['id']}/", {"opensAt": opens.isoformat()}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(dt.datetime.fromisoformat(res.data["slots"][0]["opensAt"]), opens)
        bad = dt.datetime.fromisoformat(slot["endsAt"]) + DAY
        res = auth_client(self.staffer).patch(f"/api/checkin/slots/{slot['id']}/", {"opensAt": bad.isoformat()}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(auth_client(self.member).patch(f"/api/checkin/slots/{slot['id']}/", {"name": "x"}, format="json").status_code, 403)

    def test_me_flag(self):
        self.assertTrue(auth_client(self.staffer).get("/api/me/").data["checkinManager"])
        self.assertTrue(auth_client(self.lead).get("/api/me/").data["checkinManager"])
        self.assertFalse(auth_client(self.member).get("/api/me/").data["checkinManager"])


class ScanTests(CheckinTestCase):
    def setUp(self):
        super().setUp()
        self.event = self.create(self.staffer, festival=self.festival.id).data
        self.am, self.pm1 = self.event["slots"][0], self.event["slots"][1]
        self.ts = ms(dt.datetime.fromisoformat(self.am["startsAt"]) + dt.timedelta(minutes=5))

    def record(self, cid, sid="1131021230", slot=None, src="camera"):
        return {"cid": cid, "slot": (slot or self.am)["id"], "sid": sid, "raw": sid, "src": src, "ts": self.ts}

    def test_scan_info_needs_key(self):
        url = f"/api/checkin/scan/{self.event['id']}/"
        self.assertEqual(APIClient().get(url).status_code, 403)
        self.assertEqual(APIClient().get(url + "?key=wrong").status_code, 403)
        res = APIClient().get(f"{url}?key={self.event['scanKey']}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["event"]["title"], "歌謠祭 115上期末")
        self.assertNotIn("records", res.data)  # 掃描頁拿不到別人的學號

    def test_batch_upload_with_dup_and_resend(self):
        res = self.scan(self.event, [self.record("a1"), self.record("a2", sid="113102124", src="manual"),
                                     self.record("a3", sid="12")])
        self.assertEqual(res.data["results"], {"a1": "ok", "a2": "ok", "a3": "invalid"})
        self.assertEqual(Checkin.objects.get(client_id="a1").student_id, "113102123")
        # 網路不穩重送同一批：不會重複寫入
        res = self.scan(self.event, [self.record("a1")])
        self.assertEqual(res.data["results"], {"a1": "ok"})
        # 另一台裝置離線時也掃到同一個人：同一場只留第一筆
        res = self.scan(self.event, [self.record("b1")], device="phone-2")
        self.assertEqual(res.data["results"], {"b1": "dup"})
        # 下一場可以再簽
        self.assertEqual(self.scan(self.event, [self.record("b2", slot=self.pm1)]).data["results"], {"b2": "ok"})
        counts = {s["name"]: s["count"] for s in res.data["slots"]}
        self.assertEqual(counts["上午場"], 2)
        self.assertEqual(Checkin.objects.count(), 3)

    def test_slot_from_another_event_is_rejected(self):
        other = self.create(self.lead, lesson=self.lesson.id).data
        res = self.scan(self.event, [self.record("x1", slot=other["slots"][0])])
        self.assertEqual(res.data["results"], {"x1": "invalid"})

    def test_reset_key_invalidates_old_link(self):
        old = self.event["scanKey"]
        new = auth_client(self.staffer).post(f"/api/checkin/events/{self.event['id']}/reset-key/").data["scanKey"]
        self.assertNotEqual(old, new)
        self.assertEqual(self.scan(self.event, [self.record("r1")], key=old).status_code, 403)
        self.assertEqual(self.scan(self.event, [self.record("r1")], key=new).status_code, 200)

    def test_detail_shows_student_ids_only_to_managers(self):
        self.scan(self.event, [self.record("a1")])
        url = f"/api/checkin/events/{self.event['id']}/"
        self.assertEqual(auth_client(self.member).get(url).status_code, 403)
        self.assertEqual(auth_client(self.lead).get(url).status_code, 403)
        data = auth_client(self.staffer).get(url).data
        self.assertEqual([r["studentId"] for r in data["records"]], ["113102123"])
        self.assertEqual((data["total"], data["people"]), (1, 1))
        self.assertEqual(auth_client(self.officer).get(url).status_code, 200)

    def test_delete_wrong_record(self):
        self.scan(self.event, [self.record("a1")])
        record_id = Checkin.objects.get().id
        self.assertEqual(auth_client(self.member).delete(f"/api/checkin/records/{record_id}/").status_code, 403)
        self.assertEqual(auth_client(self.staffer).delete(f"/api/checkin/records/{record_id}/").status_code, 204)

    def test_export_matches_demo_format(self):
        self.scan(self.event, [self.record("a1"), self.record("a2", sid="113102124"), self.record("a3", slot=self.pm1)])
        client = auth_client(self.staffer)
        detail = client.get(f"/api/checkin/events/{self.event['id']}/export/").content.decode("utf-8-sig")
        lines = detail.strip().split("\r\n")
        self.assertEqual(lines[0], "學號,日期,時間,場次,來源,原始條碼")
        self.assertEqual(len(lines), 4)
        summary = client.get(f"/api/checkin/events/{self.event['id']}/export/?type=summary").content.decode("utf-8-sig")
        lines = summary.strip().split("\r\n")
        self.assertEqual(lines[0], "學號,上午場,下午一,下午二,簽到場數")
        self.assertEqual(lines[1], "113102123,有,有,無,2")
        self.assertEqual(lines[2], "113102124,有,無,無,1")

        stats = client.get("/api/checkin/events/export/").content.decode("utf-8-sig").strip().split("\r\n")
        self.assertEqual(stats[0], "日期,活動,種類,場次,簽到人數")
        self.assertIn("歌謠祭 115上期末,歌謠祭,上午場,2", stats[1])

    def test_deleting_event_deletes_records(self):
        self.scan(self.event, [self.record("a1")])
        self.assertEqual(auth_client(self.staffer).delete(f"/api/checkin/events/{self.event['id']}/").status_code, 204)
        self.assertFalse(CheckinEvent.objects.exists())
        self.assertFalse(CheckinSlot.objects.exists())
        self.assertFalse(Checkin.objects.exists())

