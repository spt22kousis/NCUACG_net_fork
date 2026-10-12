# NCUACG/club/views.py
"""
成果牆 API（掛在 /api/club/ 之下）

  GET    courses/?category=seiyuu                    社課列表（含已上架作品數）
  GET    works/?course=<slug>&sort=time|popularity&order=desc|asc   course 必填
  POST   works/<id>/view/                            瀏覽數 +1（同一人同一件作品有冷卻時間）
  POST   works/<id>/like/     DELETE works/<id>/like/        按讚 / 收回（需登入）
  GET    works/<id>/comments/                        留言列表
  POST   works/<id>/comments/                        留言（需登入）
  POST   comments/<id>/like/  DELETE comments/<id>/like/     留言按讚 / 收回（需登入）

輸出欄位刻意對齊 frontend/src/pages/Works.tsx 的 Work / Comment 型別（camelCase）。
"""
from __future__ import annotations

from django.db import IntegrityError
from django.db.models import Count, Exists, F, OuterRef, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import Comment, CommentLike, Course, Work, WorkLike
from .serializers import CommentCreateSerializer


def _current_user(request):
    """已登入回傳 accounts.User，訪客回傳 None。"""
    return request.user if getattr(request.user, "is_authenticated", False) else None


# ── 輸出格式 ────────────────────────────────────────────────────────────────

def _course_to_dict(c: Course) -> dict:
    return {
        "id": c.slug,
        "name": c.name,
        "color": c.color,
        "category": c.category,
        # 前端用來決定預設選哪個社課（跳過「關於聲優社課」這類沒有作品的分類）
        "workCount": getattr(c, "work_count", 0),
    }


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
        # 留言本體改由 works/<id>/comments/ 另外抓，列表只帶數量
        "commentCount": getattr(w, "comment_count", 0),
        "createdAt": w.created_at.isoformat(),
    }


def _works_queryset(user):
    """帶好按讚數、留言數、是否已按讚的查詢，避免 N+1。"""
    works = (
        Work.objects.filter(is_published=True)
        .select_related("course")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", distinct=True),
        )
    )
    if user is not None:
        works = works.annotate(
            is_liked=Exists(WorkLike.objects.filter(work=OuterRef("pk"), user=user))
        )
    return works


def _comments_queryset(user):
    """帶好每則留言的讚數與是否已按讚。"""
    comments = Comment.objects.select_related("user").annotate(like_count=Count("likes", distinct=True))
    if user is not None:
        comments = comments.annotate(
            is_liked=Exists(CommentLike.objects.filter(comment=OuterRef("pk"), user=user))
        )
    return comments


class WorkViewThrottle(SimpleRateThrottle):
    """
    同一個人（登入看帳號、訪客看 IP）對同一件作品，冷卻時間內只算一次瀏覽。
    沒有這層，任何人用迴圈打 view/ 就能把瀏覽數灌到上萬，進而影響熱度排序。
    """

    scope = "work_view"
    rate = "1/hour"

    def get_cache_key(self, request, view):
        user = _current_user(request)
        ident = f"u{user.pk}" if user is not None else self.get_ident(request)
        work_id = view.kwargs.get("work_id")
        return self.cache_format % {"scope": self.scope, "ident": f"{ident}:{work_id}"}


# ── 讀取 ────────────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([AllowAny])
def course_list(request):
    qs = Course.objects.annotate(
        work_count=Count("works", filter=Q(works__is_published=True))
    )
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
    # 一定要指定社課：不帶的話等於把整站作品一次倒出來
    course = request.GET.get("course")
    if not course:
        return Response({"course": ["必須指定社課"]}, status=status.HTTP_400_BAD_REQUEST)
    qs = _works_queryset(_current_user(request)).filter(course__slug=course)

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
@throttle_classes([WorkViewThrottle])
def work_view(request, work_id: int):
    """
    瀏覽數 +1。用 F() 在資料庫端累加，兩個人同時看也不會少算。
    冷卻時間內重複送會回 429（前端忽略即可），見 WorkViewThrottle。
    """
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedOrReadOnly])
def work_comments(request, work_id: int):
    """GET 任何人都能看留言；POST 留言需登入。"""
    work = get_object_or_404(Work, pk=work_id, is_published=True)
    if request.method == "GET":
        comments = _comments_queryset(_current_user(request)).filter(work=work)
        return Response([_comment_to_dict(c) for c in comments])

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
