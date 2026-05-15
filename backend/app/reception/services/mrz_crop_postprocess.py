"""
MRZ-specific cleanup nakon PaddleOCR-a na MRZ cropu (prije merge-a s punim kadrom).
"""

from __future__ import annotations

import re
from typing import Any

from reception.services.td1_mrz_extract import TD1_LINE_LEN

_MRZ_ALLOWED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")
_TD1_LINE1_HEAD = re.compile(r"^I[0<]")
# TD1 linija 2: datumi + check znamenke (pozicije 0–6, 8–14)
_LINE2_DIGIT_SLOTS = frozenset(range(0, 7)) | frozenset(range(8, 15))


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


def _filler_context_map(s: str) -> str:
    """«, ‹, K, > u tipičnom MRZ filler kontekstu -> <."""
    t = s.upper().replace(" ", "").replace("\n", "").replace("\t", "")
    t = t.replace("—", "-").replace("«", "<").replace("‹", "<").replace("＜", "<")
    t = re.sub(r"(?<=[A-Z0-9])K(?=[<A-Z]{2,})", "<", t)
    t = re.sub(r"(?<=<)K(?=<)", "<", t)
    t = re.sub(r"(?<=[<A-Z0-9])>(?=[<A-Z0-9])", "<", t)
    return t


def _row_kind(line: str) -> str:
    t = _filler_context_map(line)
    t = "".join(c for c in t if c in _MRZ_ALLOWED)
    if _TD1_LINE1_HEAD.match(t):
        return "line1"
    if len(t) >= 15 and sum(1 for c in t[:15] if c.isdigit()) >= 5:
        return "line2"
    return "line3"


def _pad_30(t: str) -> str:
    u = "".join(c for c in t if c in _MRZ_ALLOWED)
    if len(u) > TD1_LINE_LEN:
        u = u[:TD1_LINE_LEN]
    return u.ljust(TD1_LINE_LEN, "<")


def _oz_on_digit_slots_only(line: str, slots: frozenset[int]) -> str:
    ch = list(line[:TD1_LINE_LEN].ljust(TD1_LINE_LEN, "<"))
    for i in slots:
        if i >= len(ch):
            continue
        c = ch[i]
        if c in "Oo":
            ch[i] = "0"
        elif c in "Zz":
            ch[i] = "2"
    return "".join(ch)


def normalize_mrz_crop_paddle_text(text: str, *, row_hint: str | None = None) -> str:
    """
    - filler znakovi u kontekstu -> <
    - samo MRZ skup; red do 30 znakova
    - O->0, Z->2 samo na pozicijama koje u TD1 liniji 2 očekuju znamenku
    """
    raw = str(text or "")
    t = _filler_context_map(raw)
    t = "".join(c for c in t if c in _MRZ_ALLOWED)
    kind = row_hint or _row_kind(t)
    if kind == "line2":
        t = _oz_on_digit_slots_only(t, _LINE2_DIGIT_SLOTS)
    return _pad_30(t)


def normalize_mrz_crop_paddle_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sortiraj po Y (gore-dolje), dodijeli hint reda za donje 3 stavke, normaliziraj tekst."""
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for i, it in enumerate(items):
        cy = _centroid_y(it.get("box"))
        scored.append((cy if cy is not None else 1e9, i, dict(it)))
    scored.sort(key=lambda x: (x[0], x[1]))
    n = len(scored)
    out: list[dict[str, Any]] = []
    for rank, (_y, _i, row) in enumerate(scored):
        txt = str(row.get("text") or "")
        hint: str | None = None
        # Tri MRZ retka u cropu idu gore→dolje (rastuci Y); dodatni bbox (šum) je obično ispod treceg retka.
        # Stari ``rank >= n-3`` za n>3 krivo preskace prvi red i pomice hintove (line1→stvarni line2).
        if n >= 3 and rank < 3:
            hint = ("line1", "line2", "line3")[rank]
        row["text"] = normalize_mrz_crop_paddle_text(txt, row_hint=hint)
        out.append(row)
    return out
