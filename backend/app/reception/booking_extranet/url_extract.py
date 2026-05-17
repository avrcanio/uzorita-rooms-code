"""Extract Booking extranet URLs and booking numbers from email content."""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, urlparse

_BOOKING_PAGE_RE = re.compile(
    r"https://admin\.booking\.com/hotel/hoteladmin/extranet_ng/manage/booking\.html\?[^\s\"'<>]+",
    re.I,
)


def extract_booking_url_from_text(text: str) -> str | None:
    if not text:
        return None
    match = _BOOKING_PAGE_RE.search(text)
    if not match:
        return None
    return html.unescape(match.group(0))


def extract_res_id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get("res_id") or []
    if values and re.fullmatch(r"\d{6,12}", values[0]):
        return values[0]
    return None


def build_booking_url(*, res_id: str, hotel_id: str) -> str:
    return (
        "https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/"
        f"booking.html?res_id={res_id}&hotel_id={hotel_id}"
    )
