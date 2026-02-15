from django.urls import path

from .views import RoomCalendarView, RoomListView, RoomTypeListView


urlpatterns = [
    path("types/", RoomTypeListView.as_view(), name="api-room-types-list"),
    path("rooms/", RoomListView.as_view(), name="api-rooms-list"),
    path("rooms/<int:room_id>/calendar/", RoomCalendarView.as_view(), name="api-room-calendar"),
]
