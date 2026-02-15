from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
import html as _html
import re
from typing import Any


@dataclass(frozen=True)
class BookingPayload:
    booking_number: str
    guest_full_name: str | None
    guest_email: str | None
    guest_nationality_iso2: str | None
    check_in_date: date | None
    check_out_date: date | None
    property_name: str | None
    room_name: str | None
    rooms: list[dict[str, Any]]
    total_amount: Decimal | None
    currency: str | None
    total_guests: int | None
    total_rooms: int | None
    kind: str  # "new" | "modify" | "cancel" | "message"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": "booking.com",
            "kind": self.kind,
            "booking_number": self.booking_number,
            "guest_full_name": self.guest_full_name,
            "guest_email": self.guest_email,
            "guest_nationality_iso2": self.guest_nationality_iso2,
            "check_in_date": self.check_in_date.isoformat() if self.check_in_date else None,
            "check_out_date": self.check_out_date.isoformat() if self.check_out_date else None,
            "property_name": self.property_name,
            "room_name": self.room_name,
            "rooms": self.rooms,
            "total_amount": str(self.total_amount) if self.total_amount is not None else None,
            "currency": self.currency,
            "total_guests": self.total_guests,
            "total_rooms": self.total_rooms,
        }


class BookingParseException(Exception):
    def __init__(self, code: str, message: str, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.context = context or {}


_RE_URL_LINE = re.compile(r"^<https?://.*?>\s*$")


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        # Body text often includes URL-only lines; drop them for more stable parsing.
        if _RE_URL_LINE.match(line):
            continue
        lines.append(line)
    return lines


def _find_value_after_label(lines: list[str], label: str) -> str | None:
    label_norm = label.strip().lower().rstrip(":")
    for i, line in enumerate(lines):
        normalized = line.strip().lower()
        if normalized.rstrip(":") == label_norm:
            # Value is typically on the next non-empty non-url line.
            if i + 1 < len(lines):
                return lines[i + 1].strip() or None
        # Inline "Label: value"
        if normalized.startswith(label_norm + ":"):
            return line.split(":", 1)[1].strip() or None
    return None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    m = re.search(r"\d+", value)
    return int(m.group(0)) if m else None


def _parse_booking_number(lines: list[str]) -> str | None:
    # Common variants across Booking templates and forwarded messages.
    for label in ("Booking number", "Confirmation number", "Reservation number"):
        v = _find_value_after_label(lines, label)
        if v and re.fullmatch(r"\d{6,}", v):
            return v
    for label in ("Booking.com ID", "Booking.com Id", "Booking.com id"):
        v = _find_value_after_label(lines, label)
        if v and re.fullmatch(r"\d{6,}", v):
            return v
    # Fallback: any "Booking number: 123" inline.
    for line in lines:
        m = re.search(r"(?i)\b(booking|confirmation)\s+number:\s*(\d{6,})\b", line)
        if m:
            return m.group(2)
        m = re.search(r"(?i)\bbooking\.com\s+id:\s*(\d{6,})\b", line)
        if m:
            return m.group(1)
    return None


def _parse_booking_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    # Examples: "Sat 14 Feb 2026"
    for fmt in ("%a %d %b %Y", "%A %d %b %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_date_range_from_text(lines: list[str]) -> tuple[date | None, date | None]:
    # Example: "14.02.2026 - 15.02.2026"
    for line in lines:
        m = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})\b", line)
        if not m:
            continue
        try:
            return (
                datetime.strptime(m.group(1), "%d.%m.%Y").date(),
                datetime.strptime(m.group(2), "%d.%m.%Y").date(),
            )
        except ValueError:
            continue
    return (None, None)


_RE_DATE_RANGE_DMY = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})\b")


def _parse_price_from_line(line: str) -> tuple[Decimal | None, str | None]:
    m = re.match(r"^\s*([0-9]{1,6}(?:[.,][0-9]{2}))\s*(?:\(|$)", line or "")
    if not m:
        return (None, None)
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        amount = Decimal(raw).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return (None, None)

    currency = None
    if re.search(r"\bEUR\b|€", line, re.I):
        currency = "EUR"
    if re.search(r"\bHRK\b|kn\b", line, re.I):
        currency = "HRK"
    return (amount, currency)


def _parse_room_blocks(lines: list[str]) -> list[dict[str, Any]]:
    """
    Rentlio group bookings may include multiple repeated blocks:
      18.09.2026 - 19.09.2026
      R3 deluxe triple, R3 - Deluxe Triple
      109,65 (...)
    Return them in email order.
    """
    rooms: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        m = _RE_DATE_RANGE_DMY.search(line)
        if not m:
            continue
        try:
            check_in = datetime.strptime(m.group(1), "%d.%m.%Y").date()
            check_out = datetime.strptime(m.group(2), "%d.%m.%Y").date()
        except ValueError:
            continue

        room_line = None
        room_line_idx = None
        for j in range(i + 1, min(len(lines), i + 4)):
            candidate = lines[j]
            if re.search(r"\bR\s*-?\s*\d+\b", candidate, re.I) and any(ch.isalpha() for ch in candidate):
                room_line = candidate
                room_line_idx = j
                break
        if not room_line:
            continue

        # Room line is either:
        # - "R3 deluxe triple, R3 - Deluxe Triple" (single room, repeated code)
        # - "R-4 DELUXE KING, R-6 DELUXE KING" (multi-room, different codes on one line)
        codes = re.findall(r"\bR\s*-?\s*(\d+)\b", room_line, re.I)
        unique_codes = {c.lstrip("0") or "0" for c in codes}
        parts = [p.strip() for p in room_line.split(",") if p.strip()]
        room_names: list[str] = []
        if len(unique_codes) >= 2:
            for part in parts:
                if re.search(r"\bR\s*-?\s*\d+\b", part, re.I) and any(ch.isalpha() for ch in part):
                    room_names.append(part)
        else:
            # Default behavior: take the first segment (usually "R3 deluxe triple").
            room_names = [parts[0]] if parts else []

        room_names = [rn for rn in room_names if 3 <= len(rn) <= 120]
        if not room_names:
            continue

        amount = None
        currency = None
        for k in range((room_line_idx or i) + 1, min(len(lines), (room_line_idx or i) + 4)):
            amount, currency = _parse_price_from_line(lines[k])
            if amount is not None:
                break

        # If one amount covers multiple rooms on the same line, don't duplicate it; keep it as payload total.
        per_room_amount = None if len(room_names) > 1 else (str(amount) if amount is not None else None)

        for room_name in room_names:
            if any(
                (
                    r.get("room_name"),
                    r.get("check_in_date"),
                    r.get("check_out_date"),
                )
                == (room_name, check_in.isoformat(), check_out.isoformat())
                for r in rooms
            ):
                continue
            rooms.append(
                {
                    "room_name": room_name,
                    "check_in_date": check_in.isoformat(),
                    "check_out_date": check_out.isoformat(),
                    "amount": per_room_amount,
                    "currency": currency,
                }
            )
    return rooms


def _parse_guest_email(lines: list[str]) -> str | None:
    emails: list[str] = []
    for line in lines:
        if "@" not in line:
            continue
        emails.extend(re.findall(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", line, re.I))

    if not emails:
        return None

    # Prefer Booking guest aliases.
    for e in emails:
        if e.lower().endswith("@guest.booking.com"):
            return e

    # Avoid picking "vendor" / footer emails.
    blocklist_domains = {"rentl.io"}
    for e in emails:
        domain = e.split("@", 1)[-1].lower()
        if domain in blocklist_domains:
            continue
        return e

    return None


def _looks_like_html(text: str) -> bool:
    t = (text or "").lower()
    return "<html" in t or "<body" in t or "<div" in t or "<style" in t or "<!doctype" in t


def _html_to_text(html: str) -> str:
    # Very small sanitizer (no external deps): strip style/script + tags.
    if not html:
        return ""
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)

    # Preserve basic structure; otherwise everything ends up on one line and "near email" heuristics fail.
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p\s*>", "\n", text)
    text = re.sub(r"(?is)</div\s*>", "\n", text)
    text = re.sub(r"(?is)</tr\s*>", "\n", text)
    text = re.sub(r"(?is)</li\s*>", "\n", text)
    text = re.sub(r"(?is)</td\s*>", " ", text)

    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = _html.unescape(text).replace("\xa0", " ")
    return text


def _parse_room_name(*, lines: list[str], subject: str) -> str | None:
    # Rentlio / forwarded templates often have a room line like:
    # "R1 deluxe king, R1 - Deluxe King"
    for line in lines:
        if re.search(r"\bR\s*-?\s*\d+\b", line, re.I) and any(ch.isalpha() for ch in line):
            candidate = line.split(",")[0].strip()
            if 3 <= len(candidate) <= 120:
                return candidate

    s = (subject or "").strip()
    # Fallback: subject tail, e.g. "... 14.02.2026 - 15.02.2026, R1 deluxe king"
    m = re.search(r"(R\s*-?\s*\d+\s+[^,]+)\s*$", s, re.I)
    if m:
        return m.group(1).strip()

    return None


_COUNTRY_TO_ISO2 = {
    "france": "FR",
    "croatia": "HR",
    "hrvatska": "HR",
    "italy": "IT",
    "italia": "IT",
    "germany": "DE",
    "deutschland": "DE",
    "poland": "PL",
    "polska": "PL",
    "united kingdom": "GB",
    "great britain": "GB",
    "uk": "GB",
    "czech republic": "CZ",
    "czechia": "CZ",
    "austria": "AT",
    "osterreich": "AT",
    "österreich": "AT",
    "netherlands": "NL",
    "the netherlands": "NL",
    "nederland": "NL",
    "serbia": "RS",
    "srbija": "RS",
    "montenegro": "ME",
    "crna gora": "ME",
    "slovakia": "SK",
    "slovensko": "SK",
    "slovenia": "SI",
    "slovenija": "SI",
    "finland": "FI",
    "suomi": "FI",
    "spain": "ES",
    "espana": "ES",
    "españa": "ES",
}


def _country_to_iso2(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) == 2 and cleaned.isalpha():
        return cleaned.upper()
    key = cleaned.lower()
    # Handle "Croatia (Hrvatska)" / "France (FR)" and similar.
    key = re.sub(r"\s*\(.*?\)\s*$", "", key).strip()
    return _COUNTRY_TO_ISO2.get(key)


def _parse_name_country_near_email(lines: list[str], guest_email: str) -> tuple[str | None, str | None]:
    # In Rentlio HTML-as-text, the name/country line is usually right above the guest email.
    email_idx = None
    for i, line in enumerate(lines):
        if guest_email.lower() in line.lower():
            email_idx = i
            break
    if email_idx is None:
        return (None, None)

    # Sometimes the whole "name, country" blob is on the same line as the email; try that first.
    email_line = lines[email_idx].strip()
    if "," in email_line and "@" in email_line:
        # Take text before the email address and look for the last comma.
        before_email = email_line.split(guest_email, 1)[0]
        if "," in before_email:
            before, after = before_email.rsplit(",", 1)
            name = before.strip()
            country = after.strip()
            if name and any(ch.isalpha() for ch in name) and not any(ch.isdigit() for ch in name):
                return (name, country)

    for j in range(max(0, email_idx - 3), email_idx):
        line = lines[j].strip()
        if "font-family" in line.lower():
            continue
        if "," in line and "@" not in line:
            before, after = line.split(",", 1)
            name = before.strip()
            country = after.strip()
            if name and any(ch.isalpha() for ch in name) and not any(ch.isdigit() for ch in name):
                return (name, country)
        # Group booking templates sometimes have only "Full Name" on the line above the guest email.
        if "@" not in line and "," not in line:
            candidate = line.strip()
            lowered = candidate.lower()
            if ":" in candidate:
                continue
            if any(ch.isdigit() for ch in candidate):
                continue
            if "booking" in lowered or "reservation" in lowered:
                continue
            if 3 <= len(candidate) <= 120 and " " in candidate and any(ch.isalpha() for ch in candidate):
                return (candidate, None)
    return (None, None)


def _parse_price_line(lines: list[str]) -> tuple[Decimal | None, str | None]:
    # Rentlio examples:
    # "75,65 (Standard rate ...)"
    # "298,10"
    for line in lines:
        amount, currency = _parse_price_from_line(line)
        if amount is not None:
            return (amount, currency)

    return (None, None)


def _infer_kind(subject: str, lines: list[str]) -> str:
    s = (subject or "").lower()
    if "nova rezervacija" in s or "new reservation" in s:
        return "new"
    if "otkaz" in s or "storno" in s:
        return "cancel"
    if "cancel" in s:
        return "cancel"
    if "modify" in s or "amend" in s or "changed" in s:
        return "modify"
    if "confirmed" in s and ("reservation" in s or "booking" in s):
        return "new"
    # Guest messaging / requests (like check-in time request confirmation)
    if any("reservation details" in ln.lower() for ln in lines):
        return "message"
    return "message"


def parse_booking_email(*, subject: str, body_text: str, body_html: str = "") -> BookingPayload:
    source = body_html if body_html else body_text
    if _looks_like_html(source):
        source = _html_to_text(source)
    lines = _clean_lines(source)
    booking_number = _parse_booking_number(lines)
    if not booking_number:
        raise BookingParseException(
            "missing_booking_number",
            "Could not find Booking booking number/confirmation number in email body.",
        )

    guest_full_name = _find_value_after_label(lines, "Guest name")
    guest_email = _parse_guest_email(lines)
    guest_nationality_iso2 = None
    check_in = _parse_booking_date(_find_value_after_label(lines, "Check-in"))
    check_out = _parse_booking_date(_find_value_after_label(lines, "Check-out"))
    property_name = _find_value_after_label(lines, "Property name")
    room_name = _parse_room_name(lines=lines, subject=subject)
    rooms = _parse_room_blocks(lines)
    total_guests = _parse_int(_find_value_after_label(lines, "Total guests"))
    total_rooms = _parse_int(_find_value_after_label(lines, "Total rooms"))
    total_amount, currency = _parse_price_line(lines)
    currency = currency or "EUR" if total_amount is not None else None

    if not check_in or not check_out:
        range_in, range_out = _parse_date_range_from_text(lines)
        check_in = check_in or range_in
        check_out = check_out or range_out

    # Try to pull name/country from the line near guest email first (most reliable for Rentlio templates).
    if guest_email and (not guest_full_name or guest_full_name.lower().startswith("font-family")):
        name, country = _parse_name_country_near_email(lines, guest_email)
        if name:
            guest_full_name = name
        if country:
            guest_nationality_iso2 = _country_to_iso2(country)

    # Label based country (other templates)
    if not guest_nationality_iso2:
        for label in ("Nationality", "Document country", "Country"):
            v = _find_value_after_label(lines, label)
            guest_nationality_iso2 = _country_to_iso2(v) or guest_nationality_iso2

    # Some templates include "Full Name , Country" on one line (without explicit nationality label).
    if not guest_nationality_iso2 and guest_full_name:
        guest_name_norm = guest_full_name.strip().lower()
        for line in lines:
            if "," not in line or "@" in line:
                continue
            before, after = line.split(",", 1)
            if before.strip().lower() == guest_name_norm:
                guest_nationality_iso2 = _country_to_iso2(after)
                if guest_nationality_iso2:
                    break

    if not guest_full_name:
        # Rentlio forward: "Full Name , Country" line.
        for line in lines:
            lowered = line.lower()
            if "font-family" in lowered or "font-size" in lowered or "line-height" in lowered:
                continue
            if "," in line and any(ch.isalpha() for ch in line):
                before, after = line.split(",", 1)
                candidate = before.strip()
                if any(ch.isdigit() for ch in candidate):
                    continue
                if re.search(r"(?i)\\bdeluxe\\b", candidate):
                    continue
                if ":" in candidate:
                    continue
                if 3 <= len(candidate) <= 120 and "booking.com" not in candidate.lower():
                    guest_full_name = candidate
                    if not guest_nationality_iso2:
                        guest_nationality_iso2 = _country_to_iso2(after)
                    break

    kind = _infer_kind(subject, lines)

    # If multi-room blocks exist, prefer them for room_name/total_rooms/amount summary.
    if rooms:
        if not room_name:
            room_name = (rooms[0].get("room_name") or "").strip() or room_name
        if total_rooms is None and len(rooms) > 1:
            total_rooms = len(rooms)
        if len(rooms) > 1:
            # Keep payload.total_amount as a helpful summary (sum) when possible.
            amounts: list[Decimal] = []
            for r in rooms:
                a = r.get("amount")
                if not a:
                    amounts = []
                    break
                try:
                    amounts.append(Decimal(str(a)))
                except Exception:
                    amounts = []
                    break
            if amounts:
                total_amount = sum(amounts).quantize(Decimal("0.01"))
                currency = currency or next((r.get("currency") for r in rooms if r.get("currency")), None)

    return BookingPayload(
        booking_number=booking_number,
        guest_full_name=guest_full_name,
        guest_email=guest_email,
        guest_nationality_iso2=guest_nationality_iso2,
        check_in_date=check_in,
        check_out_date=check_out,
        property_name=property_name,
        room_name=room_name,
        rooms=rooms,
        total_amount=total_amount,
        currency=currency,
        total_guests=total_guests,
        total_rooms=total_rooms,
        kind=kind,
    )
