# Audit log (MVP) — kompletan payload

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

## Odluka
Spremamo kompletan raw payload (JSON) iz Booking sinkronizacije.

## Tablice
### sync_run
- meta o svakom pokretanju (cron/manual), status, stats

### sync_event
- po entitetu/akciji
- payload: jsonb (kompletan)
- opcionalno payload_hash za deduplikaciju

## Napomena
Osobne i OCR podaci (check-in) NE idu u ovaj audit.

# Audit log (MVP) — raw + mapping

## Odluka
Spremamo:
- raw payload (jsonb) 1:1
- mapping stupce za brze upite

## sync_event (sažetak)
Obavezno:
- run_id, entity_type, action, external_id
- received_at, processed_at, process_status, error
- payload (jsonb)

Mapping (best-effort):
ROOM: room_booking_id, room_name, room_is_active
RESERVATION: reservation_booking_id, room_booking_id, checkin_date, checkout_date,
adults, children, booking_status

## Indeksi
- (run_id)
- (entity_type, external_id, received_at desc)
- (room_booking_id, checkin_date) za rezervacije
