# Uzorita Rooms — Brainstorming

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

## Cilj
Interna aplikacija za vođenje soba i gostiju u objektu Uzorita.

Primarni MVP:
- sinkronizacija rezervacija s Booking.com (sobe su već definirane na Bookingu)
- check-in: fotkanje osobne (mobitel) → spremanje u Django
- OCR osobne → izvlačenje podataka → slanje u eVisitor (HR)
- check-out: naplata (ako je Booking plaćeno → označi kao plaćeno; inače gotovina/kartica)
- izdavanje R1 računa na gosta + fiskalizacija (FINA certifikat) → JIR

## Glavni tokovi

### 1) Booking → Rezervacija u sustavu
- Booking kreira/izmijeni/otkaže rezervaciju
- Backend preuzima promjenu i sprema u bazu
- Rezervacija dobiva status: `OCEKUJE_DOLAZAK`

### 2) Check-in
- Recepcija otvori rezervaciju (ili kreira ručno)
- slika osobnu (kamera na mobitelu)
- OCR pročita podatke
- operater potvrdi/korigira podatke
- sustav šalje prijavu u eVisitor
- status: `PRIJAVLJEN` / `U_TOKU`

### 3) Check-out + račun
- recepcija odradi check-out
- plaćanje:
  - Booking: označiti `PLACENO`
  - inače: gotovina/kartica
- R1 račun na ime gosta
- fiskalizacija → JIR
- status: `ZAVRSENO`

## Entiteti (modeli)
- Room (soba)
- Reservation (rezervacija)
- Guest (gost)
- IDDocument (slika osobne + metapodaci)
- EvisitorSubmission (log slanja + rezultat)
- Invoice (račun)
- Fiscalization (podatci fiskalizacije + JIR)

## Integracije
- Booking.com (rezervacije + eventualno status plaćanja)
- OCR (odlučiti: server/cloud)
- eVisitor (odlučiti detalje autentikacije i minimalne podatke)
- Fiskalizacija (FINA certifikat; format prema specifikaciji)

## Must-have (sigurnost / GDPR)
- ograničiti pristup slikama osobnih (role-based)
- audit log tko je otvorio/izmijenio podatke
- politika čuvanja (retention) i brisanje
