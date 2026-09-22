from django.contrib import admin

from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "start_time", "end_time", "location", "is_published")
    list_filter = ("is_published", "start_time")
    search_fields = ("title", "description", "location")
    date_hierarchy = "start_time"
    ordering = ("start_time",)
