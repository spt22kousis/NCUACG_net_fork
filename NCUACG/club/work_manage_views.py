# NCUACG/club/work_manage_views.py
"""
社課負責人在網站上架成果牆作品（掛在 /api/club/ 之下）。只能動自己社課的作品；幹部可以管全部。

  GET    works/manage/            我能管的分類、作品（含下架的）與可以連結的堂次
  POST   works/manage/            multipart：course、title、author、type、externalUrl / file、thumbnail、lesson、isPublished
  PATCH  works/manage/<id>/       同上，只送要改的欄位
  DELETE works/manage/<id>/
  POST   courses/manage/          新增成果牆分類 {category, name, color}

圖片作品上傳後會縮小並自動做縮圖；影片可以上傳檔案（上限 settings.CLUB_MAX_VIDEO_MB）或貼連結（YouTube 會內嵌播放）。
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .images import process_thumbnail, process_work_image
from .lessons import CATEGORY_NAMES, lead_categories
from .models import Course, Lesson, Work
from .views import _course_to_dict, _work_to_dict

VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".m4v")


def _forbidden():
    return Response({"detail": "只有這個社課的負責人或幹部可以上架作品"}, status=status.HTTP_403_FORBIDDEN)


def _manage_dict(work: Work) -> dict:
    return {**_work_to_dict(work), "isPublished": work.is_published, "externalUrl": work.external_url,
            "hasFile": bool(work.media_file), "category": work.course.category}


class WorkSerializer(serializers.Serializer):
    course = serializers.SlugRelatedField(slug_field="slug", queryset=Course.objects.all(), required=False)
    title = serializers.CharField(max_length=200, required=False)
    author = serializers.CharField(max_length=100, required=False, allow_blank=True)
    type = serializers.ChoiceField(choices=Work.TYPE_CHOICES, required=False)
    externalUrl = serializers.URLField(required=False, allow_blank=True)
    lesson = serializers.PrimaryKeyRelatedField(queryset=Lesson.objects.all(), required=False, allow_null=True)
    # multipart 表單沒送這個欄位時 DRF 會當成 False，所以要明確給預設值（修改時不會套用預設）
    isPublished = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        course = attrs.get("course") or getattr(self.instance, "course", None)
        if course is None:
            raise serializers.ValidationError({"course": "請選成果牆分類"})
        if course.category not in self.context["editable"]:
            raise serializers.ValidationError({"course": "你不是這個社課的負責人"})
        lesson = attrs.get("lesson", getattr(self.instance, "lesson", None))
        if lesson is not None and lesson.category != course.category:
            raise serializers.ValidationError({"lesson": "只能選同一個社課的堂次"})
        return attrs


def _apply(work: Work, data: dict, files) -> None:
    """把表單內容與上傳的檔案寫進 work（還沒存）。檔案有問題時丟 ValidationError。"""
    for field, attr in (("course", "course"), ("title", "title"), ("author", "author"), ("type", "media_type"),
                        ("externalUrl", "external_url"), ("lesson", "lesson"), ("isPublished", "is_published")):
        if field in data:
            setattr(work, attr, data[field])

    upload = files.get("file")
    if upload is not None:
        if work.media_type == "image":
            image, thumb = process_work_image(upload)
            work.media_file.save(image.name, image, save=False)
            work.thumbnail.save(thumb.name, thumb, save=False)
        else:
            if not upload.name.lower().endswith(VIDEO_EXTENSIONS):
                raise ValidationError("影片請用 MP4、WebM 或 MOV")
            if upload.size > settings.CLUB_MAX_VIDEO_MB * 1024 * 1024:
                raise ValidationError(f"影片太大了（上限 {settings.CLUB_MAX_VIDEO_MB} MB），請改貼 YouTube 連結")
            ext = upload.name.rsplit(".", 1)[-1].lower()
            work.media_file.save(f"{uuid.uuid4().hex}.{ext}", upload, save=False)
        work.external_url = ""
    elif data.get("externalUrl"):
        # 改成貼連結：原本上傳的檔案就不用了
        if work.media_file:
            work.media_file.delete(save=False)

    thumb_upload = files.get("thumbnail")
    if thumb_upload is not None:
        thumb = process_thumbnail(thumb_upload)
        work.thumbnail.save(thumb.name, thumb, save=False)

    if not work.media_file and not work.external_url:
        raise ValidationError("請上傳檔案，或貼上連結")


def _save(request, work: Work, partial: bool, editable: set):
    ser = WorkSerializer(work if work.pk else None, data=request.data, partial=partial, context={"editable": editable})
    ser.is_valid(raise_exception=True)
    try:
        _apply(work, ser.validated_data, request.FILES)
    except ValidationError as exc:
        return Response({"file": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    if not work.pk:
        work.uploaded_by = request.user
    work.save()
    return None


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def work_manage(request):
    categories = lead_categories(request.user)
    if not categories:
        return _forbidden()
    editable = set(categories)

    if request.method == "POST":
        work = Work()
        error = _save(request, work, partial=False, editable=editable)
        if error:
            return error
        return Response(_manage_dict(work), status=status.HTTP_201_CREATED)

    courses = Course.objects.filter(category__in=categories)
    works = (
        Work.objects.filter(course__category__in=categories)
        .select_related("course", "lesson")
        .order_by("-created_at")
    )
    lessons = Lesson.objects.filter(category__in=categories).order_by("-start_time")
    return Response({
        "categories": [{"id": code, "name": CATEGORY_NAMES[code]} for code in categories],
        "courses": [_course_to_dict(c) for c in courses],
        "works": [_manage_dict(w) for w in works],
        "lessons": [
            {"id": l.id, "category": l.category, "number": l.number, "title": l.title, "startTime": l.start_time.isoformat()}
            for l in lessons
        ],
        "maxVideoMb": settings.CLUB_MAX_VIDEO_MB,
    })


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def work_manage_detail(request, work_id: int):
    work = get_object_or_404(Work.objects.select_related("course", "lesson"), pk=work_id)
    editable = set(lead_categories(request.user))
    if work.course.category not in editable:
        return _forbidden()
    if request.method == "DELETE":
        for field in (work.media_file, work.thumbnail):
            if field:
                field.delete(save=False)
        work.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    error = _save(request, work, partial=True, editable=editable)
    if error:
        return error
    return Response(_manage_dict(work))


class CourseSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=Course.CATEGORY_CHOICES)
    name = serializers.CharField(max_length=100)
    color = serializers.ChoiceField(choices=Course.COLOR_CHOICES, default="blue")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def course_manage(request):
    """新增成果牆分類，例如每學期一個「115上」。網址代碼自動產生。"""
    ser = CourseSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    if data["category"] not in lead_categories(request.user):
        return _forbidden()
    course = Course.objects.create(
        slug=f"{data['category']}-{uuid.uuid4().hex[:8]}", name=data["name"].strip(),
        category=data["category"], color=data["color"],
    )
    return Response(_course_to_dict(course), status=status.HTTP_201_CREATED)
