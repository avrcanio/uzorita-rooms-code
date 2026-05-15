from __future__ import annotations

import base64
import binascii
import inspect
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from paddleocr import PaddleOCR
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("uvicorn.error")


def _ocr_trace_enabled() -> bool:
    return os.getenv("OCR_TRACE_LOG", "1").strip().lower() in {"1", "true", "yes", "on"}

_MAX_IMAGES = 4


@asynccontextmanager
async def lifespan(app: FastAPI):
    kwargs: dict[str, Any] = {
        "use_angle_cls": True,
        "lang": "latin",
        "use_gpu": False,
        "enable_mkldnn": True,
        "show_log": False,
    }
    sig = inspect.signature(PaddleOCR.__init__)
    if "cpu_threads" in sig.parameters:
        kwargs["cpu_threads"] = 6
    app.state.ocr = PaddleOCR(**kwargs)
    yield


app = FastAPI(title="PaddleOCR", lifespan=lifespan)


_MRZ_RECOG_ALLOW = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")


class PredictRequest(BaseModel):
    images: list[str] = Field(..., description="Base64-encoded image bytes")
    # MRZ drugi prolaz: ograniči prepoznati tekst na ICAO MRZ skup (kad je true).
    mrz_crop: bool = False

    @field_validator("images")
    @classmethod
    def nonempty_and_cap(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("images must be non-empty")
        if len(v) > _MAX_IMAGES:
            raise ValueError(f"at most {_MAX_IMAGES} images allowed")
        return v


def _line_to_item(line: Any) -> dict[str, Any] | None:
    if not isinstance(line, (list, tuple)) or len(line) < 2:
        return None
    box, rec = line[0], line[1]
    if not isinstance(rec, (list, tuple)) or len(rec) < 2:
        return None
    text, confidence = rec[0], rec[1]
    if not isinstance(text, str):
        return None
    try:
        conf_f = float(confidence)
    except (TypeError, ValueError):
        conf_f = 0.0
    if hasattr(box, "tolist"):
        region = box.tolist()
    else:
        try:
            region = [[float(p[0]), float(p[1])] for p in box]  # type: ignore[index]
        except (TypeError, ValueError, IndexError):
            return None
    return {"text": text, "confidence": conf_f, "text_region": region}


def _ocr_lines(ocr: PaddleOCR, image_bgr: np.ndarray) -> list[dict[str, Any]]:
    raw = ocr.ocr(image_bgr, det=True, rec=True, cls=True)
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    for page in raw:
        if page is None or not isinstance(page, list):
            continue
        for line in page:
            if line is None:
                continue
            item = _line_to_item(line)
            if item:
                out.append(item)
    return out


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/predict")
def predict(body: PredictRequest) -> dict[str, list[list[dict[str, Any]]]]:
    ocr: PaddleOCR = app.state.ocr
    results: list[list[dict[str, Any]]] = []
    t0 = time.perf_counter()
    if _ocr_trace_enabled():
        logger.info(
            "predict: images=%d b64_lens=%s",
            len(body.images),
            [len(x) for x in body.images],
        )
    for idx, b64 in enumerate(body.images):
        try:
            raw_bytes = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=400, detail="Invalid base64 image data")
        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image data")
        h, w = image.shape[:2]
        t_img = time.perf_counter()
        try:
            lines = _ocr_lines(ocr, image)
        except HTTPException:
            raise
        except Exception:
            logger.exception("OCR failed")
            raise HTTPException(status_code=500, detail="Internal server error")
        if body.mrz_crop:
            for item in lines:
                t = item.get("text")
                if not isinstance(t, str):
                    continue
                item["text"] = "".join(ch for ch in t.upper() if ch in _MRZ_RECOG_ALLOW)
        results.append(lines)
        if _ocr_trace_enabled():
            dt_ms = int((time.perf_counter() - t_img) * 1000)
            logger.info(
                "predict: image[%d] shape=%dx%d decode_bytes=%d lines=%d ocr_ms=%d",
                idx,
                w,
                h,
                len(raw_bytes),
                len(lines),
                dt_ms,
            )
            for li, item in enumerate(lines):
                txt = item.get("text") or ""
                conf = item.get("confidence")
                reg = item.get("text_region")
                logger.info(
                    "predict: image[%d] line[%d] conf=%s text=%r region=%s",
                    idx,
                    li,
                    conf,
                    txt,
                    reg,
                )
    if _ocr_trace_enabled():
        logger.info(
            "predict: done total_ms=%d", int((time.perf_counter() - t0) * 1000)
        )
    return {"results": results}
