# NCUACG/club/urls.py
from django.urls import path

from . import lesson_views, views

urlpatterns = [
    path("courses/", views.course_list, name="club_courses"),
    path("works/", views.work_list, name="club_works"),
    path("works/<int:work_id>/view/", views.work_view, name="club_work_view"),
    path("works/<int:work_id>/like/", views.work_like, name="club_work_like"),
    path("works/<int:work_id>/comments/", views.work_comments, name="club_work_comments"),
    path("comments/<int:comment_id>/", views.comment_delete, name="club_comment_delete"),
    path("comments/<int:comment_id>/like/", views.comment_like, name="club_comment_like"),
    # 社課堂次與公告
    path("lessons/", lesson_views.lesson_list, name="club_lessons"),
    path("lessons/manage/", lesson_views.lesson_manage, name="club_lesson_manage"),
    path("lessons/<int:lesson_id>/", lesson_views.lesson_detail, name="club_lesson_detail"),
]
