from django.urls import path

from .views import (
    DocumentScanIngestView,
    ReceptionHealthView,
    ReservationDetailView,
    ReservationGuestDetailView,
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
        "reservations/<int:reservation_id>/guests/<int:guest_id>/document-scan/",
        DocumentScanIngestView.as_view(),
        name="api-reservation-guest-document-scan",
    ),
]
