from django.urls import path

from rooms.public_booking_views import PublicAvailabilityView, PublicRoomCalendarView


urlpatterns = [
    path("availability/", PublicAvailabilityView.as_view(), name="public-availability"),
    path("rooms/<int:room_id>/calendar/", PublicRoomCalendarView.as_view(), name="public-room-calendar"),
]
