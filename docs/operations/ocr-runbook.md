# OCR (Microblink) — Runbook

**Last updated:** 2026-02-15
**Status:** Draft

Ovaj dokument pokriva operativni dio OCR skeniranja dokumenata gostiju (Microblink).

## UI flow
- Guest detail: `/reservations/:id/guests/:guestId`
- Scan ekran: `/reservations/:id/guests/:guestId/scan`

## Backend endpoint
- `POST /api/reception/reservations/{id}/guests/{guestId}/ocr/`

## Audit
- Svaki scan zapisuje `OcrScanLog` (status + payload).

## Troubleshooting (osnovno)
- Ako kamera ne radi: provjeri browser permissions (mobile Safari/Chrome).
- Ako Microblink javlja licence/resource error: provjeri licencu i bundlane assets u frontend build-u.

## TODO
- Dodati konkretne poruke grešaka koje smo vidjeli u produkciji i upute za recepciju.

