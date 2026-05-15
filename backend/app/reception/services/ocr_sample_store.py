"""
Optional persistence of raw scan uploads for debugging / tuning OCR (opt-in via settings).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bin"}


def save_scan_upload_sample(
    image_bytes: bytes,
    *,
    guest_id: int,
    original_filename: str | None,
) -> str | None:
    """
    If SCAN_OCR_SAMPLE_DIR is non-empty, write bytes to that directory (default media/id_documents)
    and return the file path
    (relative to BASE_DIR when under it, else absolute). Returns None if disabled or on error.
    """
    root = (getattr(settings, "SCAN_OCR_SAMPLE_DIR", None) or "").strip()
    if not root or not image_bytes:
        return None

    try:
        path = Path(root)
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("ocr_sample: cannot create sample dir %r: %s", root, exc)
        return None

    ext = ".jpg"
    if original_filename and "." in original_filename:
        cand = Path(original_filename).suffix.lower()[:8]
        if cand in _ALLOWED_SUFFIXES:
            ext = cand
    stem = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + f"_guest{guest_id}_{uuid.uuid4().hex[:8]}"
    )
    out = path / f"{stem}{ext}"
    try:
        out.write_bytes(image_bytes)
    except OSError as exc:
        logger.warning("ocr_sample: cannot write %s: %s", out, exc)
        return None

    try:
        base = Path(settings.BASE_DIR).resolve()
        resolved = out.resolve()
        if resolved.is_relative_to(base):
            return str(resolved.relative_to(base))
    except (OSError, ValueError):
        pass
    return str(out.resolve())


def save_scan_debug_sidecar(
    sample_relpath: str | None,
    data: dict[str, Any],
) -> str | None:
    """
    Write <stem>.json next to the saved image when SCAN_OCR_DEBUG_JSON is true
    and sample_relpath points at the image file (same directory as SCAN_OCR_SAMPLE_DIR).
    """
    if not sample_relpath or not getattr(settings, "SCAN_OCR_DEBUG_JSON", True):
        return None

    try:
        img = Path(sample_relpath)
        if not img.is_absolute():
            img = Path(settings.BASE_DIR) / img
        img = img.resolve()
        if not img.is_file():
            return None
        out = img.with_suffix(".json")
        body = json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n"
        out.write_text(body, encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("ocr_sample: cannot write debug json %s: %s", sample_relpath, exc)
        return None

    try:
        base = Path(settings.BASE_DIR).resolve()
        if out.resolve().is_relative_to(base):
            return str(out.resolve().relative_to(base))
    except (OSError, ValueError):
        pass
    return str(out.resolve())


def save_mrz_crop_debug_stages(
    sample_relpath: str | None,
    *,
    full_original_bytes: bytes,
    crop_raw_jpeg: bytes,
    deskewed_jpeg: bytes,
    preprocessed_jpeg: bytes,
) -> dict[str, str | None]:
    """
    Uz spremljeni upload (SCAN_OCR_SAMPLE_DIR) zapiši MRZ debug faze:
    ``{stem}_mrz_original.jpg``, ``{stem}_mrz_crop_raw.jpg``,
    ``{stem}_mrz_crop_deskewed.jpg``, ``{stem}_mrz_crop_preprocessed.jpg``.
    """
    out_paths: dict[str, str | None] = {
        "mrz_original": None,
        "mrz_crop_raw": None,
        "mrz_crop_deskewed": None,
        "mrz_crop_preprocessed": None,
    }
    if not sample_relpath or not getattr(settings, "MRZ_CROP_DEBUG_IMAGES", True):
        return out_paths
    root = (getattr(settings, "SCAN_OCR_SAMPLE_DIR", None) or "").strip()
    if not root:
        return out_paths

    try:
        img = Path(sample_relpath)
        if not img.is_absolute():
            img = Path(settings.BASE_DIR) / img
        img = img.resolve()
        if not img.is_file():
            return out_paths
        parent = img.parent
        stem = img.stem
        mapping = {
            "mrz_original": full_original_bytes,
            "mrz_crop_raw": crop_raw_jpeg,
            "mrz_crop_deskewed": deskewed_jpeg,
            "mrz_crop_preprocessed": preprocessed_jpeg,
        }
        for key, suffix in (
            ("mrz_original", "_mrz_original.jpg"),
            ("mrz_crop_raw", "_mrz_crop_raw.jpg"),
            ("mrz_crop_deskewed", "_mrz_crop_deskewed.jpg"),
            ("mrz_crop_preprocessed", "_mrz_crop_preprocessed.jpg"),
        ):
            target = parent / f"{stem}{suffix}"
            target.write_bytes(mapping[key])
            try:
                base = Path(settings.BASE_DIR).resolve()
                if target.resolve().is_relative_to(base):
                    out_paths[key] = str(target.resolve().relative_to(base))
                else:
                    out_paths[key] = str(target.resolve())
            except (OSError, ValueError):
                out_paths[key] = str(target.resolve())
    except OSError as exc:
        logger.warning("ocr_sample: cannot write mrz crop debug %s: %s", sample_relpath, exc)
    return out_paths


def save_scan_paddle_raw_sidecar(
    sample_relpath: str | None,
    *,
    paddle_response: Any,
    paddle_response_mrz_crop: Any,
    mrz_second_pass: dict[str, Any] | None,
) -> str | None:
    """
    Write <stem>.paddle.json next to the image: raw Paddle JSON (full frame + optional MRZ crop pass).
    """
    if not sample_relpath or not getattr(settings, "SCAN_OCR_PADDLE_RAW_JSON", True):
        return None

    try:
        img = Path(sample_relpath)
        if not img.is_absolute():
            img = Path(settings.BASE_DIR) / img
        img = img.resolve()
        if not img.is_file():
            return None
        out = img.parent / f"{img.stem}.paddle.json"
        payload = {
            "paddle_response": paddle_response,
            "paddle_response_mrz_crop": paddle_response_mrz_crop,
            "mrz_second_pass": mrz_second_pass or {},
        }
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"
        out.write_text(body, encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("ocr_sample: cannot write paddle raw json %s: %s", sample_relpath, exc)
        return None

    try:
        base = Path(settings.BASE_DIR).resolve()
        if out.resolve().is_relative_to(base):
            return str(out.resolve().relative_to(base))
    except (OSError, ValueError):
        pass
    return str(out.resolve())
