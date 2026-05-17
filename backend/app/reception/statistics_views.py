from datetime import date

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reception.statistics import aggregate_monthly_statistics


class ReceptionMonthlyStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year_param = request.query_params.get("year")
        if year_param is None or str(year_param).strip() == "":
            year = timezone.localdate().year
        else:
            try:
                year = int(year_param)
            except (TypeError, ValueError) as exc:
                return Response(
                    {"detail": "year mora biti cijeli broj."},
                    status=400,
                ) from exc
            if year < 2000 or year > 2100:
                return Response(
                    {"detail": "year izvan dopuštenog raspona."},
                    status=400,
                )

        return Response(aggregate_monthly_statistics(year))
