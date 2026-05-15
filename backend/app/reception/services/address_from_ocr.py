"""
Prebivalište / adresa iz Paddle OCR stavki (iznad MRZ trake).

Kad ``mrz_strip_y0`` nije poznat (npr. isključen drugi OCR prolaz), Y zona je
ograničena omjerom visine slike — manje pouzdano; preferiraj drugi prolaz.

Nakon izbora redaka primjenjuje se ``_normalize_address_diacritics_from_latin_ocr``:
Paddle s ``lang=latin`` često gubi Ä/Č/ß pa se tipične zamjene ispravljaju heuristički
(poznati primjeri + sufiks ``STRABE`` → ``STRAẞE``). Za druge ulice proširi pravila
ili uvedi hunspell/LLM drugi prolaz; za bolji izvor znakova probaj drugi Paddle ``lang``
u ``ocr_service`` (pazi na utjecaj na cijeli dokument).
"""

from __future__ import annotations

import re
from typing import Any

from reception.services.td1_mrz_extract import (
    _looks_like_td1_mrz_row,
    _normalize_text_for_mrz,
)

_Y_MARGIN_DEFAULT = 12.0
_MIN_CONFIDENCE = 0.85
# Iznad ovog omjera visine MRZ obično nije — adresa tipično gore.
_FALLBACK_ADDRESS_MAX_Y_RATIO = 0.55

_LABEL_PREBIVALISTE = re.compile(
    r"PREBIVALISTE|PREBIVALIŠTE|PREBIVALIST",
    re.IGNORECASE,
)
_LABEL_RESIDENCE = re.compile(r"RESIDENCE", re.IGNORECASE)

_STOP_BEFORE_ADDRESS = re.compile(
    r"(IZDALA|ISSUED\s*BY|DATUM\s*IZDAVANJA|DATE\s*OF\s*ISSUE|DATEOFISSUE|\bOIB\b)",
    re.IGNORECASE,
)


def _normalize_address_diacritics_from_latin_ocr(display: str) -> str:
    """
    Vrati tekst s tipičnim dijakriticima kad Paddle ``lang=latin`` pročita
    njemačko/hrvatsko polje kao čisti ASCII (Č→C, Ä→A, ẞ→B u ``STRABE``).

    Heuristike su namjerno uske (poznati primjeri + sufiks ``STRABE``) da se
    ne širi na cijeli OCR; za ostale ulice po potrebi proširi ovdje ili uvedi
    hunspell/LLM drugi prolaz.
    """
    if not display:
        return display
    s = display
    # Redoslijed: prvo dulji / specifičniji uzorci.
    s = re.sub(r"(?i)GARTNERSTRABE", "GÄRTNERSTRAẞE", s)
    s = re.sub(r"(?i)\bNJEMACKA\b", "NJEMAČKA", s)
    # "Straße" često kao STRABE (B umjesto ß); sufiks nakon slova ili cijela riječ STRABE.
    s = re.sub(r"(?i)(?<=[A-Za-zÄÖÜäöüß])STRABE(?=[,\s]|\d|$|\b)", "STRAẞE", s)
    s = re.sub(r"(?i)\bSTRABE\b", "STRAẞE", s)
    return s


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


def _display_line(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _is_residence_label_line(display: str) -> bool:
    if len(display) > 52:
        return False
    return bool(_LABEL_PREBIVALISTE.search(display) and _LABEL_RESIDENCE.search(display))


def _is_stop_line(display: str) -> bool:
    return bool(_STOP_BEFORE_ADDRESS.search(display))


def suggest_residence_address_from_items(
    items: list[dict[str, Any]],
    *,
    mrz_strip_y0: float | None = None,
    image_height: int | None = None,
    y_margin_px: float = _Y_MARGIN_DEFAULT,
    min_confidence: float = _MIN_CONFIDENCE,
) -> dict[str, Any]:
    """
    Vrati ``{"address": str, "address_lines": list[str]}`` ili prazan dict.

    ``address`` je ``", ".join(address_lines)`` radi jednostavnog binda na forme.
    """
    if not items:
        return {}

    cutoff: float | None = None
    if mrz_strip_y0 is not None:
        cutoff = float(mrz_strip_y0) - float(y_margin_px)
    elif image_height is not None and image_height > 0:
        cutoff = float(image_height) * _FALLBACK_ADDRESS_MAX_Y_RATIO

    scored: list[tuple[float, str, str]] = []
    for it in items:
        raw = str(it.get("text") or "")
        display = _display_line(raw)
        if not display:
            continue
        cy = _centroid_y(it.get("box"))
        if cy is None:
            continue
        if cutoff is not None and cy >= cutoff:
            continue

        conf = it.get("confidence")
        if isinstance(conf, (int, float)) and float(conf) < min_confidence:
            continue

        norm = _normalize_text_for_mrz(raw)
        if _looks_like_td1_mrz_row(norm):
            continue

        scored.append((cy, display, norm))

    scored.sort(key=lambda t: t[0])

    lines_out: list[str] = []
    started = False
    for _cy, display, _norm in scored:
        if _is_stop_line(display):
            break
        if _is_residence_label_line(display):
            continue
        if not started and len(display) <= 2:
            continue
        lines_out.append(_normalize_address_diacritics_from_latin_ocr(display))
        started = True

    if not lines_out:
        return {}

    return {
        "address_lines": lines_out,
        "address": ", ".join(lines_out),
    }
