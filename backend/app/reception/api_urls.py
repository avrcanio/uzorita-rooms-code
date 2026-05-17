from django.urls import path

from communications.views import ReservationGuestMessageListCreateView

from .booking_extranet.views import (
    BookingExtranetCheckPollView,
    BookingExtranetCheckView,
    BookingExtranetConnectionView,
    BookingExtranetDisconnectView,
    BookingExtranetImportStateView,
    BookingExtranetStartConnectPollView,
    BookingExtranetStartConnectView,
    BookingExtranetVerify2faView,
    BookingExtranetFetchReservationPollView,
    BookingExtranetFetchReservationView,
    BookingExtranetVncAuthView,
    BookingExtranetVncContinueView,
)
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
    path(
        "booking-extranet/connection/",
        BookingExtranetConnectionView.as_view(),
        name="api-booking-extranet-connection",
    ),
    path(
        "booking-extranet/connection/start/",
        BookingExtranetStartConnectView.as_view(),
        name="api-booking-extranet-connection-start",
    ),
    path(
        "booking-extranet/connection/start/<str:task_id>/",
        BookingExtranetStartConnectPollView.as_view(),
        name="api-booking-extranet-connection-start-poll",
    ),
    path(
        "booking-extranet/connection/verify-2fa/",
        BookingExtranetVerify2faView.as_view(),
        name="api-booking-extranet-connection-verify-2fa",
    ),
    path(
        "booking-extranet/connection/disconnect/",
        BookingExtranetDisconnectView.as_view(),
        name="api-booking-extranet-connection-disconnect",
    ),
    path(
        "booking-extranet/connection/check/",
        BookingExtranetCheckView.as_view(),
        name="api-booking-extranet-connection-check",
    ),
    path(
        "booking-extranet/connection/check/<str:task_id>/",
        BookingExtranetCheckPollView.as_view(),
        name="api-booking-extranet-connection-check-poll",
    ),
    path(
        "booking-extranet/connection/import-state/",
        BookingExtranetImportStateView.as_view(),
        name="api-booking-extranet-connection-import-state",
    ),
    path(
        "booking-extranet/vnc/auth/",
        BookingExtranetVncAuthView.as_view(),
        name="api-booking-extranet-vnc-auth",
    ),
    path(
        "booking-extranet/vnc/continue/",
        BookingExtranetVncContinueView.as_view(),
        name="api-booking-extranet-vnc-continue",
    ),
    path(
        "booking-extranet/fetch-reservation/",
        BookingExtranetFetchReservationView.as_view(),
        name="api-booking-extranet-fetch-reservation",
    ),
    path(
        "booking-extranet/fetch-reservation/<str:task_id>/",
        BookingExtranetFetchReservationPollView.as_view(),
        name="api-booking-extranet-fetch-reservation-poll",
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
