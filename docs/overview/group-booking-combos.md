# Group booking — kombinacije soba (multi-room)

**Last updated:** 2026-02-15  
**Status:** Draft

Opisuje kako booking web slaže ponudu (kombinacije soba) kad gosti ne stanu u jednu sobu.

## Pravila kapaciteta (sažetak)

- Sve sobe osim trokrevetne: **max 2 osobe ukupno** (djeca ne povećavaju kapacitet)
- Trokrevetna:
  - default **max 3 ukupno**
  - iznimka: **točno 2 odrasla + 2 djece => max 4 ukupno**

## UI zahtjev


2) Kalendar dostupnosti za pojedinu sobu
GET /public/rooms/{room_id}/calendar?month=YYYY-MM
Primjer:
Json
Copy code
{
  "room_id": "d2b",
  "month": "2026-07",
  "days": {
    "2026-07-01": "available",
    "2026-07-02": "unavailable"
  }
}
3) Hold (anti-overbooking)
Kad korisnik odabere sobu ili kombinaciju, napravi se privremeni hold (npr. 10–15 min).
POST /public/holds
Json
Copy code
{
  "checkin": "2026-07-12",
  "checkout": "2026-07-16",
  "rooms": [
    {"room_id":"triple","adults":2,"children":2},
    {"room_id":"d2a","adults":2,"children":0},
    {"room_id":"dk","adults":2,"children":0}
  ]
}
Response:
Json
Copy code
{ "hold_token": "HOLD_xxx", "expires_at": "2026-07-01T10:15:00Z" }
4) Confirm rezervacije (pay on arrival)
POST /public/bookings/confirm
Json
Copy code
{
  "hold_token": "HOLD_xxx",
  "guest": { "first_name":"...", "last_name":"...", "email":"...", "phone":"..." },
  "payment_method": "PAY_ON_ARRIVAL_CARD"
}
Algoritam kombinacija (MVP)
Zbog malog inventara (5 soba) možeš brute-force:
Generirati sve podskupove soba (1..5)
Zadržati samo one gdje su sve sobe dostupne u periodu
Provjeriti može li kombinacija smjestiti (adults, children) uz pravila
Rangirati:
manje soba bolje
manje praznih mjesta bolje
(opcionalno) niža cijena bolje
Vratiti top 1–3 kombinacije
Posebno pravilo trokrevetne u alokaciji
Ako kombinacija sadrži trokrevetnu i imamo barem 2 odrasla i 2 djece:
prvo pokušaj alocirati 2+2 u trokrevetnu (kapacitet 4) da smanjiš broj soba.
Copy code

---

## Korak 2 — Uredi jedan postojeći fajl (Microblink detalj)
U `frontend/specs/m4-checkin-ocr-flow.md` dodaj ovu sekciju (npr. odmah nakon “API integracija”):

```md
## Microblink (BlinkID) — detalji
- Scan/OCR se izvršava na klijentu (kamera na uređaju).
- Frontend šalje backendu:
  - `provider: "microblink"`
  - `raw_payload` (originalni output SDK-a za audit/debug)
  - `suggested_fields` (normalizirana polja koja UI koristi)
  - `duration_ms`
- Privatnost:
  - ne spremati slike osobnih u frontend storage
  - backend mora ograničiti pristup `raw_payload` + definirati retention
Korak 3 — Predložene commit poruke
docs: add field schema for document extraction
docs: add booking room capacity rules
docs: add multi-room combos + availability/hold API spec
docs: expand microblink section in frontend OCR spec
Kad ovo commitaš, reci mi ići ćemo dalje: složimo točan UI layout za /search (5 soba + zasjenjene + modal kalendar) i /checkout (multi-room).
- Nakon unosa datuma i broja gostiju prikazati **svih 5 soba**.
- Nedostupne sobe prikazati **zasjenjeno**.
- Klik na nedostupnu sobu otvara **kalendar dostupnosti** te sobe.
- Iznad liste soba prikazati **1–3 preporučene kombinacije** (kad treba).
- Checkout mora podržavati **rezervaciju više soba odjednom**.

## API prijedlog (MVP)

### 1) Dostupnost + preporučene kombinacije
`GET /public/availability?checkin=YYYY-MM-DD&checkout=YYYY-MM-DD&adults=6&children=2`

Backend vraća:
- `rooms[]`: svih 5 soba sa `available=true/false`
- `combos[]`: 0–3 preporučene kombinacije (ako treba)

Primjer (skraćeno):
```json
{
  "checkin": "2026-07-12",
  "checkout": "2026-07-16",
  "adults": 6,
  "children": 2,
  "rooms": [
    {"room_id":"triple","name":"Deluxe trokrevetna","available":true},
    {"room_id":"d2a","name":"Deluxe dvokrevetna 1","available":true},
    {"room_id":"d2b","name":"Deluxe dvokrevetna 2","available":false},
    {"room_id":"dk","name":"Deluxe kingsize","available":true},
    {"room_id":"sk","name":"Standard kingsize","available":true}
  ],
  "combos": [
    {
      "combo_id": "c1",
      "rooms": ["triple","d2a","dk"],
      "allocation": {
        "triple": {"adults": 2, "children": 2},
        "d2a": {"adults": 2, "children": 0},
        "dk": {"adults": 2, "children": 0}
      }
    }
  ]
}