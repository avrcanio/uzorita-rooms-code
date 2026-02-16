from __future__ import annotations

import os
import re
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageOps
from rest_framework import serializers

from rooms.models import RoomType, RoomTypePhoto


def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


class PublicRoomTypePhotoSerializer(serializers.ModelSerializer):
    caption = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    url_small = serializers.SerializerMethodField()

    class Meta:
        model = RoomTypePhoto
        fields = ("id", "url", "url_small", "caption", "sort_order")

    def _lang(self) -> str | None:
        return (self.context or {}).get("lang")

    def get_caption(self, obj) -> str:
        return obj.get_i18n_text("caption_i18n", self._lang())

    def get_url(self, obj) -> str:
        # Always return absolute URL so the booking frontend can render images cross-origin.
        if not getattr(obj, "image", None):
            return ""
        try:
            url = obj.image.url
        except Exception:
            return ""
        req = (self.context or {}).get("request")
        return req.build_absolute_uri(url) if req else url

    def get_url_small(self, obj) -> str:
        """
        Returns a smaller, cached derivative for carousels / thumbnails.

        We generate on-demand into MEDIA_ROOT next to the original image:
          room_types/photos/YYYY/MM/DD/thumbs/<basename>_w320.jpg
        """
        if not getattr(obj, "image", None):
            return ""
        try:
            rel_url = obj.image.url
            src_path = Path(obj.image.path)
        except Exception:
            return ""

        # Keep it reasonably sharp on mobile while still much smaller than originals.
        # Thumbnail width for carousels. Keep small for fast first paint.
        target_w = 160

        try:
            if not src_path.exists():
                return self.get_url(obj)

            # Skip upscaling.
            with Image.open(src_path) as im0:
                im = ImageOps.exif_transpose(im0)
                w, h = im.size
                if not w or w <= target_w:
                    return self.get_url(obj)

                target_h = max(1, round(h * (target_w / w)))
                im = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
                if im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")

                thumb_dir = src_path.parent / "thumbs"
                thumb_dir.mkdir(parents=True, exist_ok=True)
                stem = src_path.stem
                thumb_path = thumb_dir / f"{stem}_w{target_w}.jpg"

                if not thumb_path.exists():
                    tmp_path = thumb_dir / f".{stem}_w{target_w}.tmp"
                    im.save(tmp_path, format="JPEG", quality=82, optimize=True, progressive=True)
                    os.replace(tmp_path, thumb_path)
        except Exception:
            # Fallback: keep API stable even if Pillow fails.
            return self.get_url(obj)

        # Derive URL by inserting /thumbs/ and changing filename.
        try:
            base = Path(rel_url)
            # rel_url is something like /media/room_types/photos/YYYY/MM/DD/file.jpg
            # We want /media/room_types/photos/YYYY/MM/DD/thumbs/file_w640.jpg
            thumb_url = str(base.parent / "thumbs" / f"{base.stem}_w{target_w}.jpg")
        except Exception:
            return self.get_url(obj)

        req = (self.context or {}).get("request")
        return req.build_absolute_uri(thumb_url) if req else thumb_url


class PublicRoomTypeSerializer(serializers.ModelSerializer):
    slug = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    subtitle = serializers.SerializerMethodField()
    beds = serializers.SerializerMethodField()
    highlights = serializers.SerializerMethodField()
    views = serializers.SerializerMethodField()
    amenities = serializers.SerializerMethodField()
    primary_photo_url = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()

    class Meta:
        model = RoomType
        fields = (
            "id",
            "code",
            "slug",
            "name",
            "subtitle",
            "beds",
            "highlights",
            "views",
            "amenities",
            "primary_photo_url",
            "photos",
            "size_m2",
        )

    def _lang(self) -> str | None:
        return (self.context or {}).get("lang")

    def get_slug(self, obj) -> str:
        return _slugify(obj.code)

    def get_name(self, obj) -> str:
        return obj.get_i18n_text("name_i18n", self._lang())

    def get_subtitle(self, obj) -> str:
        return obj.get_i18n_text("subtitle_i18n", self._lang())

    def get_beds(self, obj) -> str:
        return obj.get_i18n_text("beds_i18n", self._lang())

    def get_highlights(self, obj) -> list[str]:
        return obj.get_i18n_list("highlights_i18n", self._lang())

    def get_views(self, obj) -> list[str]:
        return obj.get_i18n_list("views_i18n", self._lang())

    def get_amenities(self, obj) -> list[str]:
        return obj.get_i18n_list("amenities_i18n", self._lang())

    def get_primary_photo_url(self, obj) -> str:
        photo = (
            obj.photos.filter(is_active=True, is_primary=True)
            .order_by("sort_order", "id")
            .first()
        )
        if not photo:
            return ""
        return PublicRoomTypePhotoSerializer(photo, context=self.context).data.get("url", "")

    def get_photos(self, obj) -> list[dict]:
        qs = obj.photos.filter(is_active=True).order_by("sort_order", "id")
        return PublicRoomTypePhotoSerializer(qs, many=True, context=self.context).data
