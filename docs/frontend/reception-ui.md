# Recepcija UI — kratki runbook

**Last updated:** 2026-02-15
**Status:** Draft

Ovaj dokument pokriva osnovne ekrane recepcija UI-a na `rooms.uzorita.hr`.

## Login
- `/login`
- Nakon prijave ideš na početnu (`/`).

## Početna (`/`)
Sadržaj:
- “Današnji pregled” (select: danas / ovaj tjedan / ovaj mjesec / prikaži sve)
- Timeline rezervacija
  - filtriranje po statusu i search (gost/soba/external ID)
  - grupiranje po mjesecu i ISO tjednu (collapse/expand)
  - country flag uz ime gosta (ako je nationality ISO2 dostupna)

## Kalendar soba (`/calendar/rooms`)
- Month view po fizičkim sobama (`K1`, `K2`, `D1`, `T1`)
- Prev/Next mjesec + modal izbor mjeseca
- Klik na rezervaciju vodi na detalj rezervacije

## Detalj rezervacije (`/reservations/:id`)
- Lista gostiju
- Status i datumi
- Linkovi na detalj gosta

## Detalj gosta (`/reservations/:id/guests/:guestId`)
- Prikaz i uređivanje podataka gosta
- “Skeniraj dokument” vodi na scan ekran

## Scan (`/reservations/:id/guests/:guestId/scan`)
- Microblink scan dokumenta
- Nakon skena backend upisuje OCR polja u gosta + audit log

