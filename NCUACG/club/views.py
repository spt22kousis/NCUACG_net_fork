# NCUACG/club/views.py
"""
成果牆 API（掛在 /api/club/ 之下）

  GET    courses/?category=seiyuu                    社課列表
  GET    works/?course=<slug>&sort=time|popularity&order=desc|asc
  POST   works/<id>/view/                            瀏覽數 +1
  POST   works/<id>/like/     DELETE works/<id>/like/        按讚 / 收回（需登入）
  POST   works/<id>/comments/                        留言（需登入）
  POST   comments/<id>/like/  DELETE comments/<id>/like/     留言按讚 / 收回（需登入）

輸出欄位刻意對齊 frontend/src/pages/Works.tsx 的 Work / Comment 型別（camelCase）。
"""
from __future__ import annotations

from django.db import IntegrityError
from django.db.models import Count, Exists, F, OuterRef, Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Comment, CommentLike, Course, Work, WorkLike
from .serializers import CommentCreateSerializer


def _current_user(request):
    """已登入回傳 accounts.User，訪客回傳 None。"""
    return request.user if getattr(request.user, "is_authenticated", False) else None


# ── 輸出格式 ────────────────────────────────────────────────────────────────

def _course_to_dict(c: Course) -> dict:
    return {"id": c.slug, "name": c.name, "color": c.color, "category": c.category}


def _comment_to_dict(c: Comment) -> dict:
    return {
        "id": c.id,
        "username": c.user.name,
        "content": c.content,
        "likes": getattr(c, "like_count", 0),
        "isLiked": bool(getattr(c, "is_liked", False)),
        "createdAt": c.created_at.isoformat(),
    }


def _work_to_dict(w: Work) -> dict:
    return {
        "id": w.id,
        "course": w.course.slug,
        "title": w.title,
        "author": w.author,
        "type": w.media_type,
        "url": w.media_url,
        "thumbnail": w.thumbnail.url if w.thumbnail else None,
        "likes": getattr(w, "like_count", 0),
        "views": w.views,
        "isLiked": bool(getattr(w, "is_liked", False)),
        "comments": [_comment_to_dict(c) for c in w.comments.all()],
        "createdAt": w.created_at.isoformat(),
    }


def _works_queryset(user):
    """帶好按讚數、是否已按讚、留言（含留言的讚）的查詢，避免 N+1。"""
    comments = Comment.objects.select_related("user").annotate(like_count=Count("likes", distinct=True))
    works = (
        Work.objects.filter(is_published=True)
        .select_related("course")
        .annotate(like_count=Count("likes", distinct=True))
    )
    if user is not None:
        comments = comments.annotate(
            is_liked=Exists(CommentLike.objects.filter(comment=OuterRef("pk"), user=user))
        )
        works = works.annotate(
            is_liked=Exists(WorkLike.objects.filter(work=OuterRef("pk"), user=user))
        )
    return works.prefetch_related(Prefetch("comments", queryset=comments))


# ── 讀取 ────────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def course_list(request):
    qs = Course.objects.all()
    category = request.GET.get("category")
    if category:
        qs = qs.filter(category=category)
    return Response([_course_to_dict(c) for c in qs])


@api_view(["GET"])
@permission_classes([AllowAny])
def work_list(request):
    """
    sort=time（預設）依上架時間；sort=popularity 依按讚數，同分再比瀏覽數。
    order=desc（預設）/ asc。
    """
    qs = _works_queryset(_current_user(request))

    course = request.GET.get("course")
    if course:
        qs = qs.filter(course__slug=course)

    sort = request.GET.get("sort", "time")
    desc = request.GET.get("order", "desc") != "asc"
    if sort == "popularity":
        fields = ["like_count", "views", "created_at"]
    else:
        fields = ["created_at"]
    # 最後加上 id 當作穩定的排序依據，避免同分時順序亂跳
    ordering = [f"-{f}" if desc else f for f in fields] + (["-id"] if desc else ["id"])

    return Response([_work_to_dict(w) for w in qs.order_by(*ordering)])


# ── 互動 ────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def work_view(request, work_id: int):
    """瀏覽數 +1。用 F() 在資料庫端累加，兩個人同時看也不會少算。"""
    updated = Work.objects.filter(pk=work_id, is_published=True).update(views=F("views") + 1)
    if not updated:
        return Response({"detail": "找不到這件作品"}, status=status.HTTP_404_NOT_FOUND)
    return Response({"views": Work.objects.values_list("views", flat=True).get(pk=work_id)})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def work_like(request, work_id: int):
    """POST 按讚、DELETE 收回。兩者都是冪等的：重複送不會多算或變成反向。"""
    work = get_object_or_404(Work, pk=work_id, is_published=True)
    if request.method == "POST":
        try:
            WorkLike.objects.get_or_create(work=work, user=request.user)
        except IntegrityError:
            pass  # 同時送兩次時，另一個請求已經建好了
    else:
        WorkLike.objects.filter(work=work, user=request.user).delete()

    return Response({
        "likes": WorkLike.objects.filter(work=work).count(),
        "isLiked": request.method == "POST",
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def work_comment_create(request, work_id: int):
    work = get_object_or_404(Work, pk=work_id, is_published=True)
    ser = CommentCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    comment = Comment.objects.create(work=work, user=request.user, content=ser.validated_data["content"])
    comment.like_count = 0
    comment.is_liked = False
    return Response(_comment_to_dict(comment), status=status.HTTP_201_CREATED)


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def comment_like(request, comment_id: int):
    comment = get_object_or_404(Comment, pk=comment_id, work__is_published=True)
    if request.method == "POST":
        try:
            CommentLike.objects.get_or_create(comment=comment, user=request.user)
        except IntegrityError:
            pass
    else:
        CommentLike.objects.filter(comment=comment, user=request.user).delete()

    return Response({
        "likes": CommentLike.objects.filter(comment=comment).count(),
        "isLiked": request.method == "POST",
    })
