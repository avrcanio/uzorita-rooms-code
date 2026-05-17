from __future__ import annotations

import logging
from functools import lru_cache

from django.conf import settings

from .client import EvisitorClient
from .exceptions import EvisitorApiError, EvisitorConfigError

logger = logging.getLogger(__name__)

# Common document types (eVisitor CODE); extend via API cache later.
_DOCUMENT_TYPE_MAP = {
    "passport": "008",
    "putovnica": "008",
    "putovnica.": "008",
    "id": "027",
    "identity": "027",
    "osobna": "027",
    "osobna iskaznica": "027",
    "identity card": "027",
}


@lru_cache(maxsize=1)
def _iso2_to_iso3_map() -> dict[str, str]:
    if not settings.EVISITOR_ENABLED:
        return {}
    try:
        client = EvisitorClient()
        client.login()
        records = client.fetch_records(
            "Country",
            psize=300,
            filters=[{"Property": "Active", "Operation": "equal", "Value": "true"}],
        )
        mapping: dict[str, str] = {}
        for row in records:
            iso2 = (row.get("CodeTwoLetters") or "").strip().upper()
            iso3 = (row.get("CodeThreeLetters") or "").strip().upper()
            if iso2 and iso3:
                mapping[iso2] = iso3
        return mapping
    except (EvisitorConfigError, EvisitorApiError) as exc:
        logger.warning("eVisitor country lookup failed: %s", exc)
        return {}


def iso2_to_iso3(iso2: str) -> str:
    code = (iso2 or "").strip().upper()
    if len(code) == 3:
        return code
    if len(code) != 2:
        return ""
    mapped = _iso2_to_iso3_map().get(code)
    if mapped:
        return mapped
    # Fallback for common codes when API unavailable (e.g. tests).
    fallbacks = {
        "HR": "HRV",
        "DE": "DEU",
        "IT": "ITA",
        "AT": "AUT",
        "SI": "SVN",
        "BE": "BEL",
        "FR": "FRA",
        "NL": "NLD",
        "GB": "GBR",
        "US": "USA",
        "CH": "CHE",
        "PL": "POL",
        "CZ": "CZE",
        "SK": "SVK",
        "HU": "HUN",
        "RS": "SRB",
        "BA": "BIH",
        "ME": "MNE",
        "MK": "MKD",
        "AL": "ALB",
        "GR": "GRC",
        "ES": "ESP",
        "PT": "PRT",
        "SE": "SWE",
        "NO": "NOR",
        "DK": "DNK",
        "FI": "FIN",
        "IE": "IRL",
        "LU": "LUX",
        "IN": "IND",
    }
    return fallbacks.get(code, "")


def map_document_type_code(document_type: str, document_code: str = "") -> str:
    raw = f"{document_type} {document_code}".strip().lower()
    if not raw:
        return ""
    for key, code in _DOCUMENT_TYPE_MAP.items():
        if key in raw:
            return code
    if document_code.strip().isdigit():
        return document_code.strip()
    return ""
