# Sync state (cursor) — booking_updated_at

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

## Odluka
Cursor = booking_updated_at (ako API daje).

## Pravilo
- čuvamo `booking_cursor_updated_at` u sync_state
- dohvaćamo promjene >= cursor
- nakon uspjeha cursor = max(booking_updated_at) viđen u run-u

## Fallback
Ako booking_updated_at nije pouzdan/dostupan:
- privremeno prebaciti na last_success_sync_at
