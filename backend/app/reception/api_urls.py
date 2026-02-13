from django.urls import path

from .views import (
    OcrScanLogListView,
    OcrScanStatsView,
    ReceptionHealthView,
    ReservationDetailView,
    ReservationGuestDetailView,
    ReservationGuestOcrView,
    ReservationTimelineListView,
)

urlpatterns = [
    path("health/", ReceptionHealthView.as_view(), name="api-reception-health"),
    path("reservations/", ReservationTimelineListView.as_view(), name="api-reservations-list"),
    path("reservations/<int:pk>/", ReservationDetailView.as_view(), name="api-reservations-detail"),
    path(
        "reservations/<int:reservation_id>/guests/<int:guest_id>/",
        ReservationGuestDetailView.as_view(),
        name="api-reservation-guest-detail",
    ),
    path(
        "reservations/<int:reservation_id>/guests/<int:guest_id>/ocr/",
        ReservationGuestOcrView.as_view(),
        name="api-reservation-guest-ocr",
    ),
    path("ocr/logs/", OcrScanLogListView.as_view(), name="api-ocr-logs"),
    path("ocr/stats/", OcrScanStatsView.as_view(), name="api-ocr-stats"),
]
