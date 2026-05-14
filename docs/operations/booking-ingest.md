# Booking ingest (IMAP -> Reservations) — Runbook

**Last updated:** 2026-02-15
**Status:** Active

Ovaj dokument pokriva operativni dio ingest-a Booking.com emailova u rezervacije.

## Arhitektura (MVP)
- IMAP fetch: `communications.InboundEmail` (+ attachments)
- Parser: `communications.booking_parser`
- Mapping: `communications.services` -> `reception.Reservation` + `reception.Guest`
- Periodic job: `run_booking_pipeline` u containeru `uzorita-booking-worker`

## Konfiguracija (.env)
Bitno:
- `MAILBOX_EMAIL`
- `MAILBOX_PASSWORD`
- `IMAP_HOST`
- `IMAP_PORT`
- `IMAP_USE_SSL`
- `IMAP_FOLDER` (default `INBOX`)

## Servisi (Docker)
Backend stack je u:
`/opt/stacks/uzorita/rooms/code/backend`

Provjera statusa:
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose ps
```

Logovi:
```bash
docker logs -f uzorita-booking-worker
docker logs -f uzorita-django
```

## Ručno pokretanje pipeline-a (jednom)
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py run_booking_pipeline --once --fetch-limit 50 --process-limit 50 --mark-seen"
```

## Django admin (review)
U adminu možeš pregledati:
- `Communications -> Inbound emails`
  - filter `parse_status`: `pending/parsed/partial/failed`
  - `ParseError` inline pokazuje razloge (ako je `partial/failed`)

## Najčešći problemi
### 1) Ne dolaze novi mailovi
Provjeri:
- IMAP credentials i folder (`IMAP_FOLDER`)
- log `uzorita-booking-worker` (fetch dio)
- da li mailbox uopće ima nove poruke (ručno IMAP provjera)

### 2) Parser “partial/failed”
- Otvori `InboundEmail` u adminu i pogledaj `ParseError`.
- Ako je template promijenjen, treba proširiti parser.

### 3) Duplikati rezervacija
MVP dedupe:
- `InboundEmail.message_id` je unique (nema duplog ingest-a istog emaila)
- `Reservation.external_id` je unique (idempotent update)
- Za multi-room: `external_id` sufiksi `-2`, `-3`, ...

