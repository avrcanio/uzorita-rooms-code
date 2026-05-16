from django.urls import path

from reception.ical.views import BookingIcalExportView

urlpatterns = [
    path(
        "<str:feed_code>/<uuid:export_token>.ics",
        BookingIcalExportView.as_view(),
        name="public-booking-ical-export",
    ),
]
