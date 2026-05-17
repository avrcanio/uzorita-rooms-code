"""Redis-backed VNC access tokens for noVNC + Traefik ForwardAuth."""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

VNC_REDIS_PREFIX = "booking_vnc:"
VNC_ACTIVE_KEY = "booking_vnc:active"


def _redis_client() -> redis.Redis:
    return redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


def _ttl_seconds() -> int:
    return max(60, int(settings.BOOKING_EXTRANET_VNC_TOKEN_TTL_SECONDS or 1200))


def issue_vnc_token(
    *,
    user_id: int,
    job_id: int | None = None,
) -> str:
    token = secrets.token_urlsafe(32)
    payload = {
        "user_id": user_id,
        "job_id": job_id,
    }
    client = _redis_client()
    client.setex(
        f"{VNC_REDIS_PREFIX}{token}",
        _ttl_seconds(),
        json.dumps(payload),
    )
    client.setex(VNC_ACTIVE_KEY, _ttl_seconds(), json.dumps({"token": token, **payload}))
    return token


def get_active_vnc() -> dict[str, Any] | None:
    raw = _redis_client().get(VNC_ACTIVE_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def clear_active_vnc() -> None:
    active = get_active_vnc()
    if active and active.get("token"):
        revoke_vnc_token(str(active["token"]))
    _redis_client().delete(VNC_ACTIVE_KEY)


def get_vnc_token_payload(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    raw = _redis_client().get(f"{VNC_REDIS_PREFIX}{token}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def revoke_vnc_token(token: str) -> None:
    if token:
        _redis_client().delete(f"{VNC_REDIS_PREFIX}{token}")


def refresh_vnc_token_ttl(token: str) -> bool:
    """Extend token TTL without rotating the secret (keeps an open noVNC WebSocket valid)."""
    payload = get_vnc_token_payload(token)
    if not payload:
        return False
    ttl = _ttl_seconds()
    client = _redis_client()
    client.setex(f"{VNC_REDIS_PREFIX}{token}", ttl, json.dumps(payload))
    client.setex(
        VNC_ACTIVE_KEY,
        ttl,
        json.dumps({"token": token, **payload}),
    )
    return True


def validate_vnc_token(token: str, *, user_id: int | None = None) -> bool:
    payload = get_vnc_token_payload(token)
    if not payload:
        return False
    if user_id is not None and payload.get("user_id") != user_id:
        return False
    return True


def build_vnc_url(token: str) -> str:
    public_path = (settings.BOOKING_EXTRANET_VNC_PUBLIC_PATH or "/booking-vnc").rstrip("/")
    # vnc_lite gradi wss://host/{path} — path mora uključivati booking-vnc prefiks (ne samo websockify).
    ws_path = f"{public_path.lstrip('/')}/websockify?token={token}"
    query = urlencode(
        {
            "token": token,
            "autoconnect": "true",
            "scale": "true",
            "path": ws_path,
        }
    )
    return f"{public_path}/vnc_lite.html?{query}"


def extract_vnc_token_from_request(request) -> str:
    """Token from query, Traefik X-Forwarded-Uri, or X-Booking-Vnc-Token."""
    token = (request.GET.get("token") or "").strip()
    if token:
        return token

    header_token = (request.headers.get("X-Booking-Vnc-Token") or "").strip()
    if header_token:
        return header_token

    forwarded_uri = (request.headers.get("X-Forwarded-Uri") or "").strip()
    if "?" in forwarded_uri:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(forwarded_uri)
        values = parse_qs(parsed.query).get("token") or []
        if values:
            return values[0].strip()
    return ""
