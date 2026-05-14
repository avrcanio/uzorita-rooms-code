# Viva (Smart Checkout) — smoke testovi (MVP)

**Last updated:** 2026-02-16  
**Status:** Draft

Cilj: kratki testovi koji potvrđuju da booking flow radi end-to-end, s obaveznim plaćanjem u visokoj sezoni.

## Odluke (za ove testove)
- Ako plaćanje ne uspije: booking ostaje `PENDING_PAYMENT` (retry bez kreiranja nove rezervacije).
- `orderCode` se tretira kao string.


## Preduvjeti
- booking web radi: search → room → checkout → confirmation
- backend ima:
  - `POST /public/holds`
  - `POST /public/pricing/quote`
  - `POST /public/bookings/confirm`
  - webhook `POST /webhooks/payments/viva`
- dokumenti: `billing/booking-web-payments.md`, `billing/cancellation-policy.md`

## Test 0 — Kontrola sezone
1) Check-in u 05 mjesec → očekuj `payment_required=false`  
2) Check-in u 06 mjesec → očekuj `payment_required=true`

## Test 1 — Niska sezona (bez online plaćanja)
1) Search datumi u niskoj sezoni  
2) Odaberi sobu/combo i napravi hold  
3) Checkout:
   - glavni gost
   - DOB djece (ako ima)
   - `quote` vraća tax
4) Confirm:
   - booking ide u `CONFIRMED`
   - email potvrde poslan
5) Confirmation:
   - prikazuje `CONFIRMED` + iznose

## Test 2 — Visoka sezona: kreiranje `PENDING_PAYMENT` + `orderCode`
1) Search datumi u visokoj sezoni  
2) Hold  
3) Checkout (quote obavezan)  
4) Confirm:
   - booking ide u `PENDING_PAYMENT`
   - backend vraća `order_code` (string) + `payment_url`
   - u bazi je spremljen `viva_order_code`

## Test 3 — Visoka sezona: uspješno plaćanje (happy path)
1) Otvori `payment_url` i završi plaćanje  
2) Viva šalje webhook  
3) Backend:
   - verifikacija webhooka OK
   - `PENDING_PAYMENT -> CONFIRMED`
   - spremi `viva_transaction_id`
   - pošalji email potvrde
4) Confirmation:
   - prikazuje `CONFIRMED`

## Test 4 — Visoka sezona: neuspješno plaćanje
1) Fail scenarij (demo)  
2) Očekuj:
   - booking ostaje `PENDING_PAYMENT` ili ide u `PAYMENT_FAILED` (kako odlučiš)
   - checkout nudi retry

## Test 5 — Timeout
1) Kreiraj `PENDING_PAYMENT` i ne plati  
2) Nakon `expires_at` (npr. 15 min):
   - booking ide u `EXPIRED`
   - availability se oslobađa

## Test 6 — Otkaz (visoka sezona) i fee%
1) Kreiraj CONFIRMED booking u visokoj sezoni  
2) Otkaz preko cancel flow:
   - 30+ dana prije → fee 0%
   - 8–29 dana prije → fee 50%
   - 0–7 dana prije → fee 90%
3) Fee se računa na `accommodation_total` (bez tax)

## Minimalni acceptance kriteriji
- `payment_required` ovisi o check-in mjesecu (6–9)
- `orderCode` je string i vezan uz booking
- samo webhook potvrđuje `CONFIRMED`
- email potvrde se šalje na `CONFIRMED`