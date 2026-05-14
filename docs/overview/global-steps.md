# Uzorita Rooms — globalni koraci (high level)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

Ovo je “mapa sustava”. Svaki korak ćemo kasnije razrađivati u zasebnim dokumentima.

## 1) Backend & infrastruktura
- Django backend u Dockeru na dedicated serveru
- PostgreSQL
- Django users + roles (Groups)

## 2) Booking.com (read-only MVP)
- sync soba
- sync rezervacija (create/update/cancel)
- audit sinkronizacije

## 3) Recepcija UI (mobile-friendly)
- lista dolazaka (danas + sutra)
- detalj rezervacije + timeline (Booking + recepcija)

## 4) Check-in
- wizard: prednja + zadnja osobne
- provjera kvalitete slike
- OCR → prikaz + ručna korekcija
- Confirm/Submit
- gosti: glavni + dodatni (dodavanje dodatnih preko istog wizarda)

## 5) eVisitor
- automatsko slanje nakon check-ina
- potvrda “poslano + primljeno”
- statusi + retry
- prikaz u timelineu + badge uz glavnog gosta

## 6) Check-out + plaćanje
- iznos povučen iz Bookinga + korekcije
- način plaćanja: Booking / gotovina / kartica (MVP)
- valuta: EUR (MVP)

## 7) Račun (R1)
- R1 podaci default iz glavnog gosta + mogućnost uređivanja
- automatsko numeriranje računa (MVP: 1 poslovni prostor / 1 uređaj)

## 8) Fiskalizacija (FINA)
- fiskalizacija → broj računa + ZKI + JIR
- automatski retry
- check-out moguć i bez fiskalizacije (račun može biti u retry/failed)

## 9) PDF računa
- PDF se generira odmah nakon izdavanja
- osvježi se kad fiskalizacija uspije (ZKI/JIR)

## 10) Admin/operativa
- Django admin za pregled: računi, fiskalizacija, eVisitor statusi

## 11) Kasnije (roadmap)
- write-back prema Bookingu (cijene/dostupnost)
- NFC naplata na mobitelu preko viva.com (Tap on Phone)
- više poslovnih prostora/uređaja
