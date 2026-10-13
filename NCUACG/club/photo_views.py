# NCUACG/club/photo_views.py
"""
社團照片 API（掛在 /api/club/ 之下）。照片只給登入的社員看。

照片有三種歸屬（見 models.Photo）：
  社課     category 必填、lesson 選填；該社課的負責人上傳
  歌謠祭   festival 必填；該場的排歌組上傳
  日常     topic 必填（社遊、聚餐…）；幹部上傳
幹部什麼都能傳。

登入的社員
  GET    photos/?kind=&category=&lesson=&festival=&topic=&page=1&limit=60   照片列表（新的在前）

上傳者
  POST   photos/                multipart：image、kind、category / lesson / festival / topic、takenOn、caption
  PATCH  photos/<id>/           改歸屬、拍攝日期、說明
  DELETE photos/<id>/

檔案
  GET    photos/file/<token>/   照片或縮圖。<img> 不會帶登入資訊，所以列表回傳的網址帶簽章，
                                當天與隔天有效；沒有簽章或過期就拿不到。
"""
from __future__ import annotations

import time

from django.core import signing
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from songfest.models import Festival, FestivalStaff

from .images import process_photo
from .lessons import CATEGORY_NAMES, is_officer, lead_categories
from .models import Course, Lesson, Photo

PAGE_SIZE = 60
_signer = signing.Signer(salt="club.photo-file")


# ── 權限 ────────────────────────────────────────────────────────────────────

class Uploader:
    """一個人可以傳哪些照片。一次查好，列表裡每張照片判斷 canEdit 時不用再查資料庫。"""

    def __init__(self, user):
        self.officer = is_officer(user)
        self.categories = set(lead_categories(user))
        self.festival_ids = set(
            FestivalStaff.objects.filter(user=user).values_list("festival_id", flat=True)
        ) if user.is_authenticated else set()

    def can(self, kind: str, category: str = "", festival_id: int | None = None) -> bool:
        if self.officer:
            return True
        if kind == "lesson":
            return category in self.categories
        if kind == "songfest":
            return festival_id in self.festival_ids
        return False  # 日常只有幹部

    def can_edit(self, photo: Photo) -> bool:
        return self.can(photo.kind, photo.category, photo.festival_id)

    @property
    def anything(self) -> bool:
        return self.officer or bool(self.categories) or bool(self.festival_ids)

    def options(self) -> dict:
        """前端上傳區的選項。"""
        festivals = Festival.objects.all() if self.officer else Festival.objects.filter(pk__in=self.festival_ids)
        topics = Photo.objects.filter(kind="daily").exclude(topic="").values_list("topic", flat=True).distinct()
        return {
            "categories": [{"id": code, "name": name} for code, name in CATEGORY_NAMES.items() if code in self.categories],
            "festivals": [{"id": f.id, "name": f.name, "date": f.date.isoformat()} for f in festivals.order_by("-date")[:20]],
            "daily": self.officer,
            "topics": sorted(set(topics)),
        }


# ── 輸出 ────────────────────────────────────────────────────────────────────

def _today_bucket() -> int:
    return int(time.time() // 86400)


def file_url(photo: Photo, thumb: bool = False) -> str:
    """帶簽章的檔案網址。同一天產生的網址都一樣，瀏覽器可以快取。"""
    token = _signer.sign(f"{photo.pk}.{'t' if thumb else 'f'}.{_today_bucket()}")
    return reverse("club_photo_file", args=[token])


def photo_to_dict(photo: Photo, uploader: Uploader | None = None) -> dict:
    lesson, festival = photo.lesson, photo.festival
    return {
        "id": photo.id,
        "kind": photo.kind,
        "category": photo.category,
        "lesson": {"id": lesson.id, "number": lesson.number, "title": lesson.title} if lesson else None,
        "festival": {"id": festival.id, "name": festival.name} if festival else None,
        "topic": photo.topic,
        "groupLabel": photo.group_label,
        "caption": photo.caption,
        "takenOn": photo.taken_on.isoformat(),
        "width": photo.width,
        "height": photo.height,
        "url": file_url(photo),
        "thumbUrl": file_url(photo, thumb=True),
        "canEdit": bool(uploader and uploader.can_edit(photo)),
    }


def _forbidden():
    return Response({"detail": "你沒有權限上傳或修改這類照片"}, status=status.HTTP_403_FORBIDDEN)


# ── 驗證 ────────────────────────────────────────────────────────────────────

class PhotoSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Photo.KIND_CHOICES, required=False)
    category = serializers.ChoiceField(choices=Course.CATEGORY_CHOICES, required=False, allow_blank=True)
    lesson = serializers.PrimaryKeyRelatedField(queryset=Lesson.objects.all(), required=False, allow_null=True)
    festival = serializers.PrimaryKeyRelatedField(queryset=Festival.objects.all(), required=False, allow_null=True)
    topic = serializers.CharField(max_length=50, required=False, allow_blank=True)
    takenOn = serializers.DateField(required=False)
    caption = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        """把歸屬整理成完整的一組（換歸屬時，別種的欄位清掉），並檢查權限。"""
        instance: Photo | None = self.instance
        kind = attrs.get("kind") or (instance.kind if instance else "lesson")
        pick = lambda key, current: attrs[key] if key in attrs else (current if instance and instance.kind == kind else None)  # noqa: E731
        category = pick("category", instance and instance.category) or ""
        lesson = pick("lesson", instance and instance.lesson)
        festival = pick("festival", instance and instance.festival)
        topic = (pick("topic", instance and instance.topic) or "").strip()

        if kind == "lesson":
            if not category:
                raise serializers.ValidationError({"category": "請選社課"})
            if lesson is not None and lesson.category != category:
                raise serializers.ValidationError({"lesson": "只能選同一個社課的堂次"})
            festival, topic = None, ""
        elif kind == "songfest":
            if festival is None:
                raise serializers.ValidationError({"festival": "請選歌謠祭場次"})
            category, lesson, topic = "", None, ""
        else:
            if not topic:
                raise serializers.ValidationError({"topic": "請填分類，例如社遊"})
            category, lesson, festival = "", None, None

        if not self.context["uploader"].can(kind, category, festival.id if festival else None):
            raise serializers.ValidationError({"kind": "你沒有權限上傳這類照片"})
        return {**attrs, "kind": kind, "category": category, "lesson": lesson, "festival": festival, "topic": topic}


def _default_date(data: dict):
    if data.get("takenOn"):
        return data["takenOn"]
    if data["lesson"] is not None:
        return timezone.localtime(data["lesson"].start_time).date()
    if data["festival"] is not None:
        return data["festival"].date
    return timezone.localdate()


# ── API ─────────────────────────────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def photo_list(request):
    uploader = Uploader(request.user)

    if request.method == "POST":
        if not uploader.anything:
            return _forbidden()
        upload = request.FILES.get("image")
        if upload is None:
            return Response({"image": ["請選照片"]}, status=status.HTTP_400_BAD_REQUEST)
        ser = PhotoSerializer(data=request.data, context={"uploader": uploader})
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            full, thumb, width, height = process_photo(upload, data["kind"])
        except ValidationError as exc:
            return Response({"image": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        photo = Photo(
            kind=data["kind"], category=data["category"], lesson=data["lesson"], festival=data["festival"],
            topic=data["topic"], caption=data.get("caption", ""), taken_on=_default_date(data),
            width=width, height=height, uploaded_by=request.user,
        )
        photo.image.save(full.name, full, save=False)
        photo.thumbnail.save(thumb.name, thumb, save=False)
        photo.save()
        return Response(photo_to_dict(photo, uploader), status=status.HTTP_201_CREATED)

    qs = Photo.objects.select_related("lesson", "festival")
    for param, field in (("kind", "kind"), ("category", "category"), ("topic", "topic")):
        if request.GET.get(param):
            qs = qs.filter(**{field: request.GET[param]})
    for param in ("lesson", "festival"):
        if request.GET.get(param, "").isdigit():
            qs = qs.filter(**{f"{param}_id": int(request.GET[param])})
    try:
        page = max(int(request.GET.get("page", 1)), 1)
        limit = min(max(int(request.GET.get("limit", PAGE_SIZE)), 1), PAGE_SIZE)
    except ValueError:
        page, limit = 1, PAGE_SIZE
    total = qs.count()
    photos = qs[(page - 1) * limit: page * limit]
    return Response({
        "photos": [photo_to_dict(p, uploader) for p in photos],
        "total": total,
        "hasMore": page * limit < total,
        # 篩選用：目前有照片的日常分類
        "topics": sorted(set(Photo.objects.filter(kind="daily").values_list("topic", flat=True))),
        # 上傳區的選項；什麼都不能傳就是 null
        "upload": uploader.options() if uploader.anything else None,
    })


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def photo_detail(request, photo_id: int):
    photo = get_object_or_404(Photo.objects.select_related("lesson", "festival"), pk=photo_id)
    uploader = Uploader(request.user)
    if not uploader.can_edit(photo):
        return _forbidden()
    if request.method == "DELETE":
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    ser = PhotoSerializer(photo, data=request.data, partial=True, context={"uploader": uploader})
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    for field in ("kind", "category", "lesson", "festival", "topic"):
        setattr(photo, field, data[field])
    if "takenOn" in data:
        photo.taken_on = data["takenOn"]
    if "caption" in data:
        photo.caption = data["caption"]
    photo.save()
    return Response(photo_to_dict(photo, uploader))


@api_view(["GET"])
@permission_classes([AllowAny])
def photo_file(request, token: str):
    try:
        photo_id, kind, bucket = _signer.unsign(token).split(".")
        expired = _today_bucket() - int(bucket) not in (0, 1)
    except (signing.BadSignature, ValueError):
        raise Http404
    if expired:
        raise Http404
    photo = get_object_or_404(Photo, pk=int(photo_id))
    field = photo.thumbnail if kind == "t" else photo.image
    try:
        response = FileResponse(field.open("rb"), content_type="image/jpeg")
    except FileNotFoundError:
        raise Http404
    # 只讓使用者自己的瀏覽器快取，不讓中間的代理伺服器存
    response["Cache-Control"] = "private, max-age=86400"
    return response
