# Booking — Room rules & capacity

**Last updated:** 2026-02-15  
**Status:** Draft

Ovaj dokument definira kapacitete soba i posebno pravilo za trokrevetnu sobu, kako bi booking web (booking.uzorita.hr) mogao složiti ponudu soba za zadani broj odraslih i djece.

## Inventar

- 1× **Deluxe trokrevetna**
- 2× **Deluxe dvokrevetna**
- 1× **Deluxe kingsize**
- 1× **Standard kingsize**

Ukupno: 5 soba.

## Opće pravilo (za sve sobe osim trokrevetne)

- Maksimalno **2 osobe ukupno** po sobi (bez obzira jesu li djeca ili odrasli).
- Djeca su dopuštena, ali ne povećavaju kapacitet.

Primjeri dozvoljenih kombinacija (uvijek max 2 ukupno):
- 2 odrasla, 0 djece
- 1 odrasli, 1 dijete
- 0 odraslih, 2 djece

## Posebno pravilo — Deluxe trokrevetna

Osnovno:
- Maksimalno **3 osobe ukupno** (npr. 3 odrasla ili 2 odrasla + 1 dijete).

Iznimka (bonus kapacitet):
- Ako je kombinacija **točno 2 odrasla + 2 djece**, tada trokrevetna može primiti **4 osobe ukupno**.

Jedini slučaj gdje se prelazi 3 osobe:
- ✅ (adults=2, children=2)

## UI zahtjevi

- Nakon unosa datuma prikazati **svih 5 soba**.
- Nedostupne sobe prikazati **zasjenjeno**.
- Klik na nedostupnu sobu otvara **kalendar dostupnosti** te sobe.