# Booking ingest (IMAP -> Reservations) — Runbook

**Last updated:** 2026-05-16
**Status:** Active

Ovaj dokument pokriva operativni dio ingest-a Booking.com emailova u rezervacije.

## Arhitektura
- IMAP fetch: `communications.InboundEmail` (+ attachments)
- Parser: `communications.booking_parser`
- Mapping: `communications.services` -> `reception.Reservation` + `reception.Guest`
- Periodic job: Celery task `run_booking_email_pipeline_task` (beat svake **2 min**)

## Konfiguracija (.env)
Bitno:
- `MAILBOX_EMAIL`
- `MAILBOX_PASSWORD`
- `IMAP_HOST`
- `IMAP_PORT`
- `IMAP_USE_SSL`
- `IMAP_FOLDER` (default `INBOX`)
- `IMAP_CONNECT_HOST=mailserver` + `IMAP_TLS_SERVERNAME=mail.finestar.hr` (Celery na `hetzner_net`)
- `CELERY_BROKER_URL=redis://infra-redis:6379/1`
- `DB_HOST=postgis` (hetzner_net)

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
docker logs -f uzorita-celery-worker
docker logs -f uzorita-celery-beat
docker logs -f uzorita-django
```

## Ručno pokretanje pipeline-a (jednom)
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py run_booking_pipeline --once --fetch-limit 50 --process-limit 50 --mark-seen"
```

Ili direktno Celery task (u worker kontejneru):
```bash
docker exec uzorita-celery-worker celery -A config call communications.tasks.run_booking_email_pipeline_task
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
- log `uzorita-celery-worker` (fetch dio)
- da li mailbox uopće ima nove poruke (ručno IMAP provjera)
- `docker exec uzorita-celery-worker celery -A config inspect ping`

### 2) Parser “partial/failed”
- Otvori `InboundEmail` u adminu i pogledaj `ParseError`.
- Ako je template promijenjen, treba proširiti parser.

### 3) Duplikati rezervacija
MVP dedupe:
- `InboundEmail.message_id` je unique (nema duplog ingest-a istog emaila)
- `Reservation.external_id` je unique (idempotent update)
- Za multi-room: `external_id` sufiksi `-2`, `-3`, ...

## Deploy / test plan (nakon promjene Celeryja)
1. `docker exec infra-redis redis-cli ping` → `PONG`
2. `docker exec uzorita-celery-worker celery -A config inspect ping`
3. `curl -I https://rooms.uzorita.hr/health/` → 200
4. Logovi workera: task `run_booking_email_pipeline_task` svake ~2 min
