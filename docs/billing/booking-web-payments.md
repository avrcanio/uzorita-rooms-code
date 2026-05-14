# Booking web — plaćanje (postpaid / pay on arrival)

**Last updated:** 2026-02-16  
**Status:** Active (MVP)

## MVP pravilo
- Plaćanje je **po dolasku** (postpaid).
- Dozvoljene metode:
  - **Kartica po dolasku**
  - **Gotovina po dolasku**
- Nema online plaćanja u MVP-u (Viva kasnije).

## Impl. napomena
- `POST /public/bookings/confirm` kreira booking kao `CONFIRMED` (ako je dostupno).
- Preporuka: koristiti `HOLD` (10 min) da se spriječi overbooking dok korisnik ispunjava checkout.