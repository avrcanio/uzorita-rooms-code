from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import urljoin

import httpx
from django.conf import settings


class OCRServiceError(Exception):
    """Raised when PaddleOCR HTTP call fails or returns an unexpected payload."""


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


def _walk_for_text_items(obj: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        if isinstance(obj.get("text"), str):
            out.append(
                {
                    "text": obj["text"],
                    "confidence": obj.get("confidence"),
                    "box": obj.get("box")
                    or obj.get("dt_boxes")
                    or obj.get("bbox")
                    or obj.get("text_region"),
                }
            )
        for v in obj.values():
            _walk_for_text_items(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_for_text_items(v, out)


def normalize_paddle_response(response_json: Any) -> tuple[list[dict[str, Any]], Any]:
    """
    Flatten common Paddle / PaddleHub-style JSON into text items with optional box + confidence.
    """
    items: list[dict[str, Any]] = []
    _walk_for_text_items(response_json, items)
    if not items and isinstance(response_json, dict):
        data = response_json.get("data")
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict) and isinstance(row.get("text"), str):
                    items.append(
                        {
                            "text": row["text"],
                            "confidence": row.get("confidence"),
                            "box": row.get("box") or row.get("dt_boxes"),
                        }
                    )
        # PaddleHub Serving: {"results": [[{text, confidence, text_region}, ...]]}
        if not items:
            results = response_json.get("results")
            if isinstance(results, list) and results:
                first = results[0]
                if isinstance(first, list):
                    for row in first:
                        if isinstance(row, dict) and isinstance(row.get("text"), str):
                            items.append(
                                {
                                    "text": row["text"],
                                    "confidence": row.get("confidence"),
                                    "box": row.get("text_region") or row.get("box"),
                                }
                            )
    return items, response_json


class OCRService:
    """HTTP client for a PaddleOCR inference container."""

    def __init__(self) -> None:
        self._base = (getattr(settings, "PADDLE_OCR_BASE_URL", "") or "").rstrip("/")
        self._path = getattr(settings, "PADDLE_OCR_PREDICT_PATH", "/predict") or "/predict"
        self._field = getattr(settings, "PADDLE_OCR_FILE_FIELD", "file") or "file"
        self._request_format = (
            getattr(settings, "PADDLE_OCR_REQUEST_FORMAT", "multipart") or "multipart"
        ).lower()
        self._timeout = float(getattr(settings, "PADDLE_OCR_TIMEOUT_SECONDS", 90))

    def is_configured(self) -> bool:
        return bool(self._base)

    def predict(self, *, image_bytes: bytes, filename: str, content_type: str | None) -> dict[str, Any]:
        if not self._base:
            raise OCRServiceError("PADDLE_OCR_BASE_URL nije konfiguriran.")

        url = urljoin(self._base + "/", self._path.lstrip("/"))

        try:
            with httpx.Client(timeout=self._timeout) as client:
                if self._request_format == "json_images":
                    b64 = base64.b64encode(image_bytes).decode("ascii")
                    response = client.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        json={"images": [b64]},
                    )
                else:
                    ct = content_type or "application/octet-stream"
                    files = {self._field: (filename or "image.bin", image_bytes, ct)}
                    response = client.post(url, files=files)
        except httpx.TimeoutException as exc:
            raise OCRServiceError("PaddleOCR servis je timeout.") from exc
        except httpx.RequestError as exc:
            raise OCRServiceError(f"PaddleOCR mrežna greška: {exc}") from exc

        if response.status_code >= 400:
            raise OCRServiceError(
                f"PaddleOCR HTTP {response.status_code}: {response.text[:500]!r}"
            )

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise OCRServiceError("PaddleOCR odgovor nije JSON.") from exc

        items, raw = normalize_paddle_response(payload)
        return {"items": items, "raw": raw, "http_status": response.status_code}
