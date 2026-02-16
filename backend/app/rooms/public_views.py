from __future__ import annotations

from rest_framework import generics
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema

from rooms.models import RoomType
from rooms.public_serializers import PublicRoomTypeSerializer
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


class PublicRoomTypeListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicRoomTypeSerializer

    @extend_schema(
        tags=["Public"],
        operation_id="public_room_types_list",
        summary="List room types (public)",
        description=(
            "Public endpoint for booking web. Returns active room types with translated text fields and photo URLs."
        ),
        parameters=[_LANG_QP, _ACCEPT_LANG_HDR],
        responses=PublicRoomTypeSerializer(many=True),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return (
            RoomType.objects.filter(is_active=True)
            .prefetch_related("photos")
            .order_by("code")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = _pick_lang(self.request)
        return ctx


class PublicRoomTypeDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicRoomTypeSerializer

    @extend_schema(
        tags=["Public"],
        operation_id="public_room_types_retrieve",
        summary="Get room type (public)",
        description="Public endpoint for booking web. Returns a single active room type with photos and characteristics.",
        parameters=[_LANG_QP, _ACCEPT_LANG_HDR],
        responses=PublicRoomTypeSerializer,
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return (
            RoomType.objects.filter(is_active=True)
            .prefetch_related("photos")
            .order_by("code")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = _pick_lang(self.request)
        return ctx
