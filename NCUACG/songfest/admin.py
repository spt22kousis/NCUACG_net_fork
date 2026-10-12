# NCUACG/songfest/admin.py
from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.template.response import TemplateResponse
from django.urls import path

from .importers import SpreadsheetError, import_songfest
from .models import Festival, FestivalStaff, Play, Submission, SubmissionComment, Track


class FestivalStaffInline(admin.TabularInline):
    # 帳號用一般下拉選單：搜尋式選單需要「帳號」的查看權限，幹部沒有
    model = FestivalStaff
    extra = 1


@admin.register(Festival)
class FestivalAdmin(admin.ModelAdmin):
    list_display = ("name", "date", "kind", "venue", "play_total", "is_published")
    list_filter = ("kind", "is_published")
    search_fields = ("name", "venue")
    date_hierarchy = "date"
    inlines = [FestivalStaffInline]
    fieldsets = (
        (None, {"fields": ("name", "date", "kind", "is_published")}),
        ("時間地點", {"fields": ("venue", "start_time", "end_time")}),
        ("公告", {"fields": ("description",)}),
        ("新曲投稿（沒填報曲截止就不開放投稿）", {
            "fields": ("report_deadline", "partner_deadline", "withdraw_deadline", "upload_deadline",
                       "partner_name", "partner_limit", "rules"),
        }),
        ("亂入曲", {"fields": ("guest_deadline", "guest_form_url", "guest_info")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_play_total=Count("plays"))

    @admin.display(description="播放紀錄", ordering="_play_total")
    def play_total(self, obj):
        return obj._play_total


class ImportForm(forms.Form):
    songlist = forms.FileField(label="中央動畫社線上歌單（.xlsx）", required=False)
    history = forms.FileField(label="最新播放曲目統計（.xlsx）", required=False)
    prune = forms.BooleanField(label="刪除試算表沒有的舊曲", required=False)

    def clean(self):
        data = super().clean()
        if not data.get("songlist") and not data.get("history"):
            raise forms.ValidationError("請至少選一個檔案")
        return data


class SpreadsheetManagedAdmin(admin.ModelAdmin):
    """
    舊曲與播放紀錄以 Google 試算表為正本，後台只能看、不能改；
    要改請改試算表，再用列表右上角的「匯入試算表」同步。
    """

    change_list_template = "admin/songfest/spreadsheet_change_list.html"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = [path("import/", self.admin_site.admin_view(self.import_view), name=f"songfest_{self.opts.model_name}_import")]
        return urls + super().get_urls()

    def import_view(self, request):
        if not request.user.has_module_perms("songfest"):
            raise PermissionDenied
        report = None
        error = None
        if request.method == "POST":
            form = ImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    report = import_songfest(
                        songlist=form.cleaned_data["songlist"],
                        history=form.cleaned_data["history"],
                        prune=form.cleaned_data["prune"],
                        dry_run="_import" not in request.POST,
                    )
                except SpreadsheetError as exc:
                    error = str(exc)
        else:
            form = ImportForm()
        context = {
            **self.admin_site.each_context(request),
            "opts": self.opts,
            "title": "從試算表匯入舊曲與播放紀錄",
            "form": form,
            "report": report,
            "error": error,
        }
        return TemplateResponse(request, "admin/songfest/import.html", context)


@admin.register(Track)
class TrackAdmin(SpreadsheetManagedAdmin):
    list_display = ("dvd_code", "song_source", "visual_source", "title", "editor", "duration", "index_label")
    list_filter = ("index_group",)
    search_fields = ("dvd_code", "song_source", "visual_source", "title", "artist", "editor")
    ordering = ("-dvd_sort",)

    @admin.display(description="長度", ordering="duration_seconds")
    def duration(self, obj):
        if obj.duration_seconds is None:
            return "-"
        minutes, seconds = divmod(obj.duration_seconds, 60)
        return f"{minutes}:{seconds:02d}"


@admin.register(Play)
class PlayAdmin(SpreadsheetManagedAdmin):
    list_display = ("festival", "position", "song_source", "visual_source", "title", "track", "match_status")
    list_filter = ("match_status", "festival")
    search_fields = ("song_source", "visual_source", "title")
    list_select_related = ("festival", "track")


class SubmissionCommentInline(admin.TabularInline):
    model = SubmissionComment
    extra = 0
    fields = ("user", "content", "created_at")
    readonly_fields = ("user", "content", "created_at")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """
    排歌組平常用網站上的「管理歌單」頁；換歌、補報（報曲截止後經排歌組同意新增）這類例外處理在這裡改。
    """

    list_display = ("title", "editor_name", "festival", "source", "status_label", "five_sec", "created_at")
    list_filter = ("festival", "source", "is_rejected")
    search_fields = ("title", "song_source", "visual_source", "editor_name", "submitter__name")
    raw_id_fields = ("chain_with",)
    readonly_fields = ("created_at", "updated_at", "uploaded_at", "file_updated_at", "five_sec_uploaded_at")
    inlines = [SubmissionCommentInline]
    fieldsets = (
        (None, {"fields": ("festival", "source", "submitter", "editor_name", "contact_email")}),
        ("歌曲", {"fields": ("song_source", "visual_source", "title", "artist", "attributes", "song_link",
                             "remarks", "restricted_work", "five_sec", "is_backup", "chain_with")}),
        ("繳交", {"fields": ("file_link", "duration_seconds", "uploaded_at", "file_updated_at",
                             "five_sec_link", "five_sec_uploaded_at")}),
        ("排歌組處理", {"fields": ("withdrawn_at", "extended_until", "file_checked", "is_rejected",
                                 "reject_reason", "penalty_waived")}),
        ("亂入曲表單", {"classes": ("collapse",), "fields": ("library_consent", "guest_message")}),
        ("時間", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="狀態")
    def status_label(self, obj):
        return Submission.STATUS_LABELS[obj.status()]
