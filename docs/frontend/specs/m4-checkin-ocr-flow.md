# M4 OCR Scan Flow (Frontend)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** In Progress

## Scope
- Omoguciti recepciji skeniranje osobnog dokumenta gosta preko kamere.
- Koristiti odvojeni screen za OCR skeniranje.
- Spremiti rezultat kroz backend OCR endpoint i vratiti korisnika na detail gosta.

## Implementirano
- Guest detail ruta (`/reservations/[id]/guests/[guestId]`) vise ne sadrzi inline OCR UI.
- Dodan CTA `Skeniraj dokument` koji vodi na:
  - `code/frontend/app/reservations/[id]/guests/[guestId]/scan/page.tsx`
- Scan screen:
  - Provjera auth sesije (`/api/auth/me/`).
  - Ucitavanje `@microblink/blinkid` SDK-a.
  - Pokretanje kamere i automatic scanning mode.
  - Slanje payload-a na backend OCR endpoint.
  - Povratak na guest detail nakon uspjesnog upisa.

## Env varijable
- `NEXT_PUBLIC_MICROBLINK_LICENSE_KEY`
- `NEXT_PUBLIC_MICROBLINK_RESOURCES` (default `/resources`)

## Resource hosting
- BlinkID web resources moraju biti dostupni kao staticki fajlovi iz `public/resources`.
- Ako worker file vraca `text/html`, skeniranje nece raditi (pogresan static routing).

## API integracija
- OCR ingest endpoint:
  - `POST /api/reception/reservations/{reservation_id}/guests/{guest_id}/ocr/`
- Payload koji frontend salje:
  - `provider: "microblink"`
  - `raw_payload`
  - `suggested_fields`
  - `duration_ms`

## Otvoreno
- Wizard koraci za check-in jos nisu uvedeni.
- OCR fallback/ručna korekcija UI i dalje je otvoren task.
- Usporedba vise providera je pauzirana; aktivan je samo Microblink.
