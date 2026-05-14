# M2 Email Ingest Spec (IMAP + Parser)

**Owner:** TBD
**Last updated:** 2026-02-15
**Status:** Implemented (MVP), ongoing improvements

## Kontekst
- Booking.com onboarding za nove connectivity integracije je trenutno pauziran.
- MVP koristi fallback: ingest rezervacijskih emailova sa mailbox-a `room_reservations@uzorita.hr`.

## Trenutno implementirano
- Django app: `communications`.
- Modeli:
  - `InboundEmail`
  - `OutboundEmail`
  - `EmailAttachment`
  - `ParseError`
- IMAP ingest komanda:
  - `python manage.py fetch_booking_emails --limit 50 --mark-seen`
- Deduplikacija:
  - po `Message-ID` (`InboundEmail.message_id` je unique).
- Admin registracija communications modela je aktivna.
- Booking parser:
  - normalizira HTML -> tekst (strip style/script, br->newline)
  - prepoznaje `new/modify/cancel`
  - podržava multi-room mailove (više soba u jednom emailu)
  - best-effort mapiranje nationality -> ISO2
- Booking pipeline:
  - `python manage.py process_booking_emails` mapira payload u `reception.Reservation` + `reception.Guest`
  - idempotent update po `external_id`
  - cancel email otkazuje i multi-room rezervacije (sufiksi `-2`, `-3`, ...)

## Runtime konfiguracija (env)
- `MAILBOX_EMAIL`
- `MAILBOX_PASSWORD`
- `IMAP_HOST`
- `IMAP_PORT`
- `IMAP_USE_SSL`
- `IMAP_FOLDER`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USE_SSL`
- `SMTP_USE_TLS`
- `SMTP_USER`
- `SMTP_PASSWORD`

## Operativne komande
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py fetch_booking_emails --limit 50 --mark-seen"
```

## Periodic worker (production-like)
Koristimo long-running worker container (`booking-worker`) koji vrti:
- fetch (IMAP): `fetch_booking_emails`
- process (DB): `process_booking_emails`

Komanda:
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose up -d booking-worker
docker logs -f uzorita-booking-worker
```

Jednokratno pokretanje (korisno za cron/manual):
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py run_booking_pipeline --once --fetch-limit 50 --process-limit 50 --mark-seen"
```

## Mail DNS status (uzorita.hr)
- DKIM:
  - `hostingermail-a._domainkey` -> `hostingermail-a.dkim.mail.hostinger.com`
  - `hostingermail-b._domainkey` -> `hostingermail-b.dkim.mail.hostinger.com`
  - `hostingermail-c._domainkey` -> `hostingermail-c.dkim.mail.hostinger.com`
- DMARC:
  - `_dmarc` -> `v=DMARC1; p=none`
- SPF:
  - `v=spf1 include:_spf.mail.hostinger.com ~all`

## Otvoreno (sljedece)
- Operativni audit log run-a (stats per run) + metrika.
- Admin “review queue” za `partial/failed` sa predloženim ispravcima i ručnim finalize.
