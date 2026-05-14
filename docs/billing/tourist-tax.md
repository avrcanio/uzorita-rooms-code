# Boravišna pristojba — obračun (MVP)

**Last updated:** 2026-02-15  
**Status:** Draft

Ovaj dokument definira kako booking web prikazuje i računa boravišnu pristojbu (takse) na `/checkout`.

> Napomena: konkretna pravila i iznosi ovise o lokaciji i važećim propisima. Ovdje definiramo tehnički model i UX. Iznose/pragove treba unijeti kao konfiguraciju.

## Zašto računamo na checkoutu

- pristojba može ovisiti o dobi (djeca), sezoni i broju noćenja
- na `/search` i `/rooms/[slug]` prikazujemo **cijenu smještaja bez takse** + napomenu

## Podaci koje tražimo od korisnika

### Osnovno (obavezno)
- ime, prezime
- email, telefon

### Za obračun takse
- broj odraslih (već imamo)
- broj djece (već imamo)
- **datum rođenja za svako dijete** (obavezno ako je `children > 0`)

UX prijedlog:
- polja: `Datum rođenja djeteta 1`, `Datum rođenja djeteta 2`, ...
- validacija: DOB ne smije biti u budućnosti

## Koncept obračuna

Obračun je funkcija:
- `checkin`, `checkout` => `nights`
- `rooms[]` (jedna ili više soba) + alokacija odrasli/djeca po sobi
- `children_dobs[]`
- `ruleset` (konfiguracija po sezoni / razdoblju)

### Output
- `accommodation_total` (bez takse)
- `tourist_tax_total`
- `grand_total = accommodation_total + tourist_tax_total`

## API prijedlog

### 1) Preview obračuna (na checkoutu, prije confirm)
`POST /public/pricing/quote`

Request:
```json
{
  "checkin": "2026-07-12",
  "checkout": "2026-07-16",
  "rooms": [
    {"room_id": "triple", "adults": 2, "children": 2}
  ],
  "children_dobs": ["2019-05-10", "2021-09-02"]

}

Response:
Json
Copy code
{
  "currency": "EUR",
  "nights": 4,
  "accommodation_total": 420,
  "tourist_tax_total": 24,
  "grand_total": 444,
  "breakdown": {
    "tourist_tax": [
      {"type": "adult", "count": 2, "per_night": 1.5, "nights": 4, "total": 12},
      {"type": "child", "count": 2, "rule": "discount_50", "per_night": 1.5, "nights": 4, "total": 12}
    ]
  }
}
2) Confirm rezervacije
POST /public/bookings/confirm
Dodati u payload:
children_dobs[]
(opcionalno) quote_id ako želiš zaključati izračun
Konfiguracija pravila (ruleset)
Predloženi model konfiguracije (primjer, ne konkretni propisi):
adult_rate_per_night
child_rules (npr. 0–11 besplatno / 12–17 50% / ...)
season_ranges (datumski rasponi)
Vrijednosti držati u:
DB tablici tax_rules ili
config fajlu koji se može mijenjati bez deploya (admin UI kasnije)
UX na checkoutu
Prikaži "Smještaj" (bez takse)
Prikaži "Boravišna pristojba" s tooltipom (ovisno o dobi i noćenjima)
Prikaži "Ukupno" = smještaj + pristojba
Napomena: "Plaćanje po dolasku (gotovina/kartica)"
Edge cases
Ako korisnik ne unese DOB djece: onemogućiti potvrdu rezervacije
Ako DOB nije vjerodostojan: definirati politiku (blokirati ili tretirati kao odrasli)
Ako se pravila promijene: zaključati quote pri confirmu (preporuka)
Copy code

Commit message:  
`docs: add tourist tax calculation spec for checkout`

---

## Korak 2 — Sljedeće (UI na checkoutu)
Želiš li da checkout prikazuje:
1) jedan “glavni gost” + DOB djece (bez imenovanja djece)  
2) ime/prezime za svakog gosta + DOB djece (detaljnije, više trenja)

Napiši **1** ili **2**.0