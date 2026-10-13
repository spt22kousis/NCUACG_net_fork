from django.urls import path

from . import request_views as rv
from . import setlist_views as st
from . import submission_views as sv
from . import views

urlpatterns = [
    # 公開：舊曲、歷屆歌單（views.py）
    path("festivals/", views.festival_list, name="songfest_festivals"),
    path("festivals/<int:festival_id>/", views.festival_detail, name="songfest_festival_detail"),
    path("tracks/", views.track_list, name="songfest_tracks"),
    path("tracks/groups/", views.track_groups, name="songfest_track_groups"),
    path("ranking/", views.ranking, name="songfest_ranking"),

    # 點歌（request_views.py）
    path("requests/", rv.request_list, name="songfest_requests"),
    path("requests/wishes/", rv.wish_list, name="songfest_request_wishes"),
    path("requests/<int:request_id>/", rv.request_detail, name="songfest_request_detail"),
    path("requests/<int:request_id>/vote/", rv.request_vote, name="songfest_request_vote"),

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

    # 排歌台（setlist_views.py）
    path("festivals/<int:festival_id>/setlist/", st.board, name="songfest_setlist"),
    path("festivals/<int:festival_id>/setlist/auto/", st.auto, name="songfest_setlist_auto"),
    path("festivals/<int:festival_id>/setlist/suggest/", st.suggest, name="songfest_setlist_suggest"),
    path("festivals/<int:festival_id>/setlist/export/", st.export, name="songfest_setlist_export"),
    path("festivals/<int:festival_id>/setlist/publish/", st.publish, name="songfest_setlist_publish"),
    path("festivals/<int:festival_id>/setlist/write-plays/", st.write_plays, name="songfest_setlist_write_plays"),
    path("setlist/sessions/<int:session_id>/", st.session_detail, name="songfest_session"),
    path("setlist/sessions/<int:session_id>/entries/", st.entry_create, name="songfest_entry_create"),
    path("setlist/entries/<int:entry_id>/", st.entry_detail, name="songfest_entry"),
    path("festivals/<int:festival_id>/library/", st.library, name="songfest_library"),
    path("festivals/<int:festival_id>/library/add/", st.library_add, name="songfest_library_add"),
    path("festivals/<int:festival_id>/library/export/", st.library_export, name="songfest_library_export"),
    path("library-consent/", st.my_library_consent, name="songfest_my_library_consent"),
    path("submissions/<int:submission_id>/library-consent/", st.library_consent, name="songfest_library_consent"),
]
