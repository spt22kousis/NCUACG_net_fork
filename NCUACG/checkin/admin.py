from django.contrib import admin
from django.db.models import Count

from .models import Checkin, CheckinEvent, CheckinSlot


class CheckinSlotInline(admin.TabularInline):
    model = CheckinSlot
    extra = 0
    fields = ("name", "order", "starts_at", "ends_at", "opens_at", "closes_at")


@admin.register(CheckinEvent)
class CheckinEventAdmin(admin.ModelAdmin):
    """簽到請在網站的「活動簽到」頁建立與管理；這裡用來查看與修正。"""

    list_display = ("title", "festival", "lesson", "record_count", "created_by", "created_at")
    search_fields = ("title",)
    readonly_fields = ("scan_key", "created_by", "created_at")
    inlines = [CheckinSlotInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_records=Count("slots__checkins"))

    @admin.display(description="簽到筆數", ordering="_records")
    def record_count(self, obj):
        return obj._records


@admin.register(Checkin)
class CheckinAdmin(admin.ModelAdmin):
    list_display = ("student_id", "slot", "source", "scanned_at", "device")
    list_filter = ("slot__event", "source")
    search_fields = ("student_id",)
    readonly_fields = ("slot", "student_id", "raw", "source", "scanned_at", "received_at", "client_id", "device")

    def has_add_permission(self, request):
        return False
