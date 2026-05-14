# Račun — PDF generiranje (MVP)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

## Odluka
Nakon izdavanja računa sustav **automatski generira PDF**.

## Kada je PDF dostupan
- **odmah nakon “Izdaj račun”** (može biti bez JIR-a ako fiskalizacija još nije uspjela)
- kad fiskalizacija kasnije uspije (retry), PDF se **osvježi** (finalni PDF s brojem računa + ZKI + JIR)

## Što PDF mora sadržavati (minimalno)
- podaci izdavatelja (Uzorita / tvrtka/obrt)
- podaci kupca (R1): naziv/ime, adresa, OIB (ako uneseno)
- broj računa (kad je poznat)
- datum i vrijeme izdavanja
- stavke (opis + iznos) i ukupno
- način plaćanja (Booking / gotovina / kartica)
- fiskalni podaci: **ZKI** i **JIR** (kad su dostupni)

## UI
- na računu: gumb **Preuzmi PDF**
- opcija **Ispis** preko uređaja

## Pohrana
- PDF spremiti na server (storage) i u bazi čuvati putanju + metapodatke
- pristup PDF-u samo prijavljenim korisnicima s odgovarajućom rolom
