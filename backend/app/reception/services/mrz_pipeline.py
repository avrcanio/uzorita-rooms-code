from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Any, Callable

from django.conf import settings
from mrz.base.errors import FieldError, LengthError
from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td2 import TD2CodeChecker
from mrz.checker.td3 import TD3CodeChecker

from reception.services.td1_mrz_extract import (
    apply_td1_position_ocr_hints,
    extract_td1_mrz_from_ocr,
    soften_td1_line3_garbage,
    td1_lines_are_valid_shape,
)

"""
OCR stavke → MRZ (TD1 / TD2 / TD3).

TD1 (npr. poleđina hr. osobne): MRZ je točno 3 retka × 30 znakova; znak «<» je dopušten
i broji se u duljinu svakog retka (ICAO Doc 9303).
"""

logger = logging.getLogger(__name__)


def _trace() -> bool:
    return bool(getattr(settings, "SCAN_OCR_TRACE_LOG", False))


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

# Single-character OCR confusions within ICAO MRZ charset (bounded search).
MRZ_SUBSTITUTIONS: dict[str, tuple[str, ...]] = {
    "0": ("O", "Q", "D"),
    "O": ("0", "Q", "D", "3", "8"),
    "1": ("I", "L", "7"),
    "I": ("1", "L"),
    "L": ("1", "I"),
    "2": ("Z",),
    "Z": ("<", "2"),
    "3": ("8", "B", "9", "O"),
    "5": ("S"),
    "S": ("5"),
    "6": ("G"),
    "G": ("6"),
    "8": ("B", "3"),
    "B": ("8", "3"),
    "C": ("<",),
    "<": ("K",),
    "K": ("<",),
    "E": ("<",),
    "P": ("R",),
    "R": ("P",),
    "V": ("Y",),
    "Y": ("V",),
    "N": ("M",),
    "M": ("N",),
}

# ISO 3166-1 alpha-3 → alpha-2 for common travel documents (extend as needed).
_NATIONALITY_A3_TO_A2: dict[str, str] = {
    "HRV": "HR",
    "SVN": "SI",
    "BIH": "BA",
    "SRB": "RS",
    "MNE": "ME",
    "MKD": "MK",
    "DEU": "DE",
    "AUT": "AT",
    "ITA": "IT",
    "FRA": "FR",
    "ESP": "ES",
    "PRT": "PT",
    "NLD": "NL",
    "BEL": "BE",
    "POL": "PL",
    "CZE": "CZ",
    "SVK": "SK",
    "HUN": "HU",
    "ROU": "RO",
    "BGR": "BG",
    "GRC": "GR",
    "TUR": "TR",
    "GBR": "GB",
    "IRL": "IE",
    "USA": "US",
    "CAN": "CA",
    "UKR": "UA",
    "RUS": "RU",
    "SWE": "SE",
    "NOR": "NO",
    "DNK": "DK",
    "FIN": "FI",
    "CHE": "CH",
    "LIE": "LI",
    "LUX": "LU",
    "EST": "EE",
    "LVA": "LV",
    "LTU": "LT",
    "ALB": "AL",
    "ISR": "IL",
    "ARE": "AE",
    "CHN": "CN",
    "JPN": "JP",
    "KOR": "KR",
    "AUS": "AU",
    "NZL": "NZ",
    "BRA": "BR",
    "ARG": "AR",
}


def _normalize_mrz_line(text: str) -> str:
    raw = text.upper().replace(" ", "")
    raw = raw.replace("—", "-")
    return re.sub(r"[^A-Z0-9<]", "", raw)


_MRZ_LINE_WIDTHS: tuple[int, ...] = (30, 36, 44)
_ALLOWED_MRZ_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<")

# TD1 MRZ (ICAO Doc 9303) — kao na poleđini hrvatske osobne iskaznice (ID-1):
#   • Točno 3 retka × 30 znakova (ukupno 90 znakova u MRZ bloku).
#   • U svaki red ulaze samo ICAO dopušteni znakovi; znak «<» (chevron) je punjenje i
#     broji se u tih 30 mjesta — nije „izvan“ duljine retka.
# Primjeri (svaki red = točno 30 znakova):
#   I0HRV11938408791528564544<<<<
#   7604234M3005121HRV<<<<<<<<<<9
#   VRCAN<<ANTE<<<<<<<<<<<<<<<<<<<
#   I<HRV117052128563281973348<<<
#   7206270M2801201HRV<<<<<<<<<<4
#   SUPE<<TONI<<<<<<<<<<<<<<<<<<<<
TD1_LINE_CHAR_COUNT = 30


def _chars_read_as_chevron_instead() -> frozenset[str]:
    """Znakovi za koje MRZ_SUBSTITUTIONS dopušta '<' kao zamjenu (OCR čita filler kao taj znak)."""
    return frozenset(ch for ch, alts in MRZ_SUBSTITUTIONS.items() if "<" in alts)


def smart_padding_fix(line: str) -> str:
    """
    Poravna duljinu linije na 30 / 36 / 44 (najbliži cilj) te na rubovima zamijeni sumnjive
    znakove (iz MRZ_SUBSTITUTIONS gdje je '<' alternativa) u '<' kad je linija već na ciljnoj duljini.
    Dugačke nizove (>44) ne dira (npr. spoj više MRZ redaka).
    """
    if not line or len(line) > max(_MRZ_LINE_WIDTHS):
        return line
    if not re.match(r"^[A-Z0-9<]+$", line):
        return line
    target = min(_MRZ_LINE_WIDTHS, key=lambda w: abs(len(line) - w))
    s = line
    if len(s) < target:
        s = s.ljust(target, "<")
    elif len(s) > target:
        s = s[:target]
    sus = _chars_read_as_chevron_instead()
    while s and s[0] in sus:
        s = "<" + s[1:]
    while s and s[-1] in sus:
        s = s[:-1] + "<"
    return s


def _post_normalize_candidate_line(line: str) -> str:
    return smart_padding_fix(line)


_TD1_LINE1_ANCHOR = re.compile(r"I[0<][A-Z]{3}\d")


def _td1_snippets_from_long_token(normalized: str) -> list[str]:
    """
    Kad OCR u jednoj regiji spoji numeričke polja (OIB/MBO) s MRZ-om, cijeli niz je >44 znaka
    pa ga smart_padding ne dira. Izdvoji TD1 kandidate: početak linije 1 (I + 0/< + ISO3 + znamenka),
    opcionalno cijeli blok 3 × TD1_LINE_CHAR_COUNT znakova ako slijedi odmah iza.
    """
    if len(normalized) < TD1_LINE_CHAR_COUNT:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for m in _TD1_LINE1_ANCHOR.finditer(normalized):
        start = m.start()
        triple_w = 3 * TD1_LINE_CHAR_COUNT
        if start + triple_w <= len(normalized):
            block = normalized[start : start + triple_w]
            if re.fullmatch(r"[A-Z0-9<]+", block) is not None and block.count("<") >= 6:
                for i in (0, TD1_LINE_CHAR_COUNT, 2 * TD1_LINE_CHAR_COUNT):
                    seg = block[i : i + TD1_LINE_CHAR_COUNT]
                    if len(seg) == TD1_LINE_CHAR_COUNT and seg not in seen:
                        seen.add(seg)
                        out.append(seg)
                continue
        if start + TD1_LINE_CHAR_COUNT <= len(normalized):
            seg = normalized[start : start + TD1_LINE_CHAR_COUNT]
            if (
                len(seg) == TD1_LINE_CHAR_COUNT
                and re.fullmatch(r"[A-Z0-9<]+", seg) is not None
                and seg.count("<") >= 2
            ):
                if seg not in seen:
                    seen.add(seg)
                    out.append(seg)
    return out


def _expand_td1_concatenated_candidates(lines: list[str]) -> list[str]:
    """
    Ako je OCR spojio 2–3 TD1 linije (višekratnik od TD1_LINE_CHAR_COUNT po retku) u jedan
    string bez prijeloma, dodaj pojedinačne retke duljine TD1_LINE_CHAR_COUNT.
    """
    seen = list(dict.fromkeys(lines))
    for t in lines:
        n = len(t)
        if n < 2 * TD1_LINE_CHAR_COUNT or n % TD1_LINE_CHAR_COUNT != 0:
            continue
        if t.count("<") < 6:
            continue
        for i in range(0, n, TD1_LINE_CHAR_COUNT):
            chunk = t[i : i + TD1_LINE_CHAR_COUNT]
            if len(chunk) != TD1_LINE_CHAR_COUNT:
                continue
            if chunk not in seen:
                seen.append(chunk)
    return seen


def _yymmdd_to_iso(yymmdd: str, *, expiry: bool) -> str | None:
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    today_yy = date.today().year % 100
    if expiry:
        pivot = (today_yy + 20) % 100
        century = 2000 if yy <= pivot else 1900
    else:
        pivot = today_yy
        century = 2000 if yy <= pivot else 1900
    year = century + yy
    try:
        return date(year, mm, dd).isoformat()
    except ValueError:
        return None


def _nationality_to_iso2(alpha3: str) -> str | None:
    if len(alpha3) != 3:
        return None
    return _NATIONALITY_A3_TO_A2.get(alpha3.upper())


def _sort_items_by_reading_order(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda it: (_centroid_y(it.get("box")) is None, _centroid_y(it.get("box")) or 0.0))


def _td1_bottom_block_tail_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Zadnje tri OCR stavke u vertikalnom poretku (najveći Y) ako prva izgleda kao TD1 linija 1
    (npr. I0HRV… / I<HRV…). Na poleđini hr. osobne MRZ je na dnu; gornji tekstovi ne smiju ići
    u isti „redak“ kao MRZ prije pravog tripleta.
    """
    if len(items) < 3:
        return []
    ordered = _sort_items_by_reading_order(items)
    tail = ordered[-3:]
    n0 = _normalize_mrz_line(str(tail[0].get("text") or ""))
    if _TD1_LINE1_ANCHOR.search(n0) is None:
        return []
    return tail


def _append_item_candidate_strings(it: dict[str, Any], out: list[str]) -> None:
    t = _normalize_mrz_line(str(it.get("text") or ""))
    for emb in _td1_snippets_from_long_token(t):
        e2 = _post_normalize_candidate_line(emb)
        if len(e2) >= 20:
            out.append(e2)
    t = _post_normalize_candidate_line(t)
    if len(t) >= 20:
        out.append(t)


def _candidate_strings(items: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    priority = _td1_bottom_block_tail_items(items)
    prio_ids = {id(it) for it in priority}
    for it in priority:
        _append_item_candidate_strings(it, out)
    for it in _sort_items_by_reading_order(items):
        if id(it) in prio_ids:
            continue
        _append_item_candidate_strings(it, out)
    return _expand_td1_concatenated_candidates(out)


def _pad(line: str, length: int) -> str:
    line = line[:length]
    return line.ljust(length, "<")


def _td1_row_icao_width(fragment: str) -> str:
    """
    Jedan MRZ red formata TD1 (osobna iskaznica): točno TD1_LINE_CHAR_COUNT znakova,
    uključivo «<» — chevron se broji u duljinu retka. Skup: A–Z, 0–9, «<» (vidi _ALLOWED_MRZ_CHARS).
    Dulje od 30: skraćivanje; kraće: punjenje «<» s desna do točno 30.
    """
    t = "".join(c for c in fragment.upper() if c in _ALLOWED_MRZ_CHARS)
    if len(t) > TD1_LINE_CHAR_COUNT:
        t = t[:TD1_LINE_CHAR_COUNT]
    return t.ljust(TD1_LINE_CHAR_COUNT, "<")


def _canonicalize_td1_line1_doc_type_prefix(row: str) -> str:
    """
    OCR (npr. Paddle ``lang=latin``) često pročita ICAO «<» u drugom znaku kao ``0`` ili ``O``.
    Za hrvatsku osobnu: očekuje se ``I<`` + ``HRV``.
    """
    t = _td1_row_icao_width(row)
    if len(t) >= 5 and t[0] == "I" and t[1] in "0OQ" and t[2:5] == "HRV":
        return "I<" + t[2:]
    return t


def _canonicalize_td1_line2_optional_fillers(row: str) -> str:
    """
    Opcijski blok (pozicije 18–28) mora biti «<»; znamenka na poziciji 29 je kompozitni CD.
    OCR ponekad ubaci Z/K/X ili pomakne «<»; uzmi zadnju znamenku iz repa kao kandidat za CD.
    """
    t = _td1_row_icao_width(row)
    if len(t) != 30:
        return t
    prefix = t[:18]
    tail = t[18:30]
    tail_clean = "".join("<" if c in "ZXK" else c for c in tail)
    composite = "<"
    for ch in reversed(tail_clean):
        if ch.isdigit():
            composite = ch
            break
    if composite == "<":
        for i in range(18, 29):
            if i < len(t) and t[i] in "ZXK":
                ch = list(t)
                ch[i] = "<"
                t = "".join(ch)
        return t
    return prefix + "<" * 11 + composite


def _canonicalize_td1_line3_name_tail_fillers(row: str) -> str:
    """
    Nakon ``prezime<<ime`` ostatak retka mora biti «<»; OCR šum (K, X, …) u ispuni.
    """
    t = _td1_row_icao_width(row)
    m = re.match(r"^([^<]+)<<([^<]+)(.*)$", t)
    if not m:
        return t
    sur, giv, tail = m.group(1), m.group(2), m.group(3)
    return _td1_row_icao_width(sur + "<<" + giv + "<" * len(tail))


def _canonicalize_td1_triple_common_ocr(lines: tuple[str, str, str] | list[str]) -> tuple[str, str, str]:
    a, b, c = lines[0], lines[1], lines[2]
    return (
        _canonicalize_td1_line1_doc_type_prefix(a),
        _canonicalize_td1_line2_optional_fillers(b),
        _canonicalize_td1_line3_name_tail_fillers(c),
    )


def _fielderror_priority_indices(mrz_code: str, factory: Callable[[str], Any]) -> list[int]:
    """Indeksi znakova za koje checker prijavi FieldError (ili nisu dopušteni u MRZ skupu)."""
    try:
        factory(mrz_code)
    except FieldError as exc:
        out: list[int] = []
        c = getattr(exc, "cause", None)
        if isinstance(c, str) and len(c) == 1:
            out.extend(i for i, ch in enumerate(mrz_code) if ch == c and ch != "\n")
        for i, ch in enumerate(mrz_code):
            if ch == "\n":
                continue
            if ch not in _ALLOWED_MRZ_CHARS:
                out.append(i)
        return list(dict.fromkeys(out))
    except (LengthError, ValueError):
        pass
    return []


def _substitution_variants_at_positions(
    mrz_code: str,
    position_order: list[int],
) -> list[str]:
    """Jedna zamjena po varijanti, isključivo MRZ_SUBSTITUTIONS."""
    variants: list[str] = []
    for i in position_order:
        if i >= len(mrz_code) or mrz_code[i] == "\n":
            continue
        ch = mrz_code[i]
        for alt in MRZ_SUBSTITUTIONS.get(ch, ()):
            if alt == ch:
                continue
            variants.append(mrz_code[:i] + alt + mrz_code[i + 1 :])
    return variants


def _ordered_substitution_positions(mrz_code: str, factory: Callable[[str], Any]) -> list[int]:
    priority = set(_fielderror_priority_indices(mrz_code, factory))
    rest = [i for i in range(len(mrz_code)) if mrz_code[i] != "\n" and i not in priority]
    return sorted(priority) + rest


@dataclass
class MrzAttempt:
    format: str
    mrz_code: str
    lines: list[str]
    corrected: bool
    checker: TD1CodeChecker | TD2CodeChecker | TD3CodeChecker | None


def _try_checker(mrz_code: str, factory: Callable[[str], Any]) -> Any | None:
    try:
        return factory(mrz_code)
    except (LengthError, FieldError, ValueError):
        return None


def _brute_single_char(
    mrz_code: str,
    factory: Callable[[str], Any],
    max_attempts: int,
    *,
    ocr_hint_lines: tuple[str, ...] | None = None,
) -> tuple[str, Any] | None:
    chk = _try_checker(mrz_code, factory)
    if chk is not None and bool(chk):
        return mrz_code, chk

    def _td3_doc_digit_score(candidate: str) -> int:
        lines = candidate.splitlines()
        if len(lines) < 2:
            return -1
        return sum(1 for c in lines[1][:9] if c.isdigit())

    def _td1_doc_digit_score(candidate: str) -> int:
        lines = candidate.splitlines()
        if len(lines) < 2:
            return -1
        return sum(1 for c in lines[1][:9] if c.isdigit())

    def _td2_doc_digit_score(candidate: str) -> int:
        lines = candidate.splitlines()
        if len(lines) < 2:
            return -1
        return sum(1 for c in lines[1][:9] if c.isdigit())

    scorer = _td3_doc_digit_score
    if factory is TD1CodeChecker:
        scorer = _td1_doc_digit_score
    elif factory is TD2CodeChecker:
        scorer = _td2_doc_digit_score

    def _ocr_distance(candidate: str) -> int:
        if not ocr_hint_lines:
            return 0
        cand_lines = candidate.splitlines()
        dist = 0
        for i, hint in enumerate(ocr_hint_lines):
            if i >= len(cand_lines):
                dist += len(hint)
                continue
            row_c, row_h = cand_lines[i], hint
            for j in range(max(len(row_c), len(row_h))):
                c_ch = row_c[j] if j < len(row_c) else ""
                h_ch = row_h[j] if j < len(row_h) else ""
                dist += 0 if c_ch == h_ch else 1
        return dist

    best: tuple[tuple[int, int, int, str], str, Any] | None = None

    def _consider(candidate: str, chk_obj: Any) -> None:
        nonlocal best
        if chk_obj is None or not bool(chk_obj):
            return
        key = (_ocr_distance(candidate), -scorer(candidate), len(candidate), candidate)
        if best is None or key < best[0]:
            best = (key, candidate, chk_obj)

    order0 = _ordered_substitution_positions(mrz_code, factory)
    for nxt in _substitution_variants_at_positions(mrz_code, order0):
        _consider(nxt, _try_checker(nxt, factory))
    if best is not None:
        return best[1], best[2]

    seen: set[str] = {mrz_code}
    dq: deque[str] = deque()
    for nxt in _substitution_variants_at_positions(mrz_code, order0):
        if nxt not in seen:
            seen.add(nxt)
            dq.append(nxt)

    max_states = max(64, max_attempts)
    while dq and len(seen) < max_states:
        cur = dq.popleft()
        chk_cur = _try_checker(cur, factory)
        if chk_cur is not None and bool(chk_cur):
            _consider(cur, chk_cur)
            continue

        pos_order = _ordered_substitution_positions(cur, factory)
        for nxt in _substitution_variants_at_positions(cur, pos_order):
            if nxt in seen or len(seen) >= max_states:
                continue
            seen.add(nxt)
            dq.append(nxt)

    if best is None:
        return None
    return best[1], best[2]


def _suggested_from_checker(
    chk: TD1CodeChecker | TD2CodeChecker | TD3CodeChecker,
) -> dict[str, Any]:
    f = chk.fields()
    surname = (f.surname or "").replace("<", " ").strip()
    given = (f.name or "").replace("<", " ").strip()
    nat = _nationality_to_iso2(f.nationality)
    dob = _yymmdd_to_iso(f.birth_date, expiry=False)
    doe = _yymmdd_to_iso(f.expiry_date, expiry=True)
    out: dict[str, Any] = {
        "first_name": given or "",
        "last_name": surname or "",
        "document_number": (f.document_number or "").replace("<", "").strip(),
        "sex": (f.sex or "").replace("<", "").strip(),
        "date_of_birth": dob or "",
        "date_of_expiry": doe or "",
        "mrz_raw_text": chk.mrz_code,
        "document_country_iso3": (f.country or "").strip(),
    }
    if nat:
        out["nationality"] = nat
    return {k: v for k, v in out.items() if v}


def _parsed_public_dict(
    chk: TD1CodeChecker | TD2CodeChecker | TD3CodeChecker, fmt: str
) -> dict[str, Any]:
    f = chk.fields()
    bd_raw = (f.birth_date or "").strip()
    ed_raw = (f.expiry_date or "").strip()
    birth_iso = _yymmdd_to_iso(bd_raw, expiry=False) if len(bd_raw) == 6 and bd_raw.isdigit() else None
    exp_iso = _yymmdd_to_iso(ed_raw, expiry=True) if len(ed_raw) == 6 and ed_raw.isdigit() else None
    return {
        "format": fmt,
        "document_type": f.document_type,
        "document_number": f.document_number,
        "birth_date": birth_iso or bd_raw,
        "expiry_date": exp_iso or ed_raw,
        "sex": f.sex,
        "nationality": f.nationality,
        "country": f.country,
        "surname": (f.surname or "").replace("<", " ").strip(),
        "given_names": (f.name or "").replace("<", " ").strip(),
    }


def _parsed_td1_extended(
    chk: TD1CodeChecker | TD2CodeChecker | TD3CodeChecker,
    *,
    line1: str,
) -> dict[str, Any]:
    """Strukturirani TD1 izlaz (uz polja iz checker-a)."""
    base = _parsed_public_dict(chk, "TD1")
    l1 = (line1 or "")[:30].ljust(30, "<")
    base["document_code"] = l1[0:2]
    base["issuing_state"] = l1[2:5]
    return base


def _partial_td1_from_three_lines(l1: str, l2: str, l3: str) -> dict[str, Any]:
    """Kad checksum ne prolazi: parsiranje samo iz poznatih pozicija (bez composite check)."""
    l1 = l1[:30].ljust(30, "<")
    l2 = l2[:30].ljust(30, "<")
    l3 = l3[:30].ljust(30, "<")
    dob = _yymmdd_to_iso(l2[0:6], expiry=False) if len(l2) >= 6 else None
    doe = _yymmdd_to_iso(l2[8:14], expiry=True) if len(l2) >= 14 else None
    sex = l2[7] if len(l2) > 7 else ""
    nat = l2[15:18] if len(l2) >= 18 else ""
    doc = l1[5:14].replace("<", "") if len(l1) >= 14 else ""
    sur, given = "", ""
    if "<<" in l3:
        parts = l3.split("<<", 1)
        sur = (parts[0] or "").replace("<", " ").strip()
        given = (parts[1] or "").replace("<", " ").strip() if len(parts) > 1 else ""
    else:
        sur = l3.split("<")[0].strip() if l3 else ""
    return {
        "format": "TD1",
        "document_code": l1[0:2],
        "issuing_state": l1[2:5],
        "document_number": doc,
        "birth_date": dob or "",
        "sex": sex if sex in ("M", "F", "<") else "",
        "expiry_date": doe or "",
        "nationality": nat,
        "surname": sur,
        "given_names": given,
    }


def _scan_td3_pairs(lines: list[str], max_brute: int) -> MrzAttempt | None:
    for a, b in zip(lines, lines[1:]):
        p1, p2 = _pad(a, 44), _pad(b, 44)
        code = p1 + "\n" + p2
        hit = _brute_single_char(
            code, TD3CodeChecker, max_attempts=max_brute, ocr_hint_lines=(p1, p2)
        )
        if hit:
            fixed, chk = hit
            return MrzAttempt(
                format="TD3",
                mrz_code=fixed,
                lines=fixed.splitlines(),
                corrected=fixed != code,
                checker=chk,
            )
    if len(lines) <= 8:
        for a, b in combinations(lines, 2):
            p1, p2 = _pad(a, 44), _pad(b, 44)
            code = p1 + "\n" + p2
            hit = _brute_single_char(
                code, TD3CodeChecker, max_attempts=max_brute, ocr_hint_lines=(p1, p2)
            )
            if hit:
                fixed, chk = hit
                return MrzAttempt(
                    format="TD3",
                    mrz_code=fixed,
                    lines=fixed.splitlines(),
                    corrected=fixed != code,
                    checker=chk,
                )
    return None


def _scan_td2_pairs(lines: list[str], max_brute: int) -> MrzAttempt | None:
    for a, b in zip(lines, lines[1:]):
        p1, p2 = _pad(a, 36), _pad(b, 36)
        code = p1 + "\n" + p2
        hit = _brute_single_char(
            code, TD2CodeChecker, max_attempts=max_brute, ocr_hint_lines=(p1, p2)
        )
        if hit:
            fixed, chk = hit
            return MrzAttempt(
                format="TD2",
                mrz_code=fixed,
                lines=fixed.splitlines(),
                corrected=fixed != code,
                checker=chk,
            )
    if len(lines) <= 8:
        for a, b in combinations(lines, 2):
            p1, p2 = _pad(a, 36), _pad(b, 36)
            code = p1 + "\n" + p2
            hit = _brute_single_char(
                code, TD2CodeChecker, max_attempts=max_brute, ocr_hint_lines=(p1, p2)
            )
            if hit:
                fixed, chk = hit
                return MrzAttempt(
                    format="TD2",
                    mrz_code=fixed,
                    lines=fixed.splitlines(),
                    corrected=fixed != code,
                    checker=chk,
                )
    return None


def _try_td1_from_extracted_three(
    three: list[str],
    max_brute: int,
    *,
    viz_hint_lines: tuple[str, str, str] | None = None,
) -> tuple[MrzAttempt | None, list[str], list[str]]:
    """Pokušaj TD1 samo na tri izdvojena retka; vraća (attempt|None, prije hintova, zadnji triple prije checker-a)."""
    if len(three) != 3 or not td1_lines_are_valid_shape(three):
        return None, list(three), list(three)
    raw = [_td1_row_icao_width(x) for x in three]
    raw = list(_canonicalize_td1_triple_common_ocr((raw[0], raw[1], raw[2])))
    hinted = list(apply_td1_position_ocr_hints(*raw))
    hinted2 = [hinted[0], hinted[1], soften_td1_line3_garbage(hinted[2])]
    seen: set[str] = set()
    last_triple = hinted2
    for triple in (tuple(raw), tuple(hinted), tuple(hinted2)):
        p1, p2, p3 = (_td1_row_icao_width(t) for t in triple)
        code = p1 + "\n" + p2 + "\n" + p3
        if code in seen:
            continue
        seen.add(code)
        last_triple = list(triple)
        brute_hints: tuple[str, ...] = viz_hint_lines if viz_hint_lines else (p1, p2, p3)
        hit = _brute_single_char(
            code, TD1CodeChecker, max_attempts=max_brute, ocr_hint_lines=brute_hints
        )
        if hit:
            fixed, chk = hit
            return (
                MrzAttempt(
                    format="TD1",
                    mrz_code=fixed,
                    lines=fixed.splitlines(),
                    corrected=fixed != code,
                    checker=chk,
                ),
                raw,
                last_triple,
            )
    return None, raw, last_triple


def _scan_td1_triples(lines: list[str], max_brute: int) -> MrzAttempt | None:
    for a, b, c in zip(lines, lines[1:], lines[2:]):
        p1, p2, p3 = _td1_row_icao_width(a), _td1_row_icao_width(b), _td1_row_icao_width(c)
        code = p1 + "\n" + p2 + "\n" + p3
        hit = _brute_single_char(
            code, TD1CodeChecker, max_attempts=max_brute, ocr_hint_lines=(p1, p2, p3)
        )
        if hit:
            fixed, chk = hit
            return MrzAttempt(
                format="TD1",
                mrz_code=fixed,
                lines=fixed.splitlines(),
                corrected=fixed != code,
                checker=chk,
            )
    return None


def run_mrz_pipeline(
    ocr_items: list[dict[str, Any]],
    *,
    max_brute_attempts: int = 4000,
    image_height: int | None = None,
    mrz_strip_y0: float | None = None,
    viz_hint_lines: tuple[str, str, str] | None = None,
) -> dict[str, Any]:
    """
    OCR stavke → MRZ. TD1: prvo izdvajanje tri MRZ retka (bez adresnih polja), zatim TD3/TD2 fallback.

    ``viz_hint_lines``: očekivane TD1 linije s prednje strane (VIZ) — koriste se kao sidra u brute-forceu.
    """
    if _trace():
        logger.info("mrz_pipeline: input_items=%d", len(ocr_items))
        for i, it in enumerate(ocr_items):
            y = _centroid_y(it.get("box"))
            txt = str(it.get("text") or "")
            logger.info(
                "mrz_pipeline: ocr_item[%d] y_centroid=%s conf=%s text=%r",
                i,
                f"{y:.1f}" if y is not None else "None",
                it.get("confidence"),
                txt,
            )

    ih = image_height
    if ih is None and ocr_items:
        ys2 = [y for y in (_centroid_y(it.get("box")) for it in ocr_items) if y is not None]
        if ys2:
            ih = int(max(ys2) + 120)

    ex_lines, ex_meta = extract_td1_mrz_from_ocr(
        ocr_items, image_height=ih, mrz_strip_y0=mrz_strip_y0
    )
    candidates_raw = ex_meta.get("candidates", [])

    td1_attempt: MrzAttempt | None = None
    if len(ex_lines) == 3:
        td1_attempt, _before_hint, _after_triple = _try_td1_from_extracted_three(
            ex_lines, max_brute_attempts, viz_hint_lines=viz_hint_lines
        )
    if td1_attempt is None and viz_hint_lines and len(viz_hint_lines) == 3:
        td1_attempt, _before_hint, _after_triple = _try_td1_from_extracted_three(
            list(viz_hint_lines),
            max_brute_attempts,
            viz_hint_lines=viz_hint_lines,
        )

    lines_fallback = _candidate_strings(ocr_items)
    attempt: MrzAttempt | None = td1_attempt

    if attempt is None:
        attempt = _scan_td3_pairs(lines_fallback, max_brute_attempts)
        if _trace():
            logger.info("mrz_pipeline: after TD3 scan hit=%s", attempt is not None)
    if attempt is None:
        attempt = _scan_td2_pairs(lines_fallback, max_brute_attempts)
        if _trace():
            logger.info("mrz_pipeline: after TD2 scan hit=%s", attempt is not None)
    if attempt is None:
        attempt = _scan_td1_triples(lines_fallback, max_brute_attempts)
        if _trace():
            logger.info("mrz_pipeline: after legacy TD1 triple scan hit=%s", attempt is not None)

    base_extra: dict[str, Any] = {
        "extracted_mrz_candidates": candidates_raw,
        "td1_extraction_meta": {
            "pool_source": ex_meta.get("pool_source"),
            "picked_count": ex_meta.get("picked_count"),
        },
        "final_td1_lines": ex_lines if len(ex_lines) == 3 else None,
    }

    if attempt is None or attempt.checker is None:
        if _trace():
            logger.info("mrz_pipeline: no valid MRZ checksum (TD1 extract / TD3 / TD2 / legacy TD1).")
        if len(ex_lines) == 3:
            parsed_partial = _partial_td1_from_three_lines(ex_lines[0], ex_lines[1], ex_lines[2])
            return {
                **base_extra,
                "lines": ex_lines,
                "format": "TD1",
                "checksum_valid": False,
                "parsed": parsed_partial,
                "corrected": False,
                "correction": None,
                "suggested_fields": {},
            }
        preview = ex_lines if ex_lines else lines_fallback[: min(8, len(lines_fallback))]
        return {
            **base_extra,
            "lines": preview,
            "format": None,
            "checksum_valid": False,
            "parsed": None,
            "corrected": False,
            "correction": None,
            "suggested_fields": {},
        }

    chk = attempt.checker
    valid = bool(chk)
    if attempt.format == "TD1" and valid and attempt.lines:
        parsed: dict[str, Any] | None = _parsed_td1_extended(chk, line1=attempt.lines[0])
    elif valid:
        parsed = _parsed_public_dict(chk, attempt.format)
    else:
        parsed = None

    suggested: dict[str, Any] = {}
    if valid:
        suggested = _suggested_from_checker(chk)  # type: ignore[arg-type]

    correction: dict[str, Any] | str | None = None
    if valid and attempt.corrected:
        if td1_attempt is not None and len(ex_lines) == 3:
            correction = {"before": list(ex_lines), "after": list(attempt.lines)}
        else:
            correction = {"note": "Jedna ili vise zamjena znakova radi ispravnog MRZ checksuma."}

    if _trace():
        logger.info(
            "mrz_pipeline: match format=%s checksum_valid=%s corrected=%s lines=%r",
            attempt.format,
            valid,
            attempt.corrected,
            attempt.lines,
        )

    return {
        **base_extra,
        "lines": attempt.lines,
        "format": attempt.format,
        "checksum_valid": valid,
        "parsed": parsed,
        "corrected": attempt.corrected,
        "correction": correction,
        "suggested_fields": suggested,
    }
