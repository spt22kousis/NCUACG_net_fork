from django.urls import path

from . import submission_views as sv
from . import views

urlpatterns = [
    # 公開：舊曲、歷屆歌單（views.py）
    path("festivals/", views.festival_list, name="songfest_festivals"),
    path("festivals/<int:festival_id>/", views.festival_detail, name="songfest_festival_detail"),
    path("tracks/", views.track_list, name="songfest_tracks"),
    path("tracks/groups/", views.track_groups, name="songfest_track_groups"),
    path("ranking/", views.ranking, name="songfest_ranking"),

    # 新曲投稿（submission_views.py）
    path("active/", sv.active_festival, name="songfest_active"),
    path("festivals/<int:festival_id>/submissions/", sv.festival_submissions, name="songfest_submissions"),
    path("festivals/<int:festival_id>/my-submissions/", sv.my_submissions, name="songfest_my_submissions"),
    path("submissions/<int:submission_id>/", sv.submission_detail, name="songfest_submission"),
    path("submissions/<int:submission_id>/withdraw/", sv.submission_withdraw, name="songfest_submission_withdraw"),
    path("submissions/<int:submission_id>/comments/", sv.submission_comments, name="songfest_submission_comments"),
    path("submission-comments/<int:comment_id>/", sv.submission_comment_delete, name="songfest_comment_delete"),

    # 排歌組
    path("manage/festivals/", sv.manage_festivals, name="songfest_manage_festivals"),
    path("festivals/<int:festival_id>/manage/", sv.manage_overview, name="songfest_manage"),
    path("manage/submissions/<int:submission_id>/", sv.manage_submission, name="songfest_manage_submission"),
    path("festivals/<int:festival_id>/manage/export/", sv.manage_export, name="songfest_manage_export"),
    path("festivals/<int:festival_id>/manage/import-guests/", sv.manage_import_guests, name="songfest_import_guests"),
]
