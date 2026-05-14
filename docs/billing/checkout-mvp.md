# Check-out + naplata + R1 + fiskalizacija (MVP)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

## Cilj
Recepcija može završiti smještaj (check-out), evidentirati plaćanje i izdati R1 račun uz fiskalizaciju (FINA certifikat) i dobiti fiskalne identifikatore.

## Odakle dolazi iznos (MVP)
- Iznos se **povuče iz Bookinga** ako API daje cijenu/ukupno.
- Recepcija može napraviti **ručnu korekciju** (dodatne usluge, popust, razlika).

## R1 podaci (MVP)
- Default: preuzmi podatke **glavnog gosta** (iz check-ina)
- Recepcija može kliknuti **Uredi** i promijeniti podatke za račun (npr. naziv/ime, adresa, OIB)

## Kada se radi
- Na detalju rezervacije, kad gost odlazi: akcija **Check-out**.

## Flow (globalno)

### 1) Check-out ekran
Prikazati:
- rezervacija (soba, CI/CO, gosti)
- iznos (preuzet iz Bookinga) + korekcija
- status plaćanja (Booking / interno)

Akcija: **Nastavi na plaćanje**

### 2) Plaćanje
Opcije:
- **Plaćeno preko Bookinga** (označi kao plaćeno)
- **Gotovina**
- **Kartica**

Pravila:
- ako je “preko Bookinga” → `payment_status = PAID`
- ako gotovina/kartica → `payment_status = PAID` nakon potvrde recepcije

### 3) R1 račun
Recepcija unosi/odabire:
- podaci za račun (default glavni gost) + mogućnost uređivanja
- stavke (minimalno): opis + iznos (iz Bookinga + korekcije)

Akcija: **Izdaj račun**

### 4) Fiskalizacija
Sustav:
- fiskalizira račun preko FINA certifikata
- dobije i sprema:
  - **Broj računa**
  - **ZKI**
  - **JIR**

Rezultat:
- SUCCESS → račun “FISKALIZIRAN” + broj računa/ZKI/JIR
- FAIL → račun “NEFISKALIZIRAN” + poruka (omogućiti retry)

### 5) Završetak
- `reservation.ops_status` → **CHECKED_OUT**
- timeline event:
  - “Check-out napravljen”
  - “Plaćanje evidentirano”
  - “Račun izdan”
  - “Fiskalizirano (JIR …)” ili “Fiskalizacija FAILED”

## Statusi (sažeto)
- `payment_status`: UNPAID / PAID
- `invoice_status`: DRAFT / ISSUED / FISCALIZED / FAILED
- `reservation.ops_status`: CHECKED_IN → CHECKED_OUT

## UI (recepcija)
Na detalju rezervacije:
- badge: payment (PAID/UNPAID)
- badge: račun (FISCALIZED/FAILED)
- na računu prikazati: **broj računa, ZKI, JIR**
- timeline s događajima

## Napomena
Detalji formata fiskalizacije i komunikacije s FINOM rješavaju se tijekom kodiranja prema službenoj specifikaciji.
