# Booking sinkronizacija (MVP)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** On Hold

## Odabrano
- Polling svakih **30 minuta**
- gumb **Sync now** (ručno pokretanje sinkronizacije)

## Status i smjer (2026-02-13)
- Booking.com onboarding za nove connectivity providere je trenutno pauziran.
- Ovaj dokument ostaje kao ciljna integracija kada Booking ponovo otvori onboarding.
- Do tada MVP koristi email ingest pipeline (IMAP + parser) za rezervacije.

## Kako radi (sažeto)
- sustav pamti `last_sync_at`
- na svakom sync-u dohvaća promjene od `last_sync_at`
- upis je **idempotentan** (unique po `booking_reservation_id`)
- logiramo payload + rezultat obrade
- nakon uspjeha ažuriramo `last_sync_at`

## Sync now
- pokreće isti proces kao i polling
- UI prikazuje: zadnji sync, broj promjena, greške

## Edge-caseovi
- dupli događaji / ponovljeni podaci
- otkaz rezervacije
- izmjena datuma / broja gostiju / sobe
- rate-limit: retry + backoff
