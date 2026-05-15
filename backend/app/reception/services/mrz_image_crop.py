"""
MRZ region crop + preprocess za drugi PaddleOCR prolaz (donji dio dokumenta).

Koraci: izrez donjeg 30–35 %, deskew (kut iz OCR boxova ili Hough), upscale (INTER_CUBIC),
grayscale, CLAHE, adaptive threshold → JPEG RGB za Paddle.
"""

from __future__ import annotations

import io
import logging
import math
import statistics
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps

from reception.services.td1_mrz_extract import _normalize_text_for_mrz

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np

    _CV2_AVAILABLE = True
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False
    logger.warning(
        "OpenCV nije dostupan (instaliraj ``opencv-python-headless`` u backend okruženju). "
        "MRZ drugi prolaz koristi PIL fallback bez CLAHE/adaptive threshold/Hough deskew; "
        "u JSON-u će ``skew_source`` biti ``pil_fallback_no_cv2``."
    )

try:
    from django.conf import settings as _django_settings
except ImportError:  # pragma: no cover
    _django_settings = None


def _dj_int(name: str, default: int) -> int:
    if _django_settings is None:
        return default
    try:
        return int(getattr(_django_settings, name, default))
    except (TypeError, ValueError):
        return default

# --- geometrija / IO (Pillow, bez OpenCV decode za mala utility) ---


def image_size_from_bytes(image_bytes: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = im.convert("RGB")
        return im.size


def crop_bottom_strip_jpeg(
    image_bytes: bytes,
    height_ratio: float,
    *,
    jpeg_quality: int = 92,
) -> tuple[bytes, int, int, int]:
    """
    Return (jpeg_bytes, full_width, full_height, crop_y0) where crop_y0 is the
    top Y coordinate of the bottom strip in full-image coordinates.
    """
    if height_ratio <= 0 or height_ratio >= 1:
        raise ValueError("height_ratio must be between 0 and 1")
    with Image.open(io.BytesIO(image_bytes)) as im:
        im = im.convert("RGB")
        w, h = im.size
        ch = max(1, int(h * height_ratio))
        y0 = h - ch
        strip = im.crop((0, y0, w, h))
        buf = io.BytesIO()
        strip.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        return buf.getvalue(), w, h, y0


def _centroid_y(box: Any) -> float | None:
    if not isinstance(box, (list, tuple)) or len(box) < 2:
        return None
    ys: list[float] = []
    for pt in box:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            try:
                ys.append(float(pt[1]))
            except (TypeError, ValueError):
                continue
    if not ys:
        return None
    return sum(ys) / len(ys)


def _estimate_skew_deg_from_paddle_boxes(items: list[dict[str, Any]], *, strip_y_min: float) -> float | None:
    """Kut gornjeg ruba bboxa (°) za stavke u MRZ traci; medijan ako ima ≥2."""
    angles: list[float] = []
    for it in items:
        cy = _centroid_y(it.get("box"))
        if cy is None or cy < strip_y_min:
            continue
        box = it.get("box")
        if not isinstance(box, (list, tuple)) or len(box) < 2:
            continue
        try:
            p0, p1 = box[0], box[1]
            dx = float(p1[0]) - float(p0[0])
            dy = float(p1[1]) - float(p0[1])
            if abs(dx) < 1e-3:
                continue
            deg = float(math.degrees(math.atan2(dy, dx)))
            if -22.0 <= deg <= 22.0:
                angles.append(deg)
        except (TypeError, ValueError, IndexError):
            continue
    if len(angles) < 2:
        return None
    return float(statistics.median(angles))


def _estimate_skew_deg_hough(gray: Any) -> float:
    if not _CV2_AVAILABLE or cv2 is None or np is None:
        return 0.0
    h, w = gray.shape[:2]
    if h < 8 or w < 8:
        return 0.0
    target_h = min(420, max(h, 1))
    scale = target_h / float(h)
    small_w = max(1, int(round(w * scale)))
    small = cv2.resize(gray, (small_w, target_h), interpolation=cv2.INTER_AREA)
    blur = cv2.GaussianBlur(small, (3, 3), 0)
    edges = cv2.Canny(blur, 25, 85, apertureSize=3)
    min_len = max(int(min(small.shape[:2]) * 0.18), 18)
    lines = cv2.HoughLinesP(
        edges,
        1,
        math.pi / 180.0,
        threshold=max(min_len, 25),
        minLineLength=min_len,
        maxLineGap=14,
    )
    angles: list[float] = []
    if lines is not None:
        for line in lines[:160]:
            x1, y1, x2, y2 = line[0]
            dx, dy = float(x2 - x1), float(y2 - y1)
            if abs(dx) < 1e-3:
                continue
            deg = float(math.degrees(math.atan2(dy, dx)))
            if abs(deg) <= 22.0:
                angles.append(deg)
    if not angles:
        return 0.0
    return float(statistics.median(angles))


def _clamp_angle_deg(v: float, lim: float) -> float:
    return max(-lim, min(lim, v))


def _build_mrz_crop_pil_only(
    full_image_bytes: bytes,
    *,
    height_ratio: float,
    upscale: int,
) -> MrzCropPipelineResult:
    """Ako OpenCV nije instaliran: samo Pillow izrez + preprocess_mrz_strip (bez deskew/CLAHE)."""
    crop_raw, fw, fh, y0 = crop_bottom_strip_jpeg(full_image_bytes, height_ratio)
    up = 2 if upscale not in (2, 3) else upscale
    pre = preprocess_mrz_strip(crop_raw, upscale=up)
    return MrzCropPipelineResult(
        crop_raw_jpeg=crop_raw,
        deskewed_jpeg=crop_raw,
        preprocessed_jpeg=pre,
        deskew_angle_deg=0.0,
        skew_source="pil_fallback_no_cv2",
        crop_y0=y0,
        full_width=fw,
        full_height=fh,
    )


def _rotate_bound_bgr(image: Any, angle_deg: float) -> Any:
    """Rotacija oko centra s proširenim platnom (INTER_CUBIC)."""
    if not _CV2_AVAILABLE or cv2 is None:
        return image
    if abs(angle_deg) < 0.25:
        return image
    h, w = image.shape[:2]
    c_x, c_y = (w - 1) / 2.0, (h - 1) / 2.0
    m = cv2.getRotationMatrix2D((c_x, c_y), angle_deg, 1.0)
    cos = abs(m[0, 0])
    sin = abs(m[0, 1])
    n_w = int(math.ceil(h * sin + w * cos))
    n_h = int(math.ceil(h * cos + w * sin))
    m[0, 2] += (n_w / 2.0) - c_x
    m[1, 2] += (n_h / 2.0) - c_y
    return cv2.warpAffine(
        image,
        m,
        (n_w, n_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _jpeg_encode_bgr(bgr: Any, *, quality: int = 92) -> bytes:
    if not _CV2_AVAILABLE or cv2 is None:
        raise RuntimeError("cv2 required for _jpeg_encode_bgr")
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("cv2.imencode failed")
    return bytes(buf)


def _bgr_from_jpeg_bytes(data: bytes) -> Any:
    if not _CV2_AVAILABLE or cv2 is None or np is None:
        raise RuntimeError("cv2 required for _bgr_from_jpeg_bytes")
    arr = np.frombuffer(data, dtype=np.uint8)
    im = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if im is None:
        raise ValueError("cannot decode image")
    return im


@dataclass(frozen=True)
class MrzCropPipelineResult:
    """Izlaz MRZ crop pipelinea za drugi OCR prolaz."""

    crop_raw_jpeg: bytes
    deskewed_jpeg: bytes
    preprocessed_jpeg: bytes
    deskew_angle_deg: float
    skew_source: str
    crop_y0: int
    full_width: int
    full_height: int


def build_mrz_crop_for_paddle_second_pass(
    full_image_bytes: bytes,
    *,
    height_ratio: float,
    ocr_items: list[dict[str, Any]] | None = None,
    full_height: int | None = None,
    upscale: int = 2,
    use_otsu: bool = False,
    deskew_max_abs_deg: float = 12.0,
) -> MrzCropPipelineResult:
    """
    1) Izreži donji ``height_ratio`` dijelа (30–35 % preporuka).
    2) Deskew: preferiraj kut iz Paddle bboxeva u traci, inače Hough na cropu.
    3) INTER_CUBIC upscale (2x ili 3x).
    4) Grayscale → CLAHE → adaptive ili Otsu threshold.
    5) Tri JPEG varijante za debug / slanje u OCR.
    """
    if height_ratio <= 0 or height_ratio >= 1:
        raise ValueError("height_ratio must be between 0 and 1")

    if not _CV2_AVAILABLE:
        return _build_mrz_crop_pil_only(
            full_image_bytes,
            height_ratio=height_ratio,
            upscale=upscale,
        )

    full = _bgr_from_jpeg_bytes(full_image_bytes)
    fh, fw = full.shape[:2]
    ch = max(1, int(round(fh * height_ratio)))
    y0 = fh - ch
    crop_bgr = full[y0:fh, 0:fw].copy()
    # Debug „raw“ = geometrijski izrez punog kadra (prije smanjivanja za performanse).
    crop_raw_jpeg = _jpeg_encode_bgr(crop_bgr)
    crop_work = crop_bgr
    cap = _dj_int("MRZ_CROP_MAX_LONG_EDGE", 1600)
    if cap > 0:
        chx, cwx = crop_work.shape[:2]
        longest = max(chx, cwx)
        if longest > cap:
            sc = cap / float(longest)
            crop_work = cv2.resize(
                crop_work,
                (int(round(cwx * sc)), int(round(chx * sc))),
                interpolation=cv2.INTER_AREA,
            )

    gray0 = cv2.cvtColor(crop_work, cv2.COLOR_BGR2GRAY)
    strip_y_min = float(y0) - 4.0
    ang: float = 0.0
    src = "none"
    if ocr_items and full_height:
        box_ang = _estimate_skew_deg_from_paddle_boxes(ocr_items, strip_y_min=strip_y_min)
        if box_ang is not None:
            ang = _clamp_angle_deg(box_ang, deskew_max_abs_deg)
            src = "ocr_boxes"
    if src == "none":
        h_ang = _estimate_skew_deg_hough(gray0)
        ang = _clamp_angle_deg(h_ang, deskew_max_abs_deg)
        if abs(ang) >= 0.25:
            src = "hough"

    deskewed = _rotate_bound_bgr(crop_work, -ang)
    deskewed_jpeg = _jpeg_encode_bgr(deskewed)

    g = cv2.cvtColor(deskewed, cv2.COLOR_BGR2GRAY)
    nh, nw = g.shape[:2]
    upscale_use = int(upscale)
    if upscale_use not in (2, 3):
        upscale_use = 2
    max_px = _dj_int("MRZ_CROP_MAX_PIXELS_AFTER_UPSCALE", 5_000_000)
    if max_px > 0:
        while upscale_use > 1 and (nh * nw * upscale_use * upscale_use) > max_px:
            upscale_use -= 1
    g_up = cv2.resize(
        g,
        (nw * upscale_use, nh * upscale_use),
        interpolation=cv2.INTER_CUBIC,
    )
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    eq = clahe.apply(g_up)
    bs = max(11, int(round(min(eq.shape[:2]) * 0.08)))
    if bs % 2 == 0:
        bs += 1
    if use_otsu:
        _, th = cv2.threshold(eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        th = cv2.adaptiveThreshold(
            eq,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            bs,
            7,
        )
    # MRZ: tamni znakovi na svijetloj podlozi
    if float(th.mean()) < 127.0:
        th = cv2.bitwise_not(th)
    bgr_out = cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)
    preprocessed_jpeg = _jpeg_encode_bgr(bgr_out)

    return MrzCropPipelineResult(
        crop_raw_jpeg=crop_raw_jpeg,
        deskewed_jpeg=deskewed_jpeg,
        preprocessed_jpeg=preprocessed_jpeg,
        deskew_angle_deg=ang,
        skew_source=src,
        crop_y0=y0,
        full_width=fw,
        full_height=fh,
    )


def preprocess_mrz_strip(image_bytes: bytes, *, upscale: int = 2) -> bytes:
    """
    Zastarjeli korak: grayscale + autocontrast + upscale (LANCZOS).
    Za MRZ drugi prolaz koristi ``build_mrz_crop_for_paddle_second_pass`` na punoj slici.
    """
    with Image.open(io.BytesIO(image_bytes)) as im:
        g = im.convert("L")
        g = ImageOps.autocontrast(g)
        if upscale > 1:
            nw, nh = g.size[0] * upscale, g.size[1] * upscale
            g = g.resize((nw, nh), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        g.convert("RGB").save(buf, format="JPEG", quality=92, optimize=True)
        return buf.getvalue()


def _shift_box_y(box: Any, dy: float) -> Any:
    if not isinstance(box, (list, tuple)) or not box:
        return box
    out: list[Any] = []
    for pt in box:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            try:
                x, y = float(pt[0]), float(pt[1])
                out.append([x, y + dy])
            except (TypeError, ValueError):
                out.append(list(pt))
        else:
            out.append(pt)
    return out


def _strip_has_truncated_td1_line2(in_strip: list[dict[str, Any]]) -> bool:
    """
    True ako puni kadar u MRZ traci ima prerezan TD1 red 2 (kratko + premalo filler «<»).

    Tada je strip_conf_max često visok, ali MRZ pipeline ne može validirati — bolji je crop prolaz.
    """
    for it in in_strip:
        norm = _normalize_text_for_mrz(str(it.get("text") or ""))
        if len(norm) < 15 or len(norm) > 28:
            continue
        if not norm[:6].isdigit():
            continue
        # Puni TD1-2 (30 znakova) ima tipično ≥5 «<» u državi/filler dijelu; OCR često završi na „…HRV<“.
        if norm.count("<") < 5:
            return True
    return False


def merge_fullframe_and_mrz_crop_items(
    full_items: list[dict[str, Any]],
    crop_items: list[dict[str, Any]],
    *,
    full_height: int,
    crop_y0: int,
    margin_px: float = 8.0,
) -> list[dict[str, Any]]:
    """
    U MRZ traci (donji dio slike) zamijeni puni-kadar Paddle s crop prolazom samo ako crop
    nije očito slabiji od onoga što je puni kadar već pročitao u toj zoni.

    Inače crop često ultra-široko „poboljša“ retke, a zapravo pokvari (npr. I→1, 0→U).
    """
    strip_y_min = float(crop_y0) - margin_px
    _ = full_height  # ostaje u potpisu radi kompatibilnosti s pozivateljima

    in_strip: list[dict[str, Any]] = []
    above_strip: list[dict[str, Any]] = []
    for it in full_items:
        cy = _centroid_y(it.get("box"))
        if cy is not None and cy >= strip_y_min:
            in_strip.append(dict(it))
        else:
            above_strip.append(dict(it))

    crop_conf_max = max((float(x.get("confidence") or 0.0) for x in crop_items), default=0.0)
    strip_conf_max = max((float(x.get("confidence") or 0.0) for x in in_strip), default=0.0)

    # Zahtijevaj barem jedan „jak“ puni-kadar signal u traci; inače crop (ili zadana logika ispod).
    prefer_full_strip = (
        bool(in_strip)
        and strip_conf_max >= 0.75
        and strip_conf_max >= crop_conf_max - 0.025
        and not _strip_has_truncated_td1_line2(in_strip)
    )

    if prefer_full_strip:
        return above_strip + in_strip

    kept: list[dict[str, Any]] = []
    for it in full_items:
        cy = _centroid_y(it.get("box"))
        if cy is not None and cy >= strip_y_min:
            continue
        kept.append(dict(it))

    dy = float(crop_y0)
    for it in crop_items:
        row = dict(it)
        box = row.get("box")
        if box is not None:
            row["box"] = _shift_box_y(box, dy)
        kept.append(row)
    return kept
