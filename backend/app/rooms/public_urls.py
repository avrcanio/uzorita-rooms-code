from django.urls import path

from .public_views import PublicRoomTypeDetailView, PublicRoomTypeListView


urlpatterns = [
    # Public, no-auth endpoints for booking web.
    path("", PublicRoomTypeListView.as_view(), name="public-room-types-list"),
    path("<int:pk>/", PublicRoomTypeDetailView.as_view(), name="public-room-types-detail"),
]

