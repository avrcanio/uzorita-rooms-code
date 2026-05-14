from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Any, Callable

from mrz.base.errors import FieldError, LengthError
from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td2 import TD2CodeChecker
from mrz.checker.td3 import TD3CodeChecker


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
    "2": ("Z"),
    "Z": ("2"),
    "3": ("8", "B", "9", "O"),
    "5": ("S"),
    "S": ("5"),
    "6": ("G"),
    "G": ("6"),
    "8": ("B", "3"),
    "B": ("8", "3"),
    "<": ("K",),
    "K": ("<",),
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


def _candidate_strings(items: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for it in _sort_items_by_reading_order(items):
        t = _normalize_mrz_line(str(it.get("text") or ""))
        if len(t) >= 20:
            out.append(t)
    return out


def _pad(line: str, length: int) -> str:
    line = line[:length]
    return line.ljust(length, "<")


def _substitution_variants(mrz_code: str, max_attempts: int) -> list[str]:
    positions = [i for i, ch in enumerate(mrz_code) if ch != "\n"]
    variants: list[str] = []
    attempts = 0
    for i in positions:
        ch = mrz_code[i]
        alts = MRZ_SUBSTITUTIONS.get(ch, ())
        for alt in alts:
            if alt == ch:
                continue
            variants.append(mrz_code[:i] + alt + mrz_code[i + 1 :])
            attempts += 1
            if attempts >= max_attempts:
                return variants
    return variants


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
    for variant in _substitution_variants(mrz_code, max_attempts=max_attempts):
        chk = _try_checker(variant, factory)
        if chk is None or not bool(chk):
            continue
        key = (_ocr_distance(variant), -scorer(variant), len(variant), variant)
        if best is None or key < best[0]:
            best = (key, variant, chk)
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
    return {
        "format": fmt,
        "document_type": f.document_type,
        "document_number": f.document_number,
        "birth_date": f.birth_date,
        "expiry_date": f.expiry_date,
        "sex": f.sex,
        "nationality": f.nationality,
        "country": f.country,
        "surname": (f.surname or "").replace("<", " ").strip(),
        "given_names": (f.name or "").replace("<", " ").strip(),
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


def _scan_td1_triples(lines: list[str], max_brute: int) -> MrzAttempt | None:
    for a, b, c in zip(lines, lines[1:], lines[2:]):
        p1, p2, p3 = _pad(a, 30), _pad(b, 30), _pad(c, 30)
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


def run_mrz_pipeline(ocr_items: list[dict[str, Any]], *, max_brute_attempts: int = 4000) -> dict[str, Any]:
    """
    Build MRZ result object from flattened OCR items (text/confidence/box).
    """
    lines = _candidate_strings(ocr_items)
    attempt: MrzAttempt | None = None
    # TD3 (passport) first, then TD2, then TD1 (ID-1) — common reception order.
    attempt = _scan_td3_pairs(lines, max_brute_attempts)
    if attempt is None:
        attempt = _scan_td2_pairs(lines, max_brute_attempts)
    if attempt is None:
        attempt = _scan_td1_triples(lines, max_brute_attempts)

    if attempt is None or attempt.checker is None:
        return {
            "lines": lines[:6],
            "format": None,
            "checksum_valid": False,
            "parsed": None,
            "corrected": False,
            "correction": None,
            "suggested_fields": {},
        }

    chk = attempt.checker
    valid = bool(chk)
    parsed = _parsed_public_dict(chk, attempt.format) if valid else None
    suggested: dict[str, Any] = {}
    if valid:
        suggested = _suggested_from_checker(chk)  # type: ignore[arg-type]

    correction = None
    if attempt.corrected and valid:
        correction = {"note": "Jedna ili vise zamjena znakova radi ispravnog MRZ checksuma."}

    return {
        "lines": attempt.lines,
        "format": attempt.format,
        "checksum_valid": valid,
        "parsed": parsed,
        "corrected": attempt.corrected,
        "correction": correction,
        "suggested_fields": suggested,
    }
