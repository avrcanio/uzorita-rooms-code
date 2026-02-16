from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny

from rooms.models import PropertyInfo
from rooms.public_property_serializers import PublicPropertySerializer
from rooms.views import _pick_lang


_LANG_QP = OpenApiParameter(
    name="lang",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Optional language tag (e.g. `hr`, `en`, `hr-HR`). If omitted, uses `Accept-Language` header then falls back to `en`.",
)
_ACCEPT_LANG_HDR = OpenApiParameter(
    name="Accept-Language",
    type=OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    required=False,
    description="Optional language header (e.g. `hr`, `en`, `hr-HR`). Used if `?lang=` is not provided.",
)


class PublicPropertyView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicPropertySerializer
    queryset = PropertyInfo.objects.all()
    lookup_field = "code"
    lookup_url_kwarg = "code"

    @extend_schema(
        tags=["Public"],
        operation_id="public_property_retrieve",
        summary="Get property info (public)",
        description="Public endpoint for booking web. Returns global property info including i18n 'About this property' text and Google Maps location fields.",
        parameters=[_LANG_QP, _ACCEPT_LANG_HDR],
        responses=PublicPropertySerializer,
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        # Prefer the active "default" record; fallback to first active record.
        qs = PropertyInfo.objects.filter(is_active=True).order_by("code")
        obj = qs.filter(code="default").first() or qs.first()
        if not obj:
            # Let DRF raise 404 (requires url kwarg).
            return super().get_object()
        return obj

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = _pick_lang(self.request)
        return ctx
