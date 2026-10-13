from django.urls import path

from . import views

urlpatterns = [
    # 管理
    path("events/", views.event_list, name="checkin_events"),
    path("events/export/", views.events_export, name="checkin_events_export"),
    path("events/<int:event_id>/", views.event_detail, name="checkin_event_detail"),
    path("events/<int:event_id>/reset-key/", views.reset_key, name="checkin_reset_key"),
    path("events/<int:event_id>/slots/", views.slot_create, name="checkin_slot_create"),
    path("events/<int:event_id>/export/", views.event_export, name="checkin_event_export"),
    path("slots/<int:slot_id>/", views.slot_detail, name="checkin_slot_detail"),
    path("records/<int:record_id>/", views.record_detail, name="checkin_record_detail"),
    # 掃描頁（靠網址上的 key）
    path("scan/<int:event_id>/", views.scan_info, name="checkin_scan_info"),
    path("scan/<int:event_id>/records/", views.scan_records, name="checkin_scan_records"),
]
