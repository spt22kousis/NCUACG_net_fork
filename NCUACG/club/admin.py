# NCUACG/club/admin.py
from django.contrib import admin
from django.db.models import Count

from .lessons import discord_text
from .models import Comment, Course, CourseLead, Lesson, Photo, Work


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
        (None, {"fields": ("course", "title", "author", "media_type", "lesson", "is_published")}),
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


@admin.register(CourseLead)
class CourseLeadAdmin(admin.ModelAdmin):
    """每個社課固定指定幾位負責人，他們登入網站後可以發、改自己社課的公告。"""

    list_display = ("category", "user")
    list_filter = ("category",)
    search_fields = ("user__name", "user__email")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "number", "start_time", "location", "is_published")
    list_filter = ("category", "is_published")
    search_fields = ("title", "content")
    date_hierarchy = "start_time"
    filter_horizontal = ("requires",)
    readonly_fields = ("discord_preview", "created_by", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("category", "number", "title", "start_time", "end_time", "location", "is_published")}),
        ("公告內容", {"fields": ("content", "notes", "prerequisites", "requires", "discord_role", "discord_preview")}),
        ("課後", {"fields": ("slides_url",)}),
        ("紀錄", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    @admin.display(description="Discord 公告預覽")
    def discord_preview(self, obj):
        from django.utils.html import format_html

        return format_html('<pre style="white-space:pre-wrap">{}</pre>', discord_text(obj)) if obj.pk else "-"


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    """照片請負責人在網站上傳（會自動縮小、去掉 GPS）；後台只用來查看與刪除。"""

    list_display = ("preview", "group", "taken_on", "lesson", "caption", "uploaded_by")
    list_filter = ("kind", "category", "festival")
    search_fields = ("caption", "topic")
    date_hierarchy = "taken_on"
    fields = ("preview", "kind", "category", "lesson", "festival", "topic", "taken_on", "caption", "uploaded_by", "created_at")
    readonly_fields = ("preview", "uploaded_by", "created_at")

    def has_add_permission(self, request):
        return False

    @admin.display(description="歸屬")
    def group(self, obj):
        return obj.group_label

    @admin.display(description="照片")
    def preview(self, obj):
        from django.utils.html import format_html

        from .photo_views import file_url

        return format_html('<img src="{}" style="height:80px">', file_url(obj, thumb=True)) if obj.pk else "-"
