# NCUACG/songfest/management/commands/seed_songfest_demo.py
"""
建立歌謠祭新曲投稿的展示資料，方便本機測試（DEBUG=False 時拒絕執行）。

  python manage.py seed_songfest_demo --staff c1@c.tw --members b1@b.tw a1@a.tw

- 目前的場次（今天以後最近的大講堂歌謠祭）：沒有就建立「測試場」；有就補上截止時間、規定、亂入曲設定。
- --staff 的帳號加進這場的排歌組（主排）。
- --members 的帳號各分到幾首投稿，登入就能測修改、繳交、窗歌。
- 另外建立幾個無法登入的展示帳號（demo-*@example.test），讓回報串與管理歌單有各種狀況：
  已繳交、窗歌、繳交後改檔、合作社團、撞曲、撞作品、連曲、亂入曲上一場播過。
- 可以重複執行：會先刪掉上次建立的展示投稿（external_id 以 demo: 開頭）。
"""
import datetime as dt

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from songfest.models import Festival, FestivalStaff, Play, Submission, SubmissionComment

DAY = dt.timedelta(days=1)

DEMO_USERS = [
    ("demo-member1@example.test", "展示社員甲"),
    ("demo-member2@example.test", "展示社員乙"),
    ("demo-partner@example.test", "展示健行社員"),
]

RULES = """1. 不接受兩人報同一首歌，若都想剪同一首請自行協調
2. 窗歌截止後才窗歌，下次歌謠祭禁止報曲 1 次
3. 繳交截止前未上傳，視為逾期窗歌
4. 畫面或歌曲至少一者需符合廣義 ACGN；禁止 R18 畫面、鬼畜版本，原則上禁止 AI 素材
5. 排歌組有最終解釋權"""

GUEST_INFO = """將亂入曲資訊與檔案透過下方表單投稿。
投稿資訊：曲名、作品名、長度、作者。
前次歌謠祭已播放之歌曲不會入選；禁止以分身名義投稿。"""


class Command(BaseCommand):
    help = "建立歌謠祭新曲投稿的展示資料（只在本機開發用）"

    def add_arguments(self, parser):
        parser.add_argument("--staff", help="加進排歌組（主排）的帳號 email")
        parser.add_argument("--members", nargs="*", default=[], help="要分到投稿的帳號 email")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("這個指令只能在本機開發（DJANGO_DEBUG=True）時使用")

        def get_user(email):
            try:
                return User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                raise CommandError(f"找不到帳號 {email}")

        staff = get_user(options["staff"]) if options["staff"] else None
        members = [get_user(e) for e in options["members"]]

        with transaction.atomic():
            festival = self._festival()
            if staff:
                FestivalStaff.objects.update_or_create(festival=festival, user=staff, defaults={"role": "lead"})
            Submission.objects.filter(festival=festival, external_id__startswith="demo:").delete()
            demo = [self._demo_user(email, name) for email, name in DEMO_USERS]
            count = self._submissions(festival, members, demo, staff)

        self.stdout.write(self.style.SUCCESS(f"{festival.name}（{festival.date}）：建立 {count} 筆展示投稿"))
        if staff:
            self.stdout.write(f"排歌組（主排）：{staff.name}")

    def _festival(self) -> Festival:
        now = timezone.now()
        festival = Festival.active() or Festival.objects.create(
            name="測試場", date=timezone.localdate() + 14 * DAY, kind="hall",
        )
        festival.venue = festival.venue or "校史館大講堂"
        festival.start_time = festival.start_time or dt.time(10)
        festival.end_time = festival.end_time or dt.time(17)
        festival.report_deadline = now + 3 * DAY
        festival.partner_deadline = None
        festival.withdraw_deadline = now + 5 * DAY
        festival.upload_deadline = now + 7 * DAY
        festival.guest_deadline = now + 6 * DAY
        festival.partner_limit = 3
        festival.rules = festival.rules or RULES
        festival.guest_info = festival.guest_info or GUEST_INFO
        festival.guest_form_url = festival.guest_form_url or "https://forms.example.test/guest"
        festival.save()
        return festival

    def _demo_user(self, email, name) -> User:
        user, created = User.objects.get_or_create(email=email, defaults={"name": name, "is_active": True})
        if created:
            user.set_unusable_password()  # 只用來顯示，不能登入
            user.save()
        return user

    def _submissions(self, festival, members, demo, staff) -> int:
        now = timezone.now()
        member1, member2, partner = demo
        seq = iter(range(1, 1000))

        def add(user, source="member", **fields):
            sub = Submission.objects.create(
                festival=festival, source=source, submitter=user,
                editor_name=fields.pop("editor_name", user.name if user else ""),
                external_id=f"demo:{next(seq)}",
                attributes=fields.pop("attributes", ""),
                song_link=fields.pop("song_link", "https://example.test/song"),
                **fields,
            )
            return sub

        def uploaded(minutes, seconds, **extra):
            return {"file_link": "https://drive.example.test/file", "duration_seconds": minutes * 60 + seconds,
                    "uploaded_at": now - DAY, **extra}

        # 指定的真實帳號：每人幾首不同狀態的歌，登入後可以自己操作
        songs_for_members = [
            [dict(song_source="ぼっち・ざ・ろっく！", visual_source="ぼっち・ざ・ろっく！", title="星座になれたら",
                  artist="結束バンド", five_sec=True, attributes="樂團",
                  **uploaded(4, 25, five_sec_link="https://drive.example.test/5sec", five_sec_uploaded_at=now - DAY)),
             dict(song_source="ぼっち・ざ・ろっく！", visual_source="ぼっち・ざ・ろっく！", title="あのバンド",
                  artist="結束バンド", five_sec=True),
             dict(song_source="葬送のフリーレン", visual_source="葬送のフリーレン", title="勇者", artist="YOASOBI")],
            [dict(song_source="BanG Dream! It's MyGO!!!!!", visual_source="BanG Dream! It's MyGO!!!!!",
                  title="迷星叫", artist="MyGO!!!!!", **uploaded(4, 2))],
            [dict(song_source="一般曲", visual_source="複數作品", title="後來的我們", artist="五月天",
                  remarks="畫面有部分非 ACGN 素材")],
        ]
        for user, songs in zip(members, songs_for_members):
            for song in songs:
                add(user, **song)
        if staff and staff not in members:
            add(staff, song_source="チェンソーマン", visual_source="チェンソーマン", title="KICK BACK",
                artist="米津玄師", **uploaded(3, 13))

        # 展示帳號：各種排歌組會遇到的狀況
        add(member1, song_source="ヤニねこ", visual_source="ヤニねこ", title="なんもねえ", five_sec=True,
            attributes="喜劇", **uploaded(3, 11, five_sec_link="https://drive.example.test/5sec",
                                       five_sec_uploaded_at=now - DAY, file_updated_at=now - DAY / 2))
        add(member1, song_source="黄泉のツガイ", visual_source="黄泉のツガイ", title="飛ぶ時", withdrawn_at=now - DAY)
        first = add(member2, song_source="Rewrite", visual_source="Rewrite", title="Rewrite", **uploaded(5, 30))
        second = add(member2, song_source="Rewrite", visual_source="Rewrite", title="Philosophyz", **uploaded(5, 10))
        second.chain_with = first
        second.save(update_fields=["chain_with"])
        add(partner, source="partner", song_source="葬送のフリーレン", visual_source="葬送のフリーレン",
            title="晴る", artist="ヨルシカ")

        # 亂入曲：一首跟社內撞曲、一首上一場播過
        add(None, source="guest", editor_name="展示亂入投稿者", contact_email="guest1@example.test",
            song_source="ヤニねこ", visual_source="ヤニねこ", title="なんもねえ", song_link="",
            guest_message="第一次投稿，請多指教", library_consent=True,
            file_link="https://drive.example.test/guest1", uploaded_at=now - 2 * DAY)
        previous = festival.previous_hall_festival()
        played = Play.objects.filter(festival=previous).exclude(visual_source=Play.CREDITS_VISUAL).first() if previous else None
        if played:
            add(None, source="guest", editor_name="展示亂入投稿者", contact_email="guest2@example.test",
                song_source=played.song_source, visual_source=played.visual_source, title=played.title,
                song_link="", file_link="https://drive.example.test/guest2", uploaded_at=now - 2 * DAY)

        # 回報串閒聊
        target = Submission.objects.filter(festival=festival, external_id="demo:1").first()
        if target:
            SubmissionComment.objects.create(submission=target, user=member1, content="這首我也想剪，好險你先報了")
            SubmissionComment.objects.create(submission=target, user=member2, content="期待！")

        return Submission.objects.filter(festival=festival, external_id__startswith="demo:").count()
