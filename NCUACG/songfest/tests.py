# NCUACG/songfest/tests.py
import datetime as dt
from io import BytesIO

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.tests import make_user
from songfest.importers import import_songfest
from songfest.models import Festival, Play, Track
from songfest.text import cell_text, duration_seconds, guess_festival_name, normalize, play_date

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def workbook_bytes(sheets: dict[str, list[list]]) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def as_file(data: bytes) -> BytesIO:
    return BytesIO(data)


def songlist_sheets(extra_rows=()):
    """模仿「中央動畫社線上歌單」：DVD編號 主分頁 + 五十音分頁 + 已封存的 VCD 分頁。"""
    main = [
        [None, "DVD", "歌曲出處", "畫面出處", "曲名", "歌手", "DVD編號", "長度", "製作者"],
        [None, "DVD01", "とある科学の超電磁砲", "とある科学の超電磁砲", "only my railgun", "fripSide", "D0101",
         dt.time(0, 4, 13), "pokemongod"],
        [None, None, "ヤマノススメ", "ヤマノススメ", "夏色プレゼント", "", "D9921", dt.time(0, 3, 0), 300.0],
        [None, None, "牙狼", "牙狼", "SAVIOR", "JAM", "D10001", dt.time(0, 4, 0), "A"],
        [None, None, "牙狼", "牙狼", "SAVIOR", "JAM", "D10002", dt.time(0, 4, 5), "B"],
        [None, None, "崩壞3rd", "崩壞3rd", True, "", "D10003", "3:30", "C"],
        *extra_rows,
    ]
    kana_header = [None, "歌曲出處", "畫面出處", "曲名", "DVD編號", "製作者"]
    return {
        "DVD編號": main,
        "あ～お行": [kana_header, [None, "あ 行"], [None, "牙狼", "牙狼", "SAVIOR", "D10001", "A"],
                    [None, "お 行"], [None, "牙狼", "牙狼", "SAVIOR", "D10002", "B"]],
        "た～と行": [kana_header, [None, "と 行"], [None, "とある科学の超電磁砲", "", "only my railgun", "D0101", "x"]],
        "特攝": [kana_header, [None, "特攝"], [None, "崩壞3rd", "崩壞3rd", "TRUE", "D10003", "C"]],
        # 已封存的分頁要略過，不然 D0101 會被分到這裡
        "VCD編號(已封存)": [[None, "VCD", "作品", "曲名", "DVD編號"], [None, "VCD 01", "x", "y", "D0101"]],
    }


def ymd(date: dt.date) -> float:
    """播放紀錄的日期欄在試算表裡是 20260614.0 這種數字"""
    return float(date.strftime("%Y%m%d"))


RECENT = timezone.localdate() - dt.timedelta(days=30)
OLD = timezone.localdate() - dt.timedelta(days=365 * 6)


def history_sheets():
    return {
        "工作表1": [
            ["歌曲出處", "畫面出處", "曲名", "播放日期", "注意！每個人都有編輯權限"],
            ["とある科学の超電磁砲", "とある科学の超電磁砲", "ONLY MY RAILGUN", ymd(RECENT)],  # 大小寫不同也對得到
            ["牙狼", "牙狼", "SAVIOR", ymd(RECENT)],  # 兩個版本 → 無法判斷
            ["夫婦以上、恋人未満", "夫婦以上、恋人未満", "swallows", ymd(RECENT)],  # 沒收進歌單的新曲
            ["おたくのビデオ", "5秒畫面", "戦え！おたキング", ymd(RECENT)],  # 結尾 Credits 影片
            [None, None, None, None],
            ["とある科学の超電磁砲", "とある科学の超電磁砲", "only my railgun", ymd(OLD)],
            ["x", "x", None, ymd(OLD)],  # 沒有曲名
            ["y", "y", "z", "不是日期"],
        ]
    }


SONGLIST = workbook_bytes(songlist_sheets())
HISTORY = workbook_bytes(history_sheets())


def import_all():
    return import_songfest(songlist=as_file(SONGLIST), history=as_file(HISTORY))


class TextTests(SimpleTestCase):
    def test_normalize_ignores_width_case_and_punctuation(self):
        self.assertEqual(normalize("ラブライブ！ Only My"), normalize("ラブライブ! onlymy"))
        self.assertEqual(normalize("!!"), "!!")  # 全是符號時不能變成空字串

    def test_cell_text_restores_values_spreadsheets_converted(self):
        self.assertEqual(cell_text(True), "TRUE")
        self.assertEqual(cell_text(300.0), "300")
        self.assertEqual(cell_text("  a "), "a")

    def test_duration_seconds(self):
        self.assertEqual(duration_seconds(dt.time(0, 4, 25)), 265)
        self.assertEqual(duration_seconds(dt.timedelta(seconds=211)), 211)
        self.assertEqual(duration_seconds("4:25"), 265)
        self.assertEqual(duration_seconds("1:02:03"), 3723)
        self.assertIsNone(duration_seconds("abc"))

    def test_play_date(self):
        self.assertEqual(play_date(20260614.0), dt.date(2026, 6, 14))
        self.assertEqual(play_date("2026/06/14"), dt.date(2026, 6, 14))
        self.assertIsNone(play_date("不是日期"))

    def test_guess_festival_name(self):
        self.assertEqual(guess_festival_name(dt.date(2025, 9, 20)), "114上期初")
        self.assertEqual(guess_festival_name(dt.date(2025, 11, 29)), "114上期末")
        self.assertEqual(guess_festival_name(dt.date(2026, 1, 10)), "114上期末")
        self.assertEqual(guess_festival_name(dt.date(2026, 3, 21)), "114下期初")
        self.assertEqual(guess_festival_name(dt.date(2026, 6, 14)), "114下期末")


class SonglistImportTests(TestCase):
    def test_imports_main_sheet_with_kana_index(self):
        report = import_songfest(songlist=as_file(SONGLIST))
        self.assertIn("舊曲：新增 5、更新 0、沒有變動 0", report.lines)

        railgun = Track.objects.get(dvd_code="D0101")
        # 欄位以 DVD編號 分頁為準（五十音分頁的畫面出處是空的）
        self.assertEqual(railgun.visual_source, "とある科学の超電磁砲")
        self.assertEqual(railgun.duration_seconds, 253)
        self.assertEqual((railgun.index_label, railgun.index_group), ("と", "た"))

        self.assertEqual(Track.objects.get(dvd_code="D10002").index_group, "あ")  # お行歸在あ行
        self.assertEqual(Track.objects.get(dvd_code="D10003").title, "TRUE")
        self.assertEqual(Track.objects.get(dvd_code="D10003").duration_seconds, 210)
        self.assertEqual(Track.objects.get(dvd_code="D9921").editor, "300")

        # 五十音順照試算表；沒出現在五十音分頁的排最後並提醒
        self.assertEqual(
            list(Track.objects.values_list("dvd_code", flat=True)),
            ["D10001", "D10002", "D0101", "D10003", "D9921"],
        )
        self.assertTrue(any("D9921" in w for w in report.warnings))

    def test_reimport_is_idempotent_and_updates_changes(self):
        import_songfest(songlist=as_file(SONGLIST))
        report = import_songfest(songlist=as_file(SONGLIST))
        self.assertIn("舊曲：新增 0、更新 0、沒有變動 5", report.lines)

        sheets = songlist_sheets()
        sheets["DVD編號"][1][4] = "only my railgun (TV size)"
        report = import_songfest(songlist=as_file(workbook_bytes(sheets)))
        self.assertIn("舊曲：新增 0、更新 1、沒有變動 4", report.lines)
        self.assertEqual(Track.objects.get(dvd_code="D0101").title, "only my railgun (TV size)")

    def test_removed_rows_are_kept_unless_prune(self):
        import_songfest(songlist=as_file(SONGLIST))
        sheets = songlist_sheets()
        del sheets["DVD編號"][2]  # 拿掉 D9921
        smaller = workbook_bytes(sheets)

        report = import_songfest(songlist=as_file(smaller))
        self.assertTrue(Track.objects.filter(dvd_code="D9921").exists())
        self.assertTrue(any("D9921" in w for w in report.warnings))

        import_songfest(songlist=as_file(smaller), prune=True)
        self.assertFalse(Track.objects.filter(dvd_code="D9921").exists())

    def test_dry_run_writes_nothing(self):
        report = import_songfest(songlist=as_file(SONGLIST), history=as_file(HISTORY), dry_run=True)
        self.assertIn("舊曲：新增 5、更新 0、沒有變動 0", report.lines)
        self.assertFalse(Track.objects.exists())
        self.assertFalse(Festival.objects.exists())


class HistoryImportTests(TestCase):
    def test_creates_festivals_and_matches_plays(self):
        report = import_all()
        self.assertEqual(Festival.objects.count(), 2)
        self.assertEqual(Festival.objects.get(date=RECENT).name, guess_festival_name(RECENT))
        self.assertEqual(Play.objects.count(), 5)
        self.assertTrue(any("2 列" in w for w in report.warnings))  # 沒曲名、日期看不懂

        plays = {p.title: p for p in Play.objects.filter(festival__date=RECENT)}
        self.assertEqual(plays["ONLY MY RAILGUN"].match_status, "matched")
        self.assertEqual(plays["ONLY MY RAILGUN"].track.dvd_code, "D0101")
        self.assertEqual(plays["SAVIOR"].match_status, "ambiguous")
        self.assertIsNone(plays["SAVIOR"].track)
        self.assertEqual(plays["swallows"].match_status, "unmatched")
        self.assertEqual([p.position for p in Play.objects.filter(festival__date=RECENT)], [1, 2, 3, 4])

    def test_reimport_replaces_plays_and_keeps_festival_name(self):
        import_all()
        Festival.objects.filter(date=RECENT).update(name="改過的名字", venue="校史館大講堂")
        import_all()
        self.assertEqual(Play.objects.count(), 5)
        festival = Festival.objects.get(date=RECENT)
        self.assertEqual((festival.name, festival.venue), ("改過的名字", "校史館大講堂"))


class SongfestApiTests(TestCase):
    def setUp(self):
        import_all()
        self.client = APIClient()

    def get(self, url, **params):
        res = self.client.get(url, params)
        self.assertEqual(res.status_code, 200)
        return res.data

    def test_track_play_stats_are_per_song(self):
        tracks = {t["dvdCode"]: t for t in self.get("/api/songfest/tracks/")["results"]}
        railgun = tracks["D0101"]
        self.assertEqual((railgun["playCount"], railgun["recentPlayCount"]), (2, 1))
        self.assertEqual(railgun["lastPlayed"], RECENT.isoformat())
        # 兩個版本對不到是哪一個，但「這首歌」播過，兩個版本都算
        self.assertEqual(tracks["D10001"]["playCount"], 1)
        self.assertEqual(tracks["D10002"]["playCount"], 1)
        self.assertEqual(tracks["D9921"]["playCount"], 0)
        self.assertIsNone(tracks["D9921"]["lastPlayed"])

    def test_search_ignores_full_width_and_case(self):
        data = self.get("/api/songfest/tracks/", q="ＯＮＬＹ　ＭＹ")
        self.assertEqual([t["dvdCode"] for t in data["results"]], ["D0101"])
        self.assertEqual(self.get("/api/songfest/tracks/", q="300")["count"], 1)  # 製作者也能搜

    def test_group_filter_sort_and_pagination(self):
        data = self.get("/api/songfest/tracks/", group="あ")
        self.assertEqual([t["dvdCode"] for t in data["results"]], ["D10001", "D10002"])
        data = self.get("/api/songfest/tracks/", sort="newest", page_size=2, page=2)
        self.assertEqual((data["count"], data["page"], data["pageCount"]), (5, 2, 3))
        self.assertEqual([t["dvdCode"] for t in data["results"]], ["D10001", "D9921"])

    def test_groups_follow_spreadsheet_order(self):
        self.assertEqual(
            self.get("/api/songfest/tracks/groups/"),
            [{"group": "あ", "count": 2}, {"group": "た", "count": 1}, {"group": "特攝", "count": 1}],
        )

    def test_ranking_skips_credits_video(self):
        ranking = self.get("/api/songfest/ranking/", years=0)
        self.assertEqual(ranking[0]["title"], "ONLY MY RAILGUN")  # 顯示最近一次的寫法
        self.assertEqual(ranking[0]["playCount"], 2)
        self.assertNotIn("戦え！おたキング", [r["title"] for r in ranking])
        recent = self.get("/api/songfest/ranking/")
        self.assertEqual(recent[0]["playCount"], 1)

    def test_festival_list_and_detail(self):
        festivals = self.get("/api/songfest/festivals/")
        self.assertEqual([f["date"] for f in festivals], [RECENT.isoformat(), OLD.isoformat()])
        detail = self.get(f"/api/songfest/festivals/{festivals[0]['id']}/")
        self.assertEqual(detail["playCount"], 4)
        self.assertEqual(detail["plays"][0]["dvdCode"], "D0101")
        self.assertIsNone(detail["plays"][1]["dvdCode"])
        self.assertTrue(detail["plays"][3]["isCredits"])

    def test_unpublished_festival_is_hidden(self):
        festival = Festival.objects.get(date=RECENT)
        festival.is_published = False
        festival.save()
        self.assertEqual(len(self.get("/api/songfest/festivals/")), 1)
        self.assertEqual(self.client.get(f"/api/songfest/festivals/{festival.id}/").status_code, 404)
        railgun = self.get("/api/songfest/tracks/", q="railgun")["results"][0]
        self.assertEqual(railgun["playCount"], 1)


class SongfestAdminTests(TestCase):
    def setUp(self):
        self.officer = make_user("officer@example.test", is_staff=True)

    def test_spreadsheet_data_is_read_only(self):
        import_all()
        self.client.force_login(self.officer)
        track = Track.objects.get(dvd_code="D0101")
        self.assertEqual(self.client.get("/admin/songfest/track/").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/songfest/track/{track.pk}/change/").status_code, 200)
        self.assertEqual(self.client.get("/admin/songfest/track/add/").status_code, 403)
        self.assertEqual(self.client.get("/admin/songfest/festival/add/").status_code, 200)

    def test_officer_imports_from_admin(self):
        self.client.force_login(self.officer)
        url = "/admin/songfest/track/import/"
        self.assertEqual(self.client.get(url).status_code, 200)

        def upload():
            return {
                "songlist": SimpleUploadedFile("線上歌單.xlsx", SONGLIST, content_type=XLSX),
                "history": SimpleUploadedFile("播放紀錄.xlsx", HISTORY, content_type=XLSX),
            }

        res = self.client.post(url, upload())  # 預設按鈕是試跑
        self.assertContains(res, "以上變更都沒有寫入")
        self.assertFalse(Track.objects.exists())

        res = self.client.post(url, {**upload(), "_import": "匯入"})
        self.assertContains(res, "舊曲：新增 5")
        self.assertEqual(Track.objects.count(), 5)
        self.assertEqual(Play.objects.count(), 5)

    def test_bad_file_shows_error(self):
        self.client.force_login(self.officer)
        res = self.client.post(
            "/admin/songfest/track/import/",
            {"songlist": SimpleUploadedFile("x.xlsx", b"not a spreadsheet", content_type=XLSX), "_import": "1"},
        )
        self.assertContains(res, "無法讀取試算表")

    def test_member_cannot_import(self):
        self.client.force_login(make_user())
        res = self.client.get("/admin/songfest/track/import/")
        self.assertEqual(res.status_code, 302)
