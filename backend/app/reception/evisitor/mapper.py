from __future__ import annotations

import uuid
from datetime import date

from django.conf import settings

from reception.models import Guest, Reservation

from .exceptions import EvisitorValidationError
from .lookups import iso2_to_iso3, map_document_type_code


def _format_yyyymmdd(value: date | None) -> str:
    if not value:
        return ""
    return value.strftime("%Y%m%d")


def _map_gender(sex: str) -> str:
    raw = (sex or "").strip().lower()
    if raw in {"m", "male", "muški", "muski", "muskarac", "muškarac"}:
        return "muški"
    if raw in {"f", "female", "ženski", "zenski", "zena", "žena"}:
        return "ženski"
    return ""


def _resolve_facility_code() -> str:
    from rooms.models import PropertyInfo

    prop = PropertyInfo.objects.filter(is_active=True).order_by("code").first()
    if prop and (prop.evisitor_facility_code or "").strip():
        return prop.evisitor_facility_code.strip()
    return (settings.EVISITOR_FACILITY_CODE or "").strip()


def build_check_in_payload(
    guest: Guest,
    *,
    registration_id: uuid.UUID | None = None,
) -> dict:
    reservation: Reservation = guest.reservation
    errors: dict[str, str] = {}

    first_name = (guest.first_name or "").strip()
    last_name = (guest.last_name or "").strip()
    if not first_name:
        errors["first_name"] = "Ime je obavezno."
    if not last_name:
        errors["last_name"] = "Prezime je obavezno."

    gender = _map_gender(guest.sex)
    if not gender:
        errors["sex"] = "Spol je obavezan (muški/ženski)."

    if not guest.date_of_birth:
        errors["date_of_birth"] = "Datum rođenja je obavezan."

    citizenship = (
        iso2_to_iso3(guest.nationality)
        or iso2_to_iso3(guest.document_country_iso2)
        or (guest.document_country_iso3 or "").strip().upper()[:3]
    )
    if not citizenship or len(citizenship) != 3:
        errors["nationality"] = "Državljanstvo (ISO3) nije poznato."

    document_type = map_document_type_code(guest.document_type, guest.document_code)
    if not document_type:
        errors["document_type"] = "Tip dokumenta nije mapiran na eVisitor šifru."

    document_number = (guest.document_number or "").strip()
    if not document_number:
        errors["document_number"] = "Broj dokumenta je obavezan."

    facility = _resolve_facility_code()
    if not facility:
        errors["facility"] = "Šifra objekta (Facility) nije konfigurirana."

    if not reservation.check_in_date or not reservation.check_out_date:
        errors["stay_dates"] = "Datumi boravka rezervacije nisu postavljeni."

    country_of_residence = citizenship
    if guest.document_country_iso3:
        country_of_residence = guest.document_country_iso3.strip().upper()[:3]

    city_of_residence = ""
    if guest.address and "," in guest.address:
        city_of_residence = guest.address.split(",")[0].strip()
    elif guest.address:
        city_of_residence = guest.address.strip()[:64]

    if errors:
        raise EvisitorValidationError(
            "Podaci gosta nisu potpuni za eVisitor prijavu.",
            field_errors=errors,
        )

    reg_id = registration_id or uuid.uuid4()
    return {
        "ID": str(reg_id),
        "Facility": facility,
        "TouristName": first_name,
        "TouristSurname": last_name,
        "TouristMiddleName": "",
        "Gender": gender,
        "DateOfBirth": _format_yyyymmdd(guest.date_of_birth),
        "Citizenship": citizenship,
        "CountryOfBirth": citizenship,
        "CityOfBirth": city_of_residence or "-",
        "CountryOfResidence": country_of_residence,
        "CityOfResidence": city_of_residence or "-",
        "ResidenceAddress": (guest.address or "-").strip()[:128],
        "DocumentType": document_type,
        "DocumentNumber": document_number[:16],
        "StayFrom": _format_yyyymmdd(reservation.check_in_date),
        "TimeStayFrom": settings.EVISITOR_DEFAULT_STAY_TIME_FROM,
        "ForeseenStayUntil": _format_yyyymmdd(reservation.check_out_date),
        "TimeEstimatedStayUntil": settings.EVISITOR_DEFAULT_STAY_TIME_UNTIL,
        "ArrivalOrganisation": settings.EVISITOR_DEFAULT_ARRIVAL_ORGANISATION,
        "OfferedServiceType": settings.EVISITOR_DEFAULT_OFFERED_SERVICE_TYPE,
        "TTPaymentCategory": settings.EVISITOR_DEFAULT_PAYMENT_CATEGORY,
        "TouristEmail": (guest.email or "").strip(),
        "TouristTelephone": "",
    }


def mask_payload_for_log(payload: dict) -> dict:
    masked = dict(payload)
    for key in ("DocumentNumber", "TouristEmail", "TouristTelephone", "ResidenceAddress"):
        if key in masked and masked[key]:
            masked[key] = "***"
    return masked
