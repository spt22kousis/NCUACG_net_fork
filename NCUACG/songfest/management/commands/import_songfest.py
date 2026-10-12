# NCUACG/songfest/management/commands/import_songfest.py
from django.core.management.base import BaseCommand, CommandError

from songfest.importers import SpreadsheetError, import_songfest


class Command(BaseCommand):
    help = (
        "從 Google 試算表下載的 .xlsx 同步舊曲與播放紀錄（試算表是正本，可以重複執行）。\n"
        "例：python manage.py import_songfest --songlist 線上歌單.xlsx --history 最新播放曲目統計.xlsx"
    )

    def add_arguments(self, parser):
        parser.add_argument("--songlist", help="「中央動畫社線上歌單」的 .xlsx")
        parser.add_argument("--history", help="「最新播放曲目統計」的 .xlsx")
        parser.add_argument("--prune", action="store_true", help="刪除網站上有、但試算表裡已經沒有的舊曲")
        parser.add_argument("--dry-run", action="store_true", help="試跑：只顯示會有什麼變動，不寫入資料庫")

    def handle(self, *args, **options):
        if not options["songlist"] and not options["history"]:
            raise CommandError("請至少指定 --songlist 或 --history 其中一個")
        try:
            report = import_songfest(
                songlist=options["songlist"],
                history=options["history"],
                prune=options["prune"],
                dry_run=options["dry_run"],
            )
        except (SpreadsheetError, FileNotFoundError) as exc:
            raise CommandError(str(exc)) from exc

        for line in report.lines:
            self.stdout.write(self.style.SUCCESS(line))
        for line in report.warnings:
            self.stdout.write(self.style.WARNING(f"注意：{line}"))
