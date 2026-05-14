# Uzorita Rooms - Product Roadmap

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

Kljucne faze razvoja proizvoda od MVP-a do write-back integracija.

## Faza 1 (MVP) - read-only sync (Booking -> Django)
Cilj: lokalni backend ima tocan prikaz soba i rezervacija sa Bookinga.

### Ukljuceno
- polling svakih 30 min + "Sync now"
- spremanje soba (read-only)
- spremanje rezervacija (create/update/cancel)
- log sinkronizacije (audit)

### Nije ukljuceno (jos)
- slanje promjena natrag u Booking (cijene, dostupnost, sadrzaj)
- channel manager

## Faza 2 - check-in + eVisitor
- slika osobne -> OCR -> potvrda -> slanje u eVisitor

## Faza 3 - check-out + racun + fiskalizacija
- R1 racun + fiskalizacija (FINA) -> JIR

## Faza 4 - upravljanje cijenama i dostupnoscu (write prema Bookingu)
- cijene, availability, pravila
