# NCUACG/club/lesson_views.py
"""
社課堂次與公告 API（掛在 /api/club/ 之下）。權限與公告文字在 lessons.py。

公開
  GET    lessons/?category=railway                某社課所有公開的堂次
  GET    lessons/?days=30                         還沒結束、N 天內開始的堂次（首頁公告欄）
  GET    lessons/?from=2026-10-01&to=2026-11-01   某段期間（行事曆），to 不含
  GET    lessons/<id>/                            一堂社課

社課負責人（幹部可以管全部社課）
  GET    lessons/manage/                          我能管的社課與堂次（含未公開、Discord 公告文字）
  POST   lessons/manage/                          新增一堂
  PATCH  lessons/<id>/                            修改（例如課後補簡報連結）
  DELETE lessons/<id>/
"""
from __future__ import annotations

import datetime as dt

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .lessons import CATEGORY_NAMES, discord_text, lead_categories
from .models import Lesson

# 行事曆一次最多抓的天數，避免整個資料庫被一次倒出來
MAX_RANGE_DAYS = 62


def _iso(value):
    return value.isoformat() if value else None


def lesson_to_dict(lesson: Lesson, editable=frozenset()) -> dict:
    """editable：這個人能管的社課種類（lead_categories），能管的才帶公告文字與未公開狀態。"""
    data = {
        "id": lesson.id,
        "category": lesson.category,
        "categoryName": CATEGORY_NAMES.get(lesson.category, lesson.category),
        "number": lesson.number,
        "title": lesson.title,
        "startTime": _iso(lesson.start_time),
        "endTime": _iso(lesson.end_time),
        "location": lesson.location,
        "content": lesson.content,
        "notes": lesson.notes,
        "prerequisites": lesson.prerequisites,
        "requires": [
            {"id": r.id, "number": r.number, "title": r.title}
            for r in lesson.requires.all()
        ],
        "slidesUrl": lesson.slides_url,
    }
    if lesson.category in editable:
        data.update({
            "discordRole": lesson.discord_role,
            "isPublished": lesson.is_published,
            "discordText": discord_text(lesson),
            "canEdit": True,
        })
    return data


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        day = dt.date.fromisoformat(value)
    except ValueError:
        return None
    return timezone.make_aware(dt.datetime.combine(day, dt.time.min))


def _editable(request) -> set[str]:
    return set(lead_categories(request.user))


# ── 公開 ────────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def lesson_list(request):
    qs = Lesson.objects.filter(is_published=True).prefetch_related("requires")
    category = request.GET.get("category")
    if category:
        qs = qs.filter(category=category)

    start, end = _parse_date(request.GET.get("from")), _parse_date(request.GET.get("to"))
    if start or end:
        if not (start and end) or end <= start or (end - start).days > MAX_RANGE_DAYS:
            return Response(
                {"detail": f"from 與 to 都要填，而且最多相隔 {MAX_RANGE_DAYS} 天"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = qs.filter(start_time__gte=start, start_time__lt=end)
    elif "days" in request.GET or not category:
        # 跟活動公告一樣：還沒結束的（進行中的也算），而且 N 天內開始
        try:
            days = min(max(int(request.GET.get("days", 30)), 1), 365)
        except ValueError:
            days = 30
        now = timezone.now()
        not_ended = Q(end_time__gte=now) | Q(end_time__isnull=True, start_time__gte=now)
        qs = qs.filter(not_ended, start_time__lte=now + dt.timedelta(days=days))

    editable = _editable(request)
    return Response([lesson_to_dict(lesson, editable) for lesson in qs])


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def lesson_detail(request, lesson_id: int):
    lesson = get_object_or_404(Lesson.objects.prefetch_related("requires"), pk=lesson_id)
    editable = _editable(request)
    can_edit = lesson.category in editable

    if request.method == "GET":
        if not lesson.is_published and not can_edit:
            return Response({"detail": "找不到這堂社課"}, status=status.HTTP_404_NOT_FOUND)
        return Response(lesson_to_dict(lesson, editable))

    if not request.user.is_authenticated:
        return Response({"detail": "請先登入"}, status=status.HTTP_401_UNAUTHORIZED)
    if not can_edit:
        return Response({"detail": "只有這個社課的負責人或幹部可以修改"}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "DELETE":
        lesson.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    ser = LessonSerializer(lesson, data=request.data, partial=True, context={"request": request})
    ser.is_valid(raise_exception=True)
    lesson = ser.save()
    return Response(lesson_to_dict(lesson, editable))


# ── 社課負責人 ──────────────────────────────────────────────────────────────

class LessonSerializer(serializers.ModelSerializer):
    startTime = serializers.DateTimeField(source="start_time")
    endTime = serializers.DateTimeField(source="end_time", required=False, allow_null=True)
    discordRole = serializers.CharField(source="discord_role", required=False, allow_blank=True, max_length=50)
    slidesUrl = serializers.URLField(source="slides_url", required=False, allow_blank=True)
    isPublished = serializers.BooleanField(source="is_published", required=False)
    requires = serializers.PrimaryKeyRelatedField(many=True, required=False, queryset=Lesson.objects.all())

    class Meta:
        model = Lesson
        fields = [
            "category", "number", "title", "startTime", "endTime", "location",
            "content", "notes", "prerequisites", "requires", "discordRole", "slidesUrl", "isPublished",
        ]

    def validate_category(self, value):
        if value not in lead_categories(self.context["request"].user):
            raise serializers.ValidationError("你不是這個社課的負責人")
        return value

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end < start:
            raise serializers.ValidationError({"endTime": "結束時間不能早於開始時間"})

        category = attrs.get("category", getattr(self.instance, "category", None))
        for other in attrs.get("requires", []):
            if other.category != category or (self.instance and other.pk == self.instance.pk):
                raise serializers.ValidationError({"requires": "只能選同一個社課的其他堂次"})
        return attrs


def _defaults(categories: list[str]) -> dict:
    """新增堂次時的預設值：沿用該社課上一堂的地點與身分組，第幾堂接著編。"""
    result = {}
    for code in categories:
        lessons = Lesson.objects.filter(category=code).order_by("-start_time", "-id")
        last = lessons.first()
        role = lessons.exclude(discord_role="").values_list("discord_role", flat=True).first()
        result[code] = {
            "location": last.location if last else "社辦",
            "discordRole": role or f"@{CATEGORY_NAMES[code]}社課通知",
            "nextNumber": (last.number or 0) + 1 if last else 1,
        }
    return result


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def lesson_manage(request):
    categories = lead_categories(request.user)
    if not categories:
        return Response({"detail": "只有社課負責人或幹部可以使用"}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "POST":
        ser = LessonSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        lesson = ser.save(created_by=request.user)
        return Response(lesson_to_dict(lesson, set(categories)), status=status.HTTP_201_CREATED)

    lessons = (
        Lesson.objects.filter(category__in=categories)
        .prefetch_related("requires")
        .order_by("-start_time", "-id")
    )
    return Response({
        "categories": [{"id": code, "name": CATEGORY_NAMES[code]} for code in categories],
        "defaults": _defaults(categories),
        "lessons": [lesson_to_dict(lesson, set(categories)) for lesson in lessons],
    })

