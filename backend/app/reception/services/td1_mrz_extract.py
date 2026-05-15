"""
Izdvajanje TD1 MRZ (3×30) iz Paddle OCR stavki — bez adresnih i ostalih polja dokumenta.
"""

from __future__ import annotations

import re
from typing import Any

_TD1_LINE1_ANCHOR = re.compile(r"I[0<][A-Z]{3}\d")
_ALLOWED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")
TD1_LINE_LEN = 30


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


def _normalize_text_for_mrz(text: str) -> str:
    raw = text.upper().replace(" ", "").replace("\n", "").replace("\t", "")
    raw = raw.replace("—", "-").replace("«", "<").replace("‹", "<").replace("＜", "<")
    raw = re.sub(r"[^A-Z0-9<K]", "", raw)
    # K u kontekstu punjenja (između < ili na kraju niza chevrona): tipična OCR greška za <
    raw = re.sub(r"(?<=[A-Z0-9])K(?=[<A-Z]{2,})", "<", raw)
    raw = re.sub(r"(?<=<)K(?=<)", "<", raw)
    raw = re.sub(r"[^A-Z0-9<]", "", raw)
    return raw


def _mrz_char_ratio(s: str) -> float:
    if not s:
        return 0.0
    ok = sum(1 for c in s if c in _ALLOWED)
    return ok / len(s)


def _looks_like_td1_mrz_row(t: str) -> bool:
    if len(t) < 15:
        return False
    if _mrz_char_ratio(t) < 0.88:
        return False
    if _TD1_LINE1_ANCHOR.search(t):
        return True
    digits = sum(1 for c in t if c.isdigit())
    if digits >= 4:
        return True
    # TD1 treći red: puno «<», malo znamenki (prezime<<ime)
    if "<" in t and digits <= 3:
        return True
    return False


def _looks_like_td1_name_only_row(t: str) -> bool:
    """Treći MRZ red često nema '<' u OCR-u; strogo ograniči da ne pokupi adresu."""
    if len(t) < 8 or len(t) > 34:
        return False
    if _mrz_char_ratio(t) < 0.82:
        return False
    if "<" in t:
        return False
    digits = sum(1 for c in t if c.isdigit())
    if digits > 4:
        return False
    letters = sum(1 for c in t if c.isalpha())
    return letters >= 6


def _append_loose_name_row_if_pair(
    items: list[dict[str, Any]],
    scored: list[dict[str, Any]],
) -> None:
    """
    Kad imamo točno 2 stroga MRZ retka (linija 1 + linija 2), a treći OCR nema '<',
    dopuni treći red iz najniže stavke koja izgleda kao ime/prezime (bez rušenja pipelinea).
    """
    if len(scored) != 2:
        return
    scored.sort(key=lambda r: r["y"])
    t0, t1 = scored[0]["text"], scored[1]["text"]
    if not (_TD1_LINE1_ANCHOR.search(t0) and sum(1 for c in t1 if c.isdigit()) >= 6):
        return
    y_floor = scored[1]["y"] + 3.0
    best: dict[str, Any] | None = None
    best_key: tuple[float, int] = (-1.0, -1)
    seen_text = {s["text"] for s in scored}
    for it in items:
        raw_t = str(it.get("text") or "")
        norm = _normalize_text_for_mrz(raw_t)
        if not norm or norm in seen_text:
            continue
        if not _looks_like_td1_name_only_row(norm):
            continue
        cy = _centroid_y(it.get("box"))
        if cy is None or cy < y_floor:
            continue
        conf = it.get("confidence")
        conf_f = float(conf) if isinstance(conf, (int, float)) else 0.55
        key = (cy, int(conf_f * 1000))
        if key > best_key:
            best_key = key
            best = {
                "text": norm,
                "y": cy,
                "confidence": conf_f,
                "score": _score_item(norm, cy, conf_f, None, None),
                "in_bottom_40": False,
                "in_mrz_strip": False,
            }
    if best is not None:
        scored.append(best)


def _row_width_30(s: str) -> str:
    t = "".join(c for c in s if c in _ALLOWED)
    if len(t) > TD1_LINE_LEN:
        t = t[:TD1_LINE_LEN]
    return t.ljust(TD1_LINE_LEN, "<")


def _score_item(norm: str, y: float, conf: float | None, image_height: int | None, strip_y0: float | None) -> float:
    base = _mrz_char_ratio(norm) * (1.6 if _TD1_LINE1_ANCHOR.search(norm) else 1.0) * (float(conf) if conf is not None else 0.55)
    if image_height and image_height > 0 and y >= 0.60 * float(image_height):
        base *= 1.45
    if strip_y0 is not None and y >= strip_y0 - 12.0:
        base *= 1.35
    return base


def extract_td1_mrz_from_ocr(
    items: list[dict[str, Any]],
    *,
    image_height: int | None = None,
    mrz_strip_y0: float | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """
    Vrati (najviše 3) TD1 MRZ retka širine 30 i meta s kandidatima za debug.

    Ne uključuje adresu / izdavatelja / OIB polja koja ne zadovoljavaju MRZ-like heuristiku.
    """
    scored: list[dict[str, Any]] = []
    for it in items:
        raw_t = str(it.get("text") or "")
        norm = _normalize_text_for_mrz(raw_t)
        if not _looks_like_td1_mrz_row(norm):
            continue
        cy = _centroid_y(it.get("box"))
        if cy is None:
            continue
        conf = it.get("confidence")
        conf_f = float(conf) if isinstance(conf, (int, float)) else None
        scored.append(
            {
                "text": norm,
                "y": cy,
                "confidence": conf_f,
                "score": _score_item(norm, cy, conf_f, image_height, mrz_strip_y0),
                "in_bottom_40": bool(image_height and cy >= 0.60 * float(image_height)),
                "in_mrz_strip": bool(mrz_strip_y0 is not None and cy >= mrz_strip_y0 - 12.0),
            }
        )

    _append_loose_name_row_if_pair(items, scored)
    scored.sort(key=lambda r: r["y"])
    bottom = [s for s in scored if image_height and s["y"] >= 0.60 * float(image_height)]
    pool = bottom if len(bottom) >= 3 else scored
    tail = pool[-3:] if len(pool) >= 3 else pool[:]
    lines_30 = [_row_width_30(x["text"]) for x in tail]
    meta = {
        "candidates": scored,
        "pool_source": "bottom_40" if len(bottom) >= 3 else "all_mrz_like",
        "picked_count": len(lines_30),
    }
    return lines_30, meta


def td1_lines_are_valid_shape(lines: list[str]) -> bool:
    if len(lines) != 3:
        return False
    pat = re.compile(r"^[A-Z0-9<]{30}$")
    return all(pat.match(line) for line in lines)


def soften_td1_line3_garbage(line3: str) -> str:
    """OCR treći red: očisti ne-MRZ znakove u <, zadrži strukturu << za ime/prezime."""
    t = "".join(c if c in _ALLOWED else "<" for c in line3.upper())
    if "<<" not in t and len(t) >= 6:
        i = 0
        while i < len(t) and t[i] not in "0123456789<":
            i += 1
        if i > 2:
            t = t[:i] + "<<" + t[i:]
    return _row_width_30(t)


def apply_td1_position_ocr_hints(line1: str, line2: str, line3: str) -> tuple[str, str, str]:
    """
    Ograničene zamjene na TD1 pozicijama: znamenke u datumskim poljima linije 2, spol, HRV.
    """
    d_fix = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6"})
    l_fix = str.maketrans({"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B"})

    def fix_l2(s: str) -> str:
        ch = list(s[:TD1_LINE_LEN].ljust(TD1_LINE_LEN, "<"))
        digit_slots = {0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14}
        for i in digit_slots:
            if i < len(ch) and ch[i] not in "0123456789<":
                ch[i] = ch[i].translate(d_fix) if ch[i].translate(d_fix) != ch[i] else ch[i]
        if 7 < len(ch) and ch[7] not in "MF<":
            ch[7] = "M" if ch[7] in ("N", "W") else "<"
        for i in (15, 16, 17):
            if i < len(ch) and ch[i] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ<":
                ch[i] = ch[i].translate(l_fix)
        return "".join(ch)[:TD1_LINE_LEN].ljust(TD1_LINE_LEN, "<")

    l1l = list(line1[:TD1_LINE_LEN].ljust(TD1_LINE_LEN, "<"))
    for i in range(min(14, len(l1l))):
        if i < 2 and l1l[i] in "08":
            l1l[i] = {"0": "O", "8": "B"}.get(l1l[i], l1l[i])
        if 2 <= i <= 4 and l1l[i].isdigit():
            l1l[i] = l1l[i].translate(l_fix)
    line1_f = "".join(l1l)[:TD1_LINE_LEN].ljust(TD1_LINE_LEN, "<")
    line2_f = fix_l2(line2)
    line3_f = soften_td1_line3_garbage(line3)
    return line1_f, line2_f, line3_f
