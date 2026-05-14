# Statusi rezervacije (model 2)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

## Koncept
Imamo dva sloja:
1) Booking status (OTA)
2) Operativni status (Uzorita)

## 1) Booking status
- PENDING (ako postoji)
- CONFIRMED
- CANCELLED
- NO_SHOW (ako postoji)

## 2) Operativni status
- EXPECTED
- CHECKED_IN
- CHECKED_OUT
- CLOSED

## Pravila
- CONFIRMED (nova) → EXPECTED
- CANCELLED → CLOSED
- NO_SHOW → CLOSED
- check-in → CHECKED_IN
- check-out → CHECKED_OUT
