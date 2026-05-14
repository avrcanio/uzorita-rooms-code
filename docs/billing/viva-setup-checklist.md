# Viva.com — setup checklist (MVP)

**Last updated:** 2026-02-16  
**Status:** Draft

Cilj:
- Visoka sezona (check-in 6–9): obavezno online plaćanje (kad Viva bude spremna).
- Niska sezona: plaćanje po dolasku.

## Checklist
1) Odaberi okruženje: demo prvo, zatim prod  
2) Kreiraj Payment Source za web i zapiši `sourceCode` (4 znamenke)  
3) Pripremi API credse (merchant/account + API key / client credentials)  
4) Definiraj success/fail URL-ove  
5) Postavi webhook endpoint `POST /webhooks/payments/viva`  
6) Test: success / fail / timeout / cancel+refund (visoka sezona)  
7) Produkcija: prebaci credse + ponovi test

Napomene:
- `orderCode` tretirati kao string
- booking u visokoj sezoni postaje CONFIRMED tek nakon webhooka

# Viva.com — setup checklist (MVP)

Cilj:
- Visoka sezona (check-in 6–9): obavezno online plaćanje (kad Viva bude spremna).
- Niska sezona: plaćanje po dolasku.

Checklist:
1) demo → prod
2) Payment Source + `sourceCode`
3) API credsi
4) success/fail URL-ovi
5) webhook `POST /webhooks/payments/viva`
6) test success/fail/timeout/cancel+refund
7) prod smoke test

Napomene:
- `orderCode` kao string
- `PENDING_PAYMENT -> CONFIRMED` samo preko webhooka