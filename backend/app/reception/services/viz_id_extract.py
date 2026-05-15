"""
VIZ (vizualna zona) polja s prednje strane hr. osobne iskaznice i sidra za MRZ na stražnjoj.
"""

from __future__ import annotations

import re
from typing import Any

from mrz.generator.td1 import TD1CodeGenerator

_LABEL_SURNAME = re.compile(r"PREZIME|SURNAME", re.IGNORECASE)
_LABEL_GIVEN = re.compile(r"\bIME\b|GIVEN\s*NAME", re.IGNORECASE)
_LABEL_DOC_NO = re.compile(
    r"BROJ\s*OSOBNE|IDENTITY\s*CARD\s*NUMBER|DOCUMENT\s*NO",
    re.IGNORECASE,
)
_LABEL_DOB = re.compile(r"DATUM\s*RODJENJA|DATUM\s*ROĐENJA|DATE\s*OF\s*BIRTH", re.IGNORECASE)
_LABEL_EXPIRY = re.compile(r"VRIJEDI\s*DO|DATE\s*OF\s*EXPIRY|EXPIRY", re.IGNORECASE)
_LABEL_SEX = re.compile(r"\bSPOL\b|\bSEX\b", re.IGNORECASE)

_DATE_VIZ = re.compile(r"(\d{1,2})\s+(\d{1,2})\s+(\d{4})")
_DOC_NUMBER = re.compile(r"\b(\d{9})\b")
_NAME_VALUE = re.compile(r"^[A-ZČĆŽŠĐ][A-ZČĆŽŠĐ\-']{1,39}$", re.IGNORECASE)


def _centroid_xy(box: Any) -> tuple[float, float] | None:
    if not isinstance(box, (list, tuple)) or len(box) < 2:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for pt in box:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            try:
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))
            except (TypeError, ValueError):
                continue
    if not xs:
        return None
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _display_line(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _date_to_yymmdd(day: str, month: str, year: str) -> str:
    yy = year[-2:]
    return f"{yy}{int(month):02d}{int(day):02d}"


def normalize_viz_hints(data: dict[str, Any] | None) -> dict[str, str]:
    """Uskladi ključeve iz Fluttera / OCR-a."""
    if not data:
        return {}
    aliases = {
        "surname": ("surname", "prezime", "last_name"),
        "given_names": ("given_names", "given_name", "ime", "first_name"),
        "document_number": ("document_number", "broj_dokumenta", "doc_no"),
        "birth_yymmdd": ("birth_yymmdd", "birth_yyMMdd", "datum_rodenja"),
        "expiry_yymmdd": ("expiry_yymmdd", "datum_isteka"),
        "sex": ("sex", "spol"),
        "nationality": ("nationality", "drzavljanstvo", "citizenship"),
        "oib": ("oib", "personal_id_number"),
    }
    out: dict[str, str] = {}
    lower_map = {str(k).lower(): v for k, v in data.items()}
    for canonical, keys in aliases.items():
        for k in keys:
            raw = lower_map.get(k)
            if raw is None:
                continue
            s = str(raw).strip()
            if s:
                out[canonical] = s
            break
    return out


def _value_after_label(text: str, label: re.Pattern[str]) -> str | None:
    m = label.search(text)
    if not m:
        return None
    tail = text[m.end() :].strip(" :/-")
    if not tail:
        return None
    if _DATE_VIZ.search(tail):
        dm = _DATE_VIZ.search(tail)
        if dm:
            return _date_to_yymmdd(dm.group(1), dm.group(2), dm.group(3))
    parts = tail.split()
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if _NAME_VALUE.match(p) and len(p) >= 2:
            return p.upper()
        if p.isdigit() and len(p) == 9:
            return p
        if p.upper() in ("M", "F", "M/M", "F/F"):
            return p[0].upper()
    return parts[0].upper() if parts and _NAME_VALUE.match(parts[0]) else None


def _find_neighbor_value(
    entries: list[dict[str, Any]],
    idx: int,
    *,
    same_row_dy: float = 40.0,
) -> str | None:
    """Vrijednost desno ili malo ispod label retka."""
    base = entries[idx]
    bx, by = base["x"], base["y"]
    best: tuple[float, str] | None = None
    for j, other in enumerate(entries):
        if j == idx:
            continue
        ox, oy = other["x"], other["y"]
        if ox <= bx + 5:
            continue
        if abs(oy - by) > same_row_dy:
            continue
        dist = (ox - bx) + abs(oy - by) * 0.5
        txt = other["text"]
        if not txt:
            continue
        if best is None or dist < best[0]:
            best = (dist, txt)
    return best[1] if best else None


def extract_viz_fields_from_ocr(ocr_items: list[dict[str, Any]]) -> dict[str, str]:
    """
    Iz Paddle OCR stavki prednje strane hr. osobne izvuci VIZ polja.
    Vraća normalizirani dict (prazan ako ništa pouzdano).
    """
    entries: list[dict[str, Any]] = []
    for it in ocr_items or []:
        txt = _display_line(str(it.get("text") or ""))
        if len(txt) < 2:
            continue
        pos = _centroid_xy(it.get("box"))
        if pos is None:
            entries.append({"text": txt, "x": 0.0, "y": float(len(entries))})
        else:
            entries.append({"text": txt, "x": pos[0], "y": pos[1]})

    entries.sort(key=lambda e: (e["y"], e["x"]))
    out: dict[str, str] = {}

    for i, ent in enumerate(entries):
        t = ent["text"]
        neighbor = _find_neighbor_value(entries, i)

        def pick(label_pat: re.Pattern[str], key: str, *, from_neighbor: bool = True) -> None:
            if out.get(key):
                return
            val = _value_after_label(t, label_pat)
            if not val and from_neighbor and neighbor:
                if label_pat.search(t):
                    val = _value_after_label(neighbor, label_pat) or neighbor.strip().upper()
            if val:
                out[key] = val

        pick(_LABEL_SURNAME, "surname")
        pick(_LABEL_GIVEN, "given_names")
        pick(_LABEL_DOC_NO, "document_number")
        pick(_LABEL_SEX, "sex", from_neighbor=False)

        if _LABEL_DOB.search(t):
            dm = _DATE_VIZ.search(t) or (_DATE_VIZ.search(neighbor) if neighbor else None)
            if dm:
                out["birth_yymmdd"] = _date_to_yymmdd(dm.group(1), dm.group(2), dm.group(3))
        if _LABEL_EXPIRY.search(t):
            dm = _DATE_VIZ.search(t) or (_DATE_VIZ.search(neighbor) if neighbor else None)
            if dm:
                out["expiry_yymmdd"] = _date_to_yymmdd(dm.group(1), dm.group(2), dm.group(3))

    blob = " ".join(e["text"] for e in entries)
    if "document_number" not in out:
        dm = _DOC_NUMBER.search(blob.replace(" ", ""))
        if dm:
            out["document_number"] = dm.group(1)
    if "nationality" not in out and re.search(r"\bHRV\b", blob, re.IGNORECASE):
        out["nationality"] = "HRV"
    if "sex" not in out:
        sm = re.search(r"\b([MF])\s*/\s*[MF]\b", blob, re.IGNORECASE)
        if sm:
            out["sex"] = sm.group(1).upper()

    return normalize_viz_hints(out)


def viz_fields_sufficient(viz: dict[str, str]) -> bool:
    if viz.get("document_number"):
        return True
    return bool(viz.get("surname") and viz.get("given_names"))


def build_expected_td1_lines(viz: dict[str, str]) -> tuple[str, str, str] | None:
    """Sastavi valjane TD1 linije (s checksumom) iz VIZ sidra."""
    h = normalize_viz_hints(viz)
    doc = (h.get("document_number") or "").replace("<", "").strip()
    birth = (h.get("birth_yymmdd") or "").strip()
    expiry = (h.get("expiry_yymmdd") or "").strip()
    sex = (h.get("sex") or "M")[:1].upper()
    nat = (h.get("nationality") or "HRV")[:3].upper()
    surname = re.sub(r"[^A-Z<]", "", (h.get("surname") or "").upper())
    given = re.sub(r"[^A-Z<]", "", (h.get("given_names") or "").upper())
    if len(doc) < 6 or len(birth) != 6 or len(expiry) != 6 or not surname or not given:
        return None
    if sex not in ("M", "F"):
        sex = "M"
    try:
        code = str(
            TD1CodeGenerator(
                "I",
                "HRV",
                doc,
                birth,
                sex,
                expiry,
                nat,
                surname,
                given,
            )
        )
        lines = [ln.strip() for ln in code.strip().splitlines() if ln.strip()]
        if len(lines) == 3 and all(len(ln) == 30 for ln in lines):
            return lines[0], lines[1], lines[2]
    except (TypeError, ValueError):
        return None
    return None


def cross_check_mrz_vs_viz(
    suggested: dict[str, Any],
    viz: dict[str, str],
) -> list[str]:
    """Upozorenja ako MRZ polja ne odgovaraju VIZ sidrima s prednje strane."""
    h = normalize_viz_hints(viz)
    if not h:
        return []
    warnings: list[str] = []

    def norm_name(s: str) -> str:
        return re.sub(r"[^A-Z]", "", (s or "").upper())

    if h.get("document_number"):
        mrz_doc = (suggested.get("document_number") or "").replace("<", "").strip()
        if mrz_doc and mrz_doc != h["document_number"]:
            warnings.append(
                f"Broj dokumenta na stražnjoj ({mrz_doc}) ne odgovara prednjoj ({h['document_number']})."
            )
    if h.get("surname"):
        if norm_name(suggested.get("last_name", "")) != norm_name(h["surname"]):
            warnings.append("Prezime s MRZ-a ne odgovara prednjoj strani.")
    if h.get("given_names"):
        if norm_name(suggested.get("first_name", "")) != norm_name(h["given_names"]):
            warnings.append("Ime s MRZ-a ne odgovara prednjoj strani.")
    if h.get("birth_yymmdd"):
        dob = (suggested.get("date_of_birth") or "")[:10]
        if dob and len(dob) >= 10:
            yy, mm, dd = dob[2:4], dob[5:7], dob[8:10]
            iso_yymmdd = f"{yy}{mm}{dd}"
            if iso_yymmdd != h["birth_yymmdd"]:
                warnings.append("Datum rođenja s MRZ-a ne odgovara prednjoj strani.")
    if h.get("expiry_yymmdd"):
        exp = (suggested.get("date_of_expiry") or "")[:10]
        if exp and len(exp) >= 10:
            yy, mm, dd = exp[2:4], exp[5:7], exp[8:10]
            if f"{yy}{mm}{dd}" != h["expiry_yymmdd"]:
                warnings.append("Datum isteka s MRZ-a ne odgovara prednjoj strani.")
    if h.get("sex") and suggested.get("sex"):
        if suggested["sex"][0].upper() != h["sex"][0].upper():
            warnings.append("Spol s MRZ-a ne odgovara prednjoj strani.")
    return warnings
