# NCUACG/club/lessons.py
"""社課堂次的權限判斷與 Discord 公告文字。API 在 lesson_views.py。"""
from __future__ import annotations

from django.utils import timezone

from .models import Course, CourseLead, Lesson

CATEGORY_NAMES = dict(Course.CATEGORY_CHOICES)

# 公告的分隔線，跟社課負責人平常在 Discord 貼的一樣長
DISCORD_DIVIDER = "-" * 72


def is_officer(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def lead_categories(user) -> list[str]:
    """這個人可以發公告的社課種類：幹部全部都可以，其他人看後台指定的負責人。"""
    if not (user and user.is_authenticated):
        return []
    if is_officer(user):
        return [code for code, _ in Course.CATEGORY_CHOICES]
    mine = set(CourseLead.objects.filter(user=user).values_list("category", flat=True))
    return [code for code, _ in Course.CATEGORY_CHOICES if code in mine]


def can_manage_lessons(user) -> bool:
    """側邊欄要不要顯示「管理社課公告」。"""
    return is_officer(user) or bool(user and user.is_authenticated and CourseLead.objects.filter(user=user).exists())


def _local(value):
    return timezone.localtime(value) if value else None


def time_range(lesson: Lesson) -> str:
    """10/12 18:00~20:00；跨日才把結束日期也寫出來。"""
    start = _local(lesson.start_time)
    text = f"{start.month}/{start.day} {start:%H:%M}"
    end = _local(lesson.end_time)
    if end:
        same_day = end.date() == start.date()
        text += f"~{end:%H:%M}" if same_day else f"~{end.month}/{end.day} {end:%H:%M}"
    return text


def discord_text(lesson: Lesson) -> str:
    """照社課負責人在 Discord 發公告的格式產生文字，給「一鍵複製」用。"""
    lines = [
        f"【{CATEGORY_NAMES.get(lesson.category, lesson.category)}社課】",
        f"時間：{time_range(lesson)}",
        f"地點：{lesson.location}",
        f"內容：{lesson.title}",
    ]
    if lesson.content.strip():
        lines.append(lesson.content.strip())

    after = []
    if lesson.notes.strip():
        after.append(lesson.notes.strip())
    prereq = [line.strip() for line in lesson.prerequisites.splitlines() if line.strip()]
    required = [f"《{r.title}》" for r in lesson.requires.order_by("start_time")]
    if required:
        prereq.append(f"參加過前面的社課（{'、'.join(required)}）")
    if prereq:
        after.append("\n".join(["建議具備", *prereq]))
    if after:
        lines.append(DISCORD_DIVIDER)
        lines.extend(after)

    if lesson.discord_role.strip():
        lines.append(lesson.discord_role.strip())
    return "\n".join(lines)
