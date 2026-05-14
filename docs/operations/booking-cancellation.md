# Booking — otkaz rezervacije (public flow)

**Last updated:** 2026-02-15  
**Status:** Draft

Cilj: omogućiti gostu da otkaže rezervaciju s potvrde `/confirmation?code=UZR-XXXXXXXX`, ali bez izlaganja osobnih podataka i bez mogućnosti zlouporabe (netko tko slučajno sazna kod ne smije moći otkazati).

## UX (booking.uzorita.hr)

### 1) Confirmation stranica
- Prikaže se gumb **Otkaži rezervaciju**.
- Klik otvara modal:
  - polje: **Email** (mora odgovarati emailu na rezervaciji)
  - (opcionalno) checkbox: "Razumijem uvjete otkaza"
  - gumb: **Pošalji link za otkaz**

### 2) Email za otkaz
- Ako je email ispravan, sustav šalje email s jednokratnim linkom:
  - `https://booking.uzorita.hr/cancel?token=...`

### 3) Cancel stranica
- Prikazuje sažetak (bez osjetljivih podataka) + **Potvrdi otkaz**.

## Sigurnost

- Otkaz NE smije biti moguć samo s booking kodom.
- Otkaz je moguć samo preko **signed token** linka poslanog na email s rezervacije.
- Token je:
  - vezan na `booking_id`
  - ima `expires_at` (npr. 30 min)
  - single-use (nakon korištenja se invalidira)

## Pravila (policy)

- Otkaz je dozvoljen samo ako je rezervacija `CONFIRMED`.
- (MVP) Otkaz dopušten do `checkin` (ili do X dana prije) — definirati pravilo.
- Nakon otkaza:
  - status -> `CANCELLED`
  - osloboditi zauzeće (availability)
  - poslati email potvrde otkaza

## API prijedlog

### 1) Zatraži link za otkaz
`POST /public/bookings/cancel/request`

Request:
```json
{
  "booking_code": "UZR-ABCDEFGH",
  "email": "guest@example.com"
}
```

Response:
```json
{ "ok": true }
```

Napomena: uvijek vraćati `ok=true` (ne otkrivati postoji li booking / email) i rate limit po IP.

### 2) Dohvati podatke o otkazu (preview)
`GET /public/bookings/cancel/preview?token=...`

Response (public-safe):
```json
{
  "booking_code": "UZR-ABCDEFGH",
  "checkin": "2026-07-12",
  "checkout": "2026-07-16",
  "rooms": [{"room_name":"Deluxe kingsize"}],
  "cancellable": true,
  "policy_note": "Otkaz je moguć do dana dolaska.",
  "expires_at": "2026-02-15T12:30:00Z"
}
```

### 3) Potvrdi otkaz
`POST /public/bookings/cancel/confirm`

Request:
```json
{ "token": "..." }
```

Response:
```json
{ "status": "CANCELLED" }
```

## Email template (minimalno)

### Subject
- `Link za otkaz rezervacije – Uzorita (UZR-ABCDEFGH)`

### Body
- kratak tekst + link + expiry
- kontakt

## Rate limiting / anti-abuse

- `cancel/request`: npr. 5 zahtjeva / 10 min / IP
- `cancel/preview` i `cancel/confirm`: npr. 20 req / 10 min / IP

## Logika tokena (implementacijski hint)

Model/tablica `BookingCancelToken`:
- `booking` FK
- `token_hash`
- `expires_at`
- `used_at` (null dok nije iskorišten)
- `created_at`

Token u URL-u je random string, u bazi čuvati samo hash.
