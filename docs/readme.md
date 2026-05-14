# Uzorita Rooms - Documentation

Dokumentacija živi u istom Git repozitoriju kao kod, u mapi **`docs/`** (root repozitorija).

**Owner:** TBD
**Last updated:** 2026-05-14
**Status:** Draft

Ovaj folder je organizovan po domenima, tako da su odluke i specifikacije lakse za pronalazenje i odrzavanje.

## Changelog

### 2026-05-14
- Dodan backend `POST /api/v1/scan/` (PaddleOCR + MRZ, audit `DocumentScanLog`, bez izmjene `Guest`). Spec: `backend/specs/ocr-paddle-scan-api.md`.

### 2026-02-13
- Reorganizovana dokumentacija po domenima i uveden centralni indeks.
- M1 dokumentovan kao zavrsen (backend bootstrap, role/permisije, `reception` app, lokalizacija).
- M2 plan prebacen na email/IMAP fallback zbog Booking onboarding pauze.
- Dodan M2 runbook: `backend/specs/m2-email-ingest.md` (IMAP ingest + cron + DNS mail status).
- Uskladjeni backend decisions zapisi sa implementiranim stanjem.
- Pokrenut M3 frontend foundation (`Next.js + Tailwind`) i deploy na `rooms.uzorita.hr`.
- Dodan frontend spec: `frontend/specs/m3-reception-ui-foundation.md`.
- Dodan Django REST + OpenAPI docs (`/api/schema/`, `/api/docs/`, `/api/redoc/`).
- M4 OCR flow je pokrenut preko Microblink Browser SDK.
- Gost detalj (`/reservations/[id]/guests/[guestId]`) koristi odvojeni scan ekran (`/scan`) umjesto inline OCR bloka.
- Backend OCR ingest endpoint mapira Microblink payload u `Guest` polja i zapisuje `OcrScanLog`.
- PassportEye je uklonjen iz aktivnog OCR providera; koristi se samo `microblink`.
- Prosiren `Guest` model za dodatna ID/MRZ polja (OIB/personal ID, issue/expiry, issuing authority, country metapodaci, `mrz_raw_text`, `mrz_verified`).

## Struktura

- `overview/`
  - `brainstorming.md` - inicijalni okvir proizvoda
  - `global-steps.md` - high-level redosled implementacije
  - `todo-milestones.md` - procena sati i milestone-i
- `integrations/`
  - `booking-sync.md` - Booking sync flow (MVP)
  - `mvp-sync-scope.md` - scope sinkronizacije u MVP-u
  - `sync-state.md` - cursor/sync state pravila
  - `evisitor.md` - eVisitor flow i statusi
- `billing/`
  - `checkout-mvp.md` - check-out i naplata (MVP)
  - `payments.md` - model naplate (MVP + kasnije)
  - `currency.md` - valuta i prikaz
  - `invoice-numbering.md` - numeracija racuna
  - `invoice-pdf.md` - generiranje i pohrana PDF racuna
  - `fiscalization.md` - fiskalizacija flow i retry
- `reception/`
  - `reception-mvp.md` - recepcija i check-in tok
  - `reservation-status.md` - statusi rezervacija
- `operations/`
  - `admin-ops.md` - podela odgovornosti recepcija/admin
  - `audit.md` - audit log model
- `backend/`
  - `decisions.md` - backend tehnicke odluke
  - `specs/m1-foundation.md` - M1 backend+infra specifikacija i runbook
  - `specs/m2-email-ingest.md` - M2 IMAP/email ingest specifikacija i operativa
  - `specs/m4-ocr-ingest.md` - M4 OCR ingest endpoint i mapiranje na gosta
  - `specs/ocr-paddle-scan-api.md` - PaddleOCR file scan + MRZ (`POST /api/v1/scan/`) bez auto-updatea gosta
  - `brainstorm/` - radne backend ideje
  - `specs/` - backend specifikacije
- `frontend/`
  - `decisions.md` - frontend tehnicke odluke
  - `brainstorm/` - radne frontend ideje
  - `specs/m3-reception-ui-foundation.md` - M3 frontend foundation i deploy spec
  - `specs/m4-checkin-ocr-flow.md` - M4 OCR scan flow (frontend)
- `product/`
  - `vision.md` - product vizija
  - `roadmap.md` - jedini canonical product roadmap
  - `faq.md` - product FAQ

## Pravilo organizacije

- Novi dokument ide u domen koji najvise opisuje njegovu svrhu.
- Ako dokument predstavlja odluku, navesti datum i kontekst odluke na vrhu.
- Ako dokument postane predugacak, podeliti ga na manjih vise fokusiranih dokumenata.
