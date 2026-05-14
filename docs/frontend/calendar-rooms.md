# Rooms calendar (`/calendar/rooms`) — usage

**Last updated:** 2026-02-15
**Status:** Active

URL:
- `https://rooms.uzorita.hr/calendar/rooms`

## Što ekran prikazuje
- Timeline zauzeća po fizičkim sobama (`K1`, `K2`, `D1`, `T1`) kroz odabrani mjesec.
- Svaka rezervacija je kartica koja vodi na detalj rezervacije.

## Navigacija
- `Previous` / `Next` mjesec: mijenja prikazani mjesec.
- Klik na naziv mjeseca: otvara modal sa listom svih mjeseci u godini za brzi skok.

## Filteri
- Filter soba (desktop): brzo sužavanje prikaza na jednu sobu.
- Mobile prikaz: timeline se fokusira na jedan “selection”, a možeš prebacivati sobe.

## Napomene
- Rezervacije sa statusom `canceled` se ne prikazuju u kalendaru.
- Dodjela soba:
  - Ako rezervacija nema dodijeljenu fizičku sobu (`room=null`), neće se pojaviti u kalendaru.

