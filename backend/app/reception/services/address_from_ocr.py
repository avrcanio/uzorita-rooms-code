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
_BLOB_LABEL = re.compile(
    r"PREBIVALI[ŠS]TE.*?RESIDENCE",
    re.IGNORECASE,
)
_BLOB_STOP = re.compile(
    r"(?:IZDALA|ISSUED\s*BY|DATUM\s*IZDAVANJA|DATE\s*OF\s*ISSUE|DATEOFISSUE|\bOIB\b|\bMBO\b)",
    re.IGNORECASE,
)
# Šum iz OCR-a (npr. "KCard", datum s ghost portreta)
_BLOB_NOISE = re.compile(
    r"\b(?:KCARD|K\s*CARD)\b|\b\d{1,2}\s*[-/]?\s*\d{1,2}\s*[-/]?\s*\d{4}\b",
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


def _split_city_street_heuristic(text: str) -> list[str]:
    """``NJEMACKAHANAU`` / ``NSJEMACKAHANAU`` → ``NJEMAČKA, HANAU`` kad OCR spoji bez zareza."""
    s = text.strip()
    if not s:
        return []

    # Ulica u zasebnom tokenu (npr. ``NSJEMACKAHANAU GARTNERSTRABE4A``).
    tokens = s.split()
    if len(tokens) >= 2 and re.search(r"STRABE|STRA[SßB]|GART", tokens[-1], re.IGNORECASE):
        city_blob = " ".join(tokens[:-1])
        street = tokens[-1]
        city_lines = _split_city_street_heuristic(city_blob)
        street_n = _normalize_address_diacritics_from_latin_ocr(street)
        return [*city_lines, street_n]

    m = re.match(
        r"^(NJEMACKA|NJEMAČKA|GERMANY|DEUTSCHLAND)\s*,?\s*(.+)$",
        s,
        re.IGNORECASE,
    )
    if m:
        city = _normalize_address_diacritics_from_latin_ocr(m.group(1).strip())
        rest = _normalize_address_diacritics_from_latin_ocr(m.group(2).strip())
        if rest:
            return [city, rest]
        return [city]
    m2 = re.match(
        r"^(?:NS|N|S)?J?EMACKA(HANAU|[A-ZČĆŽŠĐ][A-ZČĆŽŠĐa-zčćžšđ\-]+)$",
        s,
        re.IGNORECASE,
    )
    if m2:
        country = _normalize_address_diacritics_from_latin_ocr("NJEMACKA")
        city = _normalize_address_diacritics_from_latin_ocr(m2.group(1))
        return [f"{country}, {city}"]
    return [_normalize_address_diacritics_from_latin_ocr(s)]


def _is_plausible_address_line(display: str) -> bool:
    """Adresni red — ne koristiti ``_looks_like_td1_mrz_row`` (preagresivno na latinici)."""
    if len(display) < 3 or _is_stop_line(display):
        return False
    if display.count("<") >= 4:
        return False
    letters = sum(1 for c in display if c.isalpha())
    return letters >= 4


def _extract_address_lines_from_blob(blob: str) -> list[str]:
    """
    Kad Paddle vrati jedan dugačak OCR redak (label + adresa + IZDALA u istom stringu),
    izreži dio između PREBIVALIŠTE/RESIDENCE i sljedećeg administrativnog polja.
    """
    raw = _display_line(blob)
    if not raw or not _BLOB_LABEL.search(raw):
        return []
    m_label = _BLOB_LABEL.search(raw)
    assert m_label is not None
    tail = raw[m_label.end() :].strip(" :/-")
    m_stop = _BLOB_STOP.search(tail)
    if m_stop:
        tail = tail[: m_stop.start()].strip()
    tail = _BLOB_NOISE.sub(" ", tail)
    tail = " ".join(tail.split())
    if len(tail) < 3:
        return []

    parts: list[str] = []
    if "," in tail:
        parts = [p.strip() for p in tail.split(",") if p.strip()]
    else:
        parts = _split_city_street_heuristic(tail)

    out: list[str] = []
    for p in parts:
        p = _normalize_address_diacritics_from_latin_ocr(p)
        if _is_plausible_address_line(p):
            out.append(p)
    return out


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
    blob_candidates: list[str] = []
    for idx, it in enumerate(items):
        raw = str(it.get("text") or "")
        display = _display_line(raw)
        if not display:
            continue
        cy = _centroid_y(it.get("box"))
        if cy is None:
            cy = float(idx)
        if cutoff is not None and cy >= cutoff:
            continue

        conf = it.get("confidence")
        if isinstance(conf, (int, float)) and float(conf) < min_confidence:
            continue

        is_residence_blob = bool(
            _BLOB_LABEL.search(display)
            and (_BLOB_STOP.search(display) or len(display) > 52)
        )
        if is_residence_blob:
            blob_candidates.append(display)

        norm = _normalize_text_for_mrz(raw)
        if _looks_like_td1_mrz_row(norm) and not is_residence_blob:
            continue

        scored.append((cy, display, norm))

    scored.sort(key=lambda t: t[0])

    lines_out: list[str] = []
    started = False
    for _cy, display, _norm in scored:
        if _is_residence_label_line(display):
            continue
        if _is_stop_line(display):
            if started:
                break
            blob_lines = _extract_address_lines_from_blob(display)
            if blob_lines:
                lines_out.extend(blob_lines)
                started = True
            break
        if not started and len(display) <= 2:
            continue
        line = _normalize_address_diacritics_from_latin_ocr(display)
        if _is_plausible_address_line(line):
            lines_out.append(line)
            started = True

    if not lines_out and blob_candidates:
        for blob in blob_candidates:
            lines_out.extend(_extract_address_lines_from_blob(blob))
        # Dedupe uz očuvanje redoslijeda
        seen: set[str] = set()
        deduped: list[str] = []
        for ln in lines_out:
            key = ln.upper()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(ln)
        lines_out = deduped

    if not lines_out:
        return {}

    return {
        "address_lines": lines_out,
        "address": ", ".join(lines_out),
    }
