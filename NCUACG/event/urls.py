from django.urls import path
from .views import calendar, upcoming_events

urlpatterns = [
    path("upcoming/", upcoming_events, name="upcoming_events"),
    path("calendar/", calendar, name="event_calendar"),
]