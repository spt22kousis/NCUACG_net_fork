from django.urls import path

from . import views

urlpatterns = [
    path("festivals/", views.festival_list, name="songfest_festivals"),
    path("festivals/<int:festival_id>/", views.festival_detail, name="songfest_festival_detail"),
    path("tracks/", views.track_list, name="songfest_tracks"),
    path("tracks/groups/", views.track_groups, name="songfest_track_groups"),
    path("ranking/", views.ranking, name="songfest_ranking"),
]
