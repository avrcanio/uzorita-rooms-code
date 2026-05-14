8# Hold snapshot API (booking web)

**Last updated:** 2026-02-16  
**Status:** Draft

Cilj: `GET /public/holds/{hold_token}` vraća snapshot potreban da `/checkout` može renderati bez dodatnih poziva (osim `quote` i eventualno `confirm`).

## Preduvjeti

- confirmation page radi polling na `GET /public/bookings/confirmation?code=...`


## Zašto snapshot
- checkout uvijek zahtijeva `hold`
- refresh mora zadržati isti hold
- frontend treba sve podatke za UI: sobe, datume, gosti, cijene (bez taksi), te kontrolu tajmera

## Endpoint
`GET /public/holds/{hold_token}`

### Response (ACTIVE)
```json
{
  "hold_status": "ACTIVE",
  "hold_expires_at": "2026-06-01T12:10:00Z",
  "checkin": "2026-07-12",
  "checkout": "2026-07-16",
  "nights": 4,
  "adults": 2,
  "children": 1,
  "rooms": [
    {
      "room_id": "dk",
      "room_slug": "deluxe-kingsize",
      "room_name": "Deluxe kingsize",
      "adults": 2,
      "children": 1,
      "pricing": {
        "currency": "EUR",
        "nights": 4,
        "accommodation_total": 420,
        "avg_per_night": 105,
        "taxes_excluded": true
      }
    }
  ],
  "pricing": {
    "currency": "EUR",
    "nights": 4,
    "accommodation_total": 420,
    "taxes_excluded": true,
    "tax_note": "Boravišna pristojba se obračunava na checkoutu."
  },
  "payment_policy": {
    "payment_required": true,
    "reason": "HIGH_SEASON",
    "high_season_months": [6, 7, 8, 9]
  }
}

Response (EXPIRED)
HTTP 410
Json
Copy code
{
  "hold_status": "EXPIRED",
  "message": "Hold je istekao. Molimo odaberite datume ponovno."
}
Response (CONSUMED)
Ako je hold već iskorišten u confirm, vrati booking snapshot:
Json
Copy code
{
  "hold_status": "CONSUMED",
  "booking": {
    "booking_code": "UZR-ABCDEFGH",
    "status": "PENDING_PAYMENT"
  }
}
Napomene
Snapshot cijene su bez boravišne pristojbe.
quote endpoint računa boravišnu pristojbu kad korisnik unese DOB djece.
confirm endpoint vraća hold_status + booking stanje (kako je dogovoreno).
hold_expires_at vraćati samo kad je hold_status=ACTIVE.


Korak 1 — Što točno dodaješ u snapshot response
U ACTIVE response dodaj objekt:
Json
Copy code
"combo": {
  "combo_id": "c1",
  "allocation": {
    "triple": { "adults": 2, "children": 2 },
    "d2a": { "adults": 2, "children": 0 },
    "dk": { "adults": 2, "children": 0 }
  }
}
I na razini rooms[] već imaš adults/children per room — to mora biti konzistentno s combo.allocation.
Korak 2 — Spremi/izmijeni dokument u repo
U backend/specs/hold-snapshot.md dopiši sekciju (ili zamijeni primjer) da eksplicitno kaže:
ako je hold nastao iz kombinacije → vraća combo.allocation
checkout ne računa ništa sam, samo rendera snapshot
Ako želiš, evo kratkog dodatka koji zalijepiš u “Napomene”:
Md
Copy code
- Ako je hold nastao iz kombinacije soba, `combo.allocation` je obavezan i predstavlja izvor istine za raspored gostiju po sobama.
- `rooms[].adults/children` mora odgovarati `combo.allocation`.


### 3) CONSUMED

Ako je hold već iskorišten u `confirm`, vratiti booking snapshot kako bi frontend mogao odmah redirectati.

- Ako je `booking.status=PENDING_PAYMENT`, vratiti i `payment` snapshot (za countdown + retry bez dodatnih poziva).

```json
{
  "hold_status": "CONSUMED",
  "booking": {
    "booking_code": "UZR-ABCDEFGH",
    "status": "PENDING_PAYMENT",
    "payment": {
      "required": true,
      "expires_at": "2026-06-01T12:15:00Z",
      "order_code": "1234567890123456",
      "payment_url": "https://www.vivapayments.com/web/checkout?ref=1234567890123456"
    }
  }
}