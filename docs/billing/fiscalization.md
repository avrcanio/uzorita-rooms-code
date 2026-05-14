# Fiskalizacija — globalno (MVP)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

## Cilj
Račun se fiskalizira (FINA certifikat) i dobiva:
- **Broj računa**
- **ZKI**
- **JIR**

## Ključne odluke (MVP)
- Fiskalizacija se pokreće automatski nakon izdavanja računa.
- Ako fiskalizacija ne uspije, sustav radi **automatski retry**.
- **Check-out je moguć i ako fiskalizacija još nije uspjela** (račun može biti u statusu retry/failed).

## Statusi
- `FISCALIZED` (uspješno, imamo broj računa + ZKI + JIR)
- `FAILED` (nije uspjelo, retry radi ili čeka)

## UI (recepcija)
- Na detalju rezervacije i/ili računu jasno prikazati:
  - `FISCALIZED` + broj računa + ZKI + JIR
  - ili `FAILED/RETRYING` (s porukom da sustav pokušava ponovno)
- Rezervacija može biti `CHECKED_OUT` i dok je račun `FAILED/RETRYING`.

## Timeline
- “Račun izdan”
- “Fiskalizacija pokušaj #n”
- “Fiskalizirano” (JIR/ZKI/broj računa)
- “Fiskalizacija FAILED” (ako je trajna greška)

## Napomena
Interval i maksimalni broj pokušaja definiraju se u implementaciji.
