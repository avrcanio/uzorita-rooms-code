"""URL helpers for Booking extranet (no Playwright dependency)."""

from django.conf import settings


def success_url_pattern() -> str:
    return (settings.BOOKING_EXTRANET_SUCCESS_URL_CONTAINS or "search_reservations.html").strip()


def is_connected_url(url: str) -> bool:
    lowered = (url or "").lower()
    needle = success_url_pattern().lower()
    return "admin.booking.com" in lowered and (not needle or needle in lowered)


def is_login_redirect_url(url: str) -> bool:
    lowered = (url or "").lower()
    return "account.booking.com" in lowered and "/sign-in" in lowered
