# Viva.com — Smart Checkout (JS widget) integracija

**Last updated:** 2026-02-16  
**Status:** Draft

Ovaj dokument opisuje MVP integraciju za **Viva.com Smart Checkout** (embedded JS) za `booking.uzorita.hr`.

> Napomena: nazivi polja/URL-ova ovise o Viva konfiguraciji. Ovo je tehnički blueprint (flow, statusi, gdje što ide) da implementacija bude sigurna i deterministična.

## Kada je online plaćanje obavezno
- Ako je `checkin` u mjesecima **6–9** (visoka sezona) => `payment_required=true`
- Niska sezona => plaćanje po dolasku, bez online naplate

## Što se naplaćuje online (MVP)
- Naplaćuje se **cijena smještaja** (`accommodation_total`)
- Boravišna pristojba se i dalje računa i prikazuje na checkoutu, ali se naplaćuje po dolasku

## Statusi
- `HOLD` (10–15 min)
- `PENDING_PAYMENT` (booking kreiran, čeka naplatu)
- `CONFIRMED` (plaćeno i potvrđeno)
- `PAYMENT_FAILED` (neuspjelo plaćanje)
- `EXPIRED` (istekao payment window)
- `CANCELLED`

## Endpoints (MVP)

### 1) Kreiraj booking + vrati payment init podatke (visoka sezona)
`POST /public/bookings/confirm`

- niska sezona: vraća `CONFIRMED` + `booking_code`
- visoka sezona: kreira booking `PENDING_PAYMENT` + vraća payment init data za Smart Checkout

Predloženi response za visoku sezonu:
```json
{
  "status": "PENDING_PAYMENT",
  "booking_code": "UZR-ABCDEFGH",
  "payment_required": true,
  "payment": {
    "provider": "viva",
    "amount": 42000,
    "currency": "EUR",
    "order_code": "...",
    "merchant_ref": "UZR-ABCDEFGH",
    "success_url": "https://booking.uzorita.hr/confirmation?code=UZR-ABCDEFGH",
    "fail_url": "https://booking.uzorita.hr/checkout?hold=HOLD_xxx&payment=failed"
  }
}

amount je u centima (preporuka). order_code/transaction_id ovisi o Viva API-ju.
2) Webhook za potvrdu plaćanja (source of truth)
POST /webhooks/payments/viva
verifikacija potpisa (HMAC/secret)
mapiranje eventa na booking (preko merchant_ref ili order_code)
Logika:
ako je plaćanje success => PENDING_PAYMENT -> CONFIRMED + poslati email potvrde
ako je failed => PAYMENT_FAILED (ili ostaviti PENDING_PAYMENT i dopustiti retry)
3) Polling endpoint (opcionalno)
Ako želiš da frontend može provjeriti status nakon callbacka: GET /public/bookings/payment-status?code=UZR-ABCDEFGH
Frontend (Next.js) — Smart Checkout widget
Na /checkout:
korisnik popuni podatke + DOB djece
zove POST /public/pricing/quote (za taksu)
zove POST /public/bookings/confirm
ako payment_required=true:
prikaži Smart Checkout kartični widget
inicijaliziraj ga s order_code (ili tokenom) iz backend-a
na client success callback prikaži "Plaćanje u obradi" i redirect na /confirmation?code=...
Ne vjerovati samo client callbacku: webhook finalno potvrđuje.
Timeouts
HOLD vrijedi 10–15 min
PENDING_PAYMENT treba imati expires_at (npr. 15 min)
cron job: PENDING_PAYMENT stariji od expires_at => EXPIRED + osloboditi availability
Refund (otkaz u visokoj sezoni)
fee% se računa po billing/cancellation-policy.md
refund = plaćeno - fee
(MVP) refund ručno ili kroz Viva refund API (kasnije)
Sigurnosne smjernice
kartični podaci ne smiju ići kroz backend
webhook endpoint mora imati:
signature verification
rate limit
idempotency (isti event ne smije duplo potvrditi)
TODO (za dopunu kad uzmeš Viva parametre)
točan naziv order_code / transaction_id polja
točan format potpisa i headeri za webhook
minimalni set Viva JS init parametara
