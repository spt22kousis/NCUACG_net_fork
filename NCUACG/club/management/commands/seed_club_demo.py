# NCUACG/club/management/commands/seed_club_demo.py
"""
建立成果牆的示範作品，方便本機測試版面（DEBUG=False 時拒絕執行）。

  python manage.py seed_club_demo            每個社課建立一個「示範作品」分類，各放幾件佔位圖片
  python manage.py seed_club_demo --clear    刪掉示範分類、作品與圖片檔

- 分類的網址代碼以 demo- 開頭，排在列表最下面；作品標題以「［示範］」開頭，一看就知道不是真的作品。
- 佔位圖片用 Pillow 產生（社課名稱＋編號），存在 media/works/ 底下，--clear 會一起刪掉。
- 可以重複執行：會先刪掉上次建立的示範作品再重建。
"""
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageDraw, ImageFont

from club.models import Course, Work

DEMO_PREFIX = "demo-"
TITLE_PREFIX = "［示範］"
WORKS_PER_COURSE = 3

# 每個社課一個底色，跟網站的米色、黑框風格搭
COLORS = {
    "anime": "#93C5FD", "otaku": "#FCA5A5", "model": "#FDBA74", "art": "#F9A8D4",
    "trpg": "#C4B5FD", "mv": "#86EFAC", "seiyuu": "#FDE68A", "railway": "#A5B4FC",
}

# 有中文字型就用（Windows 的微軟正黑體、Linux 的 Noto CJK），沒有就只畫英文代碼
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msjhbd.ttc", "C:/Windows/Fonts/msjh.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/System/Library/Fonts/PingFang.ttc",
]


def _font(size):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size), True
        except OSError:
            continue
    return ImageFont.load_default(), False


def placeholder(code: str, name: str, number: int, size=(1280, 720)) -> bytes:
    """畫一張佔位圖：社課底色、黑色粗框、中間寫「社課名稱 示範作品 N」。"""
    image = Image.new("RGB", size, COLORS.get(code, "#EFE7DC"))
    draw = ImageDraw.Draw(image)
    w, h = size
    draw.rectangle([24, 24, w - 24, h - 24], outline="#1f2937", width=12)
    draw.rectangle([w // 2 - 340, h // 2 - 150, w // 2 + 340, h // 2 + 150], fill="#FFFFFF", outline="#1f2937", width=8)
    font, has_cjk = _font(64)
    small, _ = _font(40)
    title = f"{name} 示範作品" if has_cjk else f"{code} demo"
    for text, f, y in ((title, font, h // 2 - 50), (f"#{number}", small, h // 2 + 50)):
        box = draw.textbbox((0, 0), text, font=f)
        draw.text(((w - (box[2] - box[0])) / 2, y - (box[3] - box[1]) / 2), text, fill="#1f2937", font=f)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def thumbnail(data: bytes) -> bytes:
    image = Image.open(BytesIO(data))
    image.thumbnail((480, 480))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def _delete_works(works) -> int:
    count = 0
    for work in works:
        for field in (work.media_file, work.thumbnail):
            if field:
                field.delete(save=False)
        work.delete()
        count += 1
    return count


class Command(BaseCommand):
    help = "建立成果牆的示範作品（只在本機開發用）"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="刪掉示範分類、作品與圖片檔")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("這個指令只能在本機開發（DJANGO_DEBUG=True）時使用")

        demo_courses = Course.objects.filter(slug__startswith=DEMO_PREFIX)
        if options["clear"]:
            removed = _delete_works(Work.objects.filter(course__in=demo_courses))
            courses = demo_courses.count()
            demo_courses.delete()
            self.stdout.write(self.style.SUCCESS(f"已刪除 {courses} 個示範分類、{removed} 件示範作品"))
            return

        with transaction.atomic():
            _delete_works(Work.objects.filter(course__in=demo_courses, title__startswith=TITLE_PREFIX))
            created = 0
            for code, name in Course.CATEGORY_CHOICES:
                course, _ = Course.objects.update_or_create(
                    slug=f"{DEMO_PREFIX}{code}",
                    defaults={"name": "示範作品", "category": code, "color": "green", "order": 999},
                )
                for number in range(1, WORKS_PER_COURSE + 1):
                    data = placeholder(code, name, number)
                    work = Work(course=course, title=f"{TITLE_PREFIX}{name}作品 {number}", author="示範", media_type="image")
                    work.media_file.save(f"demo-{code}-{number}.jpg", ContentFile(data), save=False)
                    work.thumbnail.save(f"demo-{code}-{number}_thumb.jpg", ContentFile(thumbnail(data)), save=False)
                    work.save()
                    created += 1
        self.stdout.write(self.style.SUCCESS(
            f"已建立 {len(Course.CATEGORY_CHOICES)} 個示範分類、{created} 件示範作品；用 --clear 可以全部刪掉"
        ))
