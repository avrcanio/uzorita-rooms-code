# Recepcija (MVP) — globalni flow i odluke

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

## Cilj
Recepcija može:
- brzo pronaći rezervaciju
- napraviti check-in (sken osobne + OCR + potvrda)
- dodavati/uređivati goste na rezervaciji
- imati timeline događaja (Booking + recepcija)

## Ekrani

### 1) Lista dolazaka
- default: **Danas + Sutra**
- grupiranje: **Danas / Sutra**
- sortiranje unutar grupe: **po sobi**
- search: ime/prezime, broj rezervacije, soba

### 2) Detalj rezervacije
- prikaz: soba, datumi, statusi (Booking + operativni)
- sekcije:
  - Sažetak
  - **Gosti**
  - **Timeline**

Timeline prikazuje:
- Booking događaje (create/update/cancel)
- recepcija događaje (check-in, dodavanje/uređivanje/brisanje gostiju)

### 3) Check-in wizard (glavni gost)
Koraci:
1. Prednja strana osobne (slika + provjera kvalitete)
2. Zadnja strana osobne (slika + provjera kvalitete)
3. OCR + provjera (usporedi s fotkama, ručno ispravi sitno) + gumb **"Sve provjereno"**
4. Confirm/Submit (tek tada check-in vrijedi)

Nakon Confirm/Submit:
- povratak na **Detalj rezervacije**

## Gosti
- check-in wizard se radi za **glavnog gosta**
- dodatni gosti se dodaju po potrebi iz sekcije **Gosti**
- gumb **"Dodaj gosta"** postoji samo u sekciji **Gosti**
- "Dodaj gosta" otvara **isti wizard** (sken osobne)

Pravila:
- glavni gost: **Edit only** (nema delete)
- dodatni gosti: **Add/Edit/Delete**
- delete dodatnog gosta: **hard delete**, a timeline bilježi tko/kad (bez osobnih podataka obrisanog gosta)

## OCR polja (širi set)
- ime, prezime, spol, datum rođenja, državljanstvo
- tip dokumenta, broj dokumenta
- datum izdavanja, datum isteka
- izdavatelj (ako postoji), mjesto rođenja, adresa (ako postoji)
- OIB (ako je pouzdano; inače ručno)

## Autentikacija
- Django users + roles (Groups)
- login: **username + password**
- remember me: **30 dana**

## Povezivost
- internet je obavezan
- ako internet pukne usred wizarda:
  - slike se privremeno zadrže
  - upload se nastavlja **automatski** kad se veza vrati

## Pohrana slika osobne
- slike se spremaju na disk/object storage (ne u DB)
- struktura: **godina/mjesec/rezervacija**
- imena datoteka: **UUID**
- kod retake: stara slika se briše odmah (sync) i zamjenjuje novom
