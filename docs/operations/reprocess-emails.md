# Reprocess Booking emails — kako ponovo parsirati i mapirati

**Last updated:** 2026-02-15
**Status:** Active

Koristi se kad:
- parser je ispravljen i želiš ponovo obraditi stare `InboundEmail` zapise
- želiš backfill novih polja (npr. nationality ISO2)

## Opcija A: reprocess svega (include non-pending)
Ovo će ponovo obraditi i `parsed/partial/failed` zapise.

```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py run_booking_pipeline --once --include-non-pending --process-limit 200"
```

Napomena:
- Fetch dio nije nužan za reprocess; bitan je `process_booking_emails`.

## Opcija B: samo process (bez fetch-a)
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py process_booking_emails --limit 200"
```

## Opcija C: dry-run
Koristi za provjeru parsiranja bez upisa promjena u `Reservation/Guest`.
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py process_booking_emails --limit 50 --dry-run --only-pending"
```

## Kad je potrebno restartati worker
`uzorita-booking-worker` je long-running proces (loop). Ako promijeniš python kod parsera/mappinga:
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose restart booking-worker
```

