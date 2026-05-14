# MVP scope — Booking read-only sync

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** On Hold

## Cilj
U prvoj fazi sustav je read-only prema Booking.com:
- povlačimo podatke (sobe + rezervacije)
- spremamo ih lokalno u Django bazu
- ništa ne mijenjamo na Bookingu (još)

## Status i smjer (2026-02-13)
- Plan je trenutno na cekanju zbog pauze Booking onboarding procesa za nove integracije.
- Aktivni MVP fallback je ingest rezervacija iz booking emailova preko IMAP-a.
- Ovaj scope se aktivira cim Booking ponovo krene prihvacati nove connectivity integracije.

## Što syncamo

### 1) Sobe (Rooms)
Minimalno za MVP:
- `booking_room_id` (unique)
- `name`
- `max_occupancy` (ako postoji)
- `is_active`
- eventualno: opis/amenities (nije must)

### 2) Rezervacije (Reservations)
Minimalno za MVP:
- `booking_reservation_id` (unique)
- `room_booking_id` (FK mapiranje na sobu)
- `checkin_date`, `checkout_date`
- `adults`, `children` (ako postoji)
- `status` (confirmed/modified/canceled ili vaše mapiranje)
- `created_at`, `updated_at` (ako Booking daje)
- osnovni “booker/guest” podaci koliko Booking daje (kasnije se na check-in nadopune)

## Način sinkronizacije
- polling svakih 30 min + gumb Sync now
- idempotentan upis (unique na booking id-jevima)
- audit log svakog sync run-a

## Što nije u MVP-u
- push promjena prema Bookingu (cijene/dostupnost/sadržaj)
- webhooks
- channel manager
