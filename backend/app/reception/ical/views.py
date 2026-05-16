from __future__ import annotations

from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from reception.ical.export import build_export_ics
from reception.models import BookingIcalFeed


class BookingIcalExportView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, feed_code, export_token):
        feed = (
            BookingIcalFeed.objects.filter(
                code=feed_code.strip().lower(),
                export_token=export_token,
                is_active=True,
            )
            .select_related("room_type")
            .first()
        )
        if not feed:
            return HttpResponse(status=404)
        body = build_export_ics(feed)
        response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = f'inline; filename="uzorita-{feed.code}.ics"'
        return response
