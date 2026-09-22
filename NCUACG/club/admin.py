# NCUACG/club/admin.py
from django.contrib import admin
from django.db.models import Count

from .models import Comment, Course, Work


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "category", "color", "order")
    list_editable = ("order",)
    list_filter = ("category",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("user", "content", "created_at")
    readonly_fields = ("user", "content", "created_at")
    can_delete = True  # 幹部可以直接在作品頁刪掉不當留言


@admin.register(Work)
class WorkAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "author", "media_type", "like_total", "views", "is_published", "created_at")
    list_filter = ("is_published", "media_type", "course__category", "course")
    search_fields = ("title", "author")
    list_editable = ("is_published",)
    readonly_fields = ("views", "created_at")
    inlines = [CommentInline]
    fieldsets = (
        (None, {"fields": ("course", "title", "author", "media_type", "is_published")}),
        ("媒體（上傳檔案或填外部網址，擇一）", {"fields": ("media_file", "external_url", "thumbnail")}),
        ("統計", {"fields": ("views", "created_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_like_total=Count("likes"))

    @admin.display(description="讚", ordering="_like_total")
    def like_total(self, obj):
        return obj._like_total


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("user", "work", "short_content", "created_at")
    list_filter = ("work__course",)
    search_fields = ("content", "user__name")
    readonly_fields = ("user", "work", "content", "created_at")

    @admin.display(description="內容")
    def short_content(self, obj):
        return obj.content[:40]
