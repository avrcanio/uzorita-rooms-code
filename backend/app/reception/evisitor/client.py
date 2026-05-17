from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from django.conf import settings

from .exceptions import EvisitorApiError, EvisitorConfigError

logger = logging.getLogger(__name__)

_PROD_API_MARKER = "eVisitorRhetos_API"
_TEST_API_MARKER = "testApi"


class EvisitorClient:
    def __init__(self) -> None:
        self._ensure_config()
        self._session = httpx.Client(timeout=60.0, follow_redirects=True)

    def _ensure_config(self) -> None:
        if not settings.EVISITOR_ENABLED:
            raise EvisitorConfigError("eVisitor integracija nije uključena (EVISITOR_ENABLED).")
        if not settings.EVISITOR_BASE_URL:
            raise EvisitorConfigError("EVISITOR_BASE_URL nije postavljen.")
        if not settings.EVISITOR_USERNAME or not settings.EVISITOR_PASSWORD:
            raise EvisitorConfigError("EVISITOR_USERNAME / EVISITOR_PASSWORD nisu postavljeni.")
        base = settings.EVISITOR_BASE_URL
        env = (settings.EVISITOR_ENV or "test").lower()
        if env == "test" and _PROD_API_MARKER in base and _TEST_API_MARKER not in base:
            raise EvisitorConfigError(
                "EVISITOR_ENV=test ali BASE_URL izgleda kao produkcija. Koristite testApi URL."
            )
        if env == "test" and not settings.EVISITOR_API_KEY:
            raise EvisitorConfigError("EVISITOR_API_KEY je obavezan na testnoj okolini.")

    @property
    def _auth_url(self) -> str:
        return f"{settings.EVISITOR_BASE_URL}/Resources/AspNetFormsAuth/Authentication/"

    @property
    def _rest_url(self) -> str:
        return f"{settings.EVISITOR_BASE_URL}/Rest/Htz/"

    def login(self) -> bool:
        payload: dict[str, Any] = {
            "UserName": settings.EVISITOR_USERNAME,
            "Password": settings.EVISITOR_PASSWORD,
            "PersistCookie": False,
        }
        if settings.EVISITOR_API_KEY:
            payload["apikey"] = settings.EVISITOR_API_KEY
        response = self._session.post(f"{self._auth_url}Login", json=payload)
        if response.status_code != 200:
            raise EvisitorApiError(
                f"eVisitor login HTTP {response.status_code}",
                system_message=response.text[:500],
                status_code=response.status_code,
            )
        body = (response.text or "").strip().lower()
        if body != "true":
            raise EvisitorApiError(
                "eVisitor login nije uspio (korisničko ime, lozinka ili apikey).",
                system_message=response.text[:500],
                status_code=response.status_code,
            )
        return True

    def logout(self) -> None:
        try:
            self._session.post(f"{self._auth_url}Logout", json={})
        except httpx.HTTPError:
            logger.debug("eVisitor logout failed", exc_info=True)

    def execute_action(self, action: str, data: dict[str, Any]) -> None:
        url = f"{self._rest_url}{action.strip('/')}/"
        response = self._session.post(url, json=data)
        if response.status_code != 200:
            raise EvisitorApiError(
                f"eVisitor {action} HTTP {response.status_code}",
                system_message=response.text[:500],
                status_code=response.status_code,
            )
        text = (response.text or "").strip()
        if not text:
            return
        try:
            payload = response.json()
        except json.JSONDecodeError:
            raise EvisitorApiError(
                f"eVisitor {action} neočekivan odgovor.",
                system_message=text[:500],
                status_code=response.status_code,
            )
        if isinstance(payload, dict) and (
            payload.get("UserMessage") or payload.get("SystemMessage")
        ):
            raise EvisitorApiError(
                payload.get("UserMessage") or "eVisitor validacijska greška.",
                user_message=str(payload.get("UserMessage") or ""),
                system_message=str(payload.get("SystemMessage") or ""),
                status_code=response.status_code,
            )

    def fetch_records(
        self,
        resource: str,
        *,
        psize: int = 50,
        page: int = 1,
        filters: list[dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"psize": psize, "page": page}
        if filters:
            params["filters"] = json.dumps(filters)
        query = urlencode(params)
        url = f"{self._rest_url}{resource.strip('/')}/?{query}"
        response = self._session.get(url)
        if response.status_code != 200:
            raise EvisitorApiError(
                f"eVisitor GET {resource} HTTP {response.status_code}",
                system_message=response.text[:500],
                status_code=response.status_code,
            )
        payload = response.json()
        if isinstance(payload, dict):
            records = payload.get("Records")
            if isinstance(records, list):
                return [r for r in records if isinstance(r, dict)]
        return []

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> EvisitorClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
