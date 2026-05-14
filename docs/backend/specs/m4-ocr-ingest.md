# M4 OCR Ingest Spec (Backend)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** In Progress

## Scope
- Primiti OCR rezultat sa frontend scan ekrana.
- Spremiti OCR log.
- Normalizirati payload i auto-upisati prepoznata polja u `Guest`.

## Endpoint
- `POST /api/reception/reservations/{reservation_id}/guests/{guest_id}/ocr/`
- View: `ReservationGuestOcrView`
- Provider (aktivan): `microblink`

## Trenutno ponasanje
- Validira da guest pripada rezervaciji.
- Prihvata `raw_payload`, `suggested_fields`, `corrected_fields`, `duration_ms`.
- Ako `suggested_fields` postoji -> status `ok`; inace `failed`.
- Uvijek zapisuje `OcrScanLog` sa raw payload-om i statusom.
- Kod statusa `ok` mapira polja na `Guest` i radi `save(update_fields=...)`.

## Gost polja koja se popunjavaju iz OCR-a
- Osnovno:
  - `first_name`, `last_name`, `date_of_birth`, `nationality`, `document_number`
- Dodatno:
  - `sex`, `address`, `date_of_issue`, `date_of_expiry`, `issuing_authority`
  - `personal_id_number`, `document_additional_number`, `additional_personal_id_number`
  - `document_code`, `document_type`
  - `document_country`, `document_country_iso2`, `document_country_iso3`, `document_country_numeric`
  - `mrz_raw_text`, `mrz_verified`

## Modeli
- `Guest` (prosiren OCR/document poljima)
- `OcrScanLog` (audit OCR pokusaja)
- Provider choices: trenutno samo `microblink`

## Napomene
- PassportEye provider je uklonjen iz aktivnog model choices i flow-a.
- OCR ingest trenutno ne sprema image binary ni image storage pointere (to je kasniji task).

## Otvoreno
- Manual review queue za failed/partial OCR.
- Check-in wizard status tranzicije nakon OCR potvrde.
- Dodatni quality metrics i alerting.
