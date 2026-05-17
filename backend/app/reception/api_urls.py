from django.urls import path

from communications.views import ReservationGuestMessageListCreateView

from .booking_xls_views import BookingXlsImportView
from .statistics_views import ReceptionMonthlyStatisticsView
from .views import (
    DocumentScanIngestView,
    EvisitorSubmitView,
    GuestFacePhotoView,
    ReceptionHealthView,
    ReservationDetailView,
    ReservationGuestDetailView,
    ReservationGuestListCreateView,
    ReservationTimelineListView,
)

urlpatterns = [
    path("health/", ReceptionHealthView.as_view(), name="api-reception-health"),
    path("booking-xls-import/", BookingXlsImportView.as_view(), name="api-booking-xls-import"),
    path(
        "statistics/monthly/",
        ReceptionMonthlyStatisticsView.as_view(),
        name="api-reception-statistics-monthly",
    ),
    path("reservations/", ReservationTimelineListView.as_view(), name="api-reservations-list"),
    path("reservations/<int:pk>/", ReservationDetailView.as_view(), name="api-reservations-detail"),
    path(
        "reservations/<int:pk>/messages/",
        ReservationGuestMessageListCreateView.as_view(),
        name="api-reservation-messages",
    ),
    path(
        "reservations/<int:reservation_id>/guests/",
        ReservationGuestListCreateView.as_view(),
        name="api-reservation-guest-list-create",
    ),
    path(
        "reservations/<int:reservation_id>/guests/<int:guest_id>/",
        ReservationGuestDetailView.as_view(),
        name="api-reservation-guest-detail",
    ),
    path(
        "reservations/<int:reservation_id>/guests/<int:guest_id>/face-photo/",
        GuestFacePhotoView.as_view(),
        name="api-reception-guest-face-photo",
    ),
    path(
        "reservations/<int:reservation_id>/guests/<int:guest_id>/document-scan/",
        DocumentScanIngestView.as_view(),
        name="api-reservation-guest-document-scan",
    ),
    path(
        "reservations/<int:reservation_id>/guests/<int:guest_id>/evisitor-submit/",
        EvisitorSubmitView.as_view(),
        name="api-reservation-guest-evisitor-submit",
    ),
]
