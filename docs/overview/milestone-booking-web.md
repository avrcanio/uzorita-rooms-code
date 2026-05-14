# Milestone: Booking web (booking.uzorita.hr)

**Status:** In progress  
**Last updated:** 2026-02-16

Cilj: public booking web u Next.js, s dostupnošću, multi-room combo ponudama, checkoutom, boravišnom pristojbom, **postpaid plaćanjem po dolasku** i **free cancellation** (Viva kasnije).

---

## 0) Setup / infrastruktura

- [x] DNS: kreirati `booking.uzorita.hr`
  - [x] Cloudflare record je **Proxied** (verified `2026-02-16`)
- [ ] Deploy okruženje (staging + prod)
  - [x] Booking web dignut kao Docker servis iza Traefik-a (router `booking.uzorita.hr`), verified `2026-02-16`
- [ ] SSL certifikat
  - [x] HTTPS radi kroz Cloudflare proxy, verified `2026-02-16`
- [ ] Basic monitoring/logging (min: error tracking + request logs)

## 1) Public web (Next.js)

- [x] Repo scaffold: `code/booking` (Next.js + Tailwind + docker-compose + osnovni routing)
  - [x] Docker image/service: `uzorita-booking-web` (Traefik labels, `proxy` network)
  - [x] Helper skripta za Cloudflare DNS upsert: `code/ops/cloudflare_dns.py`

### Stranice i routing
- [x] `/` (hero search-first)
- [x] `/search` (grid 2×2 desktop, 1× mobile)
- [x] `/rooms/[slug]` (SEO + availability widget + 2-mjesečni kalendar)
- [x] `/checkout?hold=...` (checkout samo s hold tokenom)
- [x] `/confirmation?code=...` (public-safe prikaz)

### SEO
- [x] Dynamic metadata (title/description/OG) za `/rooms/[slug]`
- [x] Schema.org (Room/Accommodation)
- [x] Sitemap (barem rooms)
- [x] Robots.txt

### UI detalji
- [x] Sobe prikazati i kad nisu dostupne (zasjenjeno)
- [ ] Klik na nedostupnu sobu: modal s kalendarom dostupnosti
- [x] Preporučene kombinacije (combo) za veće grupe

### Kalendar (UX poboljšanje - fluidnost)
- [ ] Navigacija mjeseci (next/previous) bez full page reload-a
- [ ] Ukloniti scroll-to-top efekt kod promjene mjeseca
- [ ] Next/Prev prebaciti na client-side state (button, fetch, bez promjene rute)
- [ ] Ako se ipak koristi router.replace/query, koristiti `{ scroll: false }`
- [ ] Loading state (skeleton) kod promjene mjeseca
- [ ] Cacheirati 2 mjeseca unaprijed radi bržeg prebacivanja

### Implementirano (update 2026-02-16)
- [x] Branding i jezik (hr/en)
- [x] Home (`/`) koristi `GET /api/public/property/`
- [x] Search (`/search`) koristi `GET /api/public/availability/` + combos
- [x] Room detalj (`/rooms/[slug]`) koristi `GET /api/public/rooms/{room_id}/calendar/?month=YYYY-MM`

## 2) Availability + combos (backend)

- [x] `GET /api/public/availability/?checkin&checkout&adults&children`
  - [x] vraća sve aktivne sobe s `available=true/false`
  - [x] vraća `pricing.accommodation_total` (bez boravišne)
  - [x] vraća `combos[]` (1–3 preporuke) s `allocation`
- [x] `GET /api/public/rooms/{room_id}/calendar/?month=YYYY-MM`

## 3) HOLD (anti-overbooking)

- [ ] `POST /public/holds` (10 min)
- [ ] `GET /public/holds/{hold_token}` snapshot
  - [ ] vraća `combo.allocation` ako postoji
  - [ ] kad je CONSUMED vraća `booking_code`
- [ ] Job: expire holds (10 min) → oslobodi availability

## 4) Checkout + quote (boravišna pristojba)

- [ ] Checkout forma: glavni gost (ime, prezime, email, telefon)
- [ ] DOB za svako dijete (obavezno ako children > 0)
- [ ] `POST /public/pricing/quote` (računa boravišnu)
- [ ] Prikaz cijena:
  - [ ] Smještaj (bez takse)
  - [ ] Boravišna
  - [ ] Ukupno
- [ ] Plaćanje na checkoutu (MVP):
  - [ ] izbor: kartica po dolasku / gotovina po dolasku

## 5) Booking confirm (MVP = always CONFIRMED)

- [ ] `POST /public/bookings/confirm` (idempotentno po hold_token)
  - [ ] vraća `hold_status`
  - [ ] uvijek kreira `CONFIRMED` (postpaid)
- [ ] Booking code `UZR-XXXXXXXX` (unique)

## MVP politika: postpaid + free cancellation

- [x] Pravilo plaćanja: kartica/gotovina po dolasku (nema online plaćanja)
- [x] Politika otkaza: 0% fee, otkaz bilo kada

## 7) Email

- [ ] Email potvrde na CONFIRMED (SMTP već postoji)
- [ ] Email otkaza (opcionalno)

## 8) Cancellation (public)

- [ ] `POST /public/bookings/cancel/request` (email link)
- [ ] `GET /public/bookings/cancel/preview?token=...` (uvijek fee 0%)
- [ ] `POST /public/bookings/cancel/confirm`

## 9) Smoke testovi (MVP)

- [ ] Postpaid: confirm → `CONFIRMED` + email
- [ ] Hold timeout: hold → `EXPIRED` + availability free
- [ ] Cancel: free cancellation (fee 0%)

---

## Definition of Done

- [ ] End-to-end flow radi (search → room → hold → checkout → confirm → email)
- [ ] Nema overbookinga (hold)
- [ ] SEO stranice soba indexable
- [ ] Email potvrde stiže