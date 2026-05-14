# Uzorita Rooms — TODO & Milestones (procjena sati)

**Owner:** TBD
**Last updated:** 2026-02-15
**Status:** Active

Procjene su **grube** i odnose se na *programiranje*.

---

## M0 — Dokumentacija i odluke
**6 h**
- [x] M0 zavrsen

---

## M1 — Django backend + infrastruktura (Docker + Postgres + auth)
**40 h**

**Status update (2026-02-13):** Completed  
Core M1 baza je postavljena (Django bootstrap, docker setup, migracije, health endpoint, admin dostupnost na `rooms.uzorita.hr`).  
Detaljna specifikacija i runbook: `docs/backend/specs/m1-foundation.md`.

### Scope
- [x] Postaviti stabilnu backend bazu za daljnje milestone-e: Django app, lokalni Docker stack, Postgres, auth i osnovne role.

### Razrada (40 h)
- [x] `M1.1` Django bootstrap i struktura projekta — **6 h**
- [x] `M1.2` Konfiguracija preko env varijabli (dev-first) — **5 h**
- [x] `M1.3` Docker Compose setup (web + db) — **7 h**
- [x] `M1.4` Integracija sa postojecim host PostGIS-om (`127.0.0.1:5432`) + healthcheck — **4 h**
- [x] `M1.5` Base migracije i smoke model check — **4 h**
- [x] `M1.6` Admin user bootstrap (management command ili init skripta) — **3 h** (manualno odradjeno iz terminala)
- [x] `M1.7` Auth i roles (Django Groups + osnovne dozvole) — **7 h**
- [x] `M1.8` Dokumentacija runbook-a za lokalni start i troubleshooting — **4 h**

### Deliverables
- [x] Django projekat sa odvojenim settings slojem (`base/dev/prod` ili ekvivalent).
- [x] `.env.example` sa svim obaveznim varijablama.
- [x] `docker-compose.yml` koji podize app; baza je postojeci external host PostGIS.
- [x] Funkcionalan migration workflow (`makemigrations`, `migrate`).
- [x] Kreiran admin korisnik i definisane minimalne grupe: `reception`, `manager`, `admin`.
- [x] Kratki onboarding docs za pokretanje lokalnog okruzenja.

### Acceptance kriteriji
- [x] `docker compose up -d` podize servise bez greske.
- [x] App se otvara lokalno i uspostavlja vezu prema Postgres-u.
- [x] Migracije prolaze na cistoj bazi.
- [x] Admin login radi i korisnik moze dodeliti grupe.
- [x] Barem jedan endpoint/health URL vraca `200` za osnovni smoke test.

### Follow-up tasks (Django app structure)
- [x] `M1.F1` Kreirati Django app `reception` (`python manage.py startapp reception`).
- [x] `M1.F2` Dodati `reception` u `INSTALLED_APPS`.
- [x] `M1.F3` Napraviti `reception/urls.py` i povezati ga u root `config/urls.py`.
- [x] `M1.F4` Prebaciti reception-related logiku iz `config` u `reception` app gdje je primjenjivo.
- [x] `M1.F5` Definisati bazne modele za reception domen (placeholder za M3/M4): `Reservation`, `Guest`, `IDDocument`.
- [x] `M1.F6` Registrirati modele u Django admin (`reception/admin.py`) sa osnovnim list prikazom.
- [x] `M1.F7` Dodati permisije za `reception` modele u `bootstrap_roles` komandu.
- [x] `M1.F8` Kreirati i primijeniti inicijalne migracije za `reception` app.
- [x] `M1.F9` Ažurirati dokumentaciju (`docs/backend/specs/m1-foundation.md` + `docs/backend/decisions.md`) nakon izdvajanja app-a.

---

## M2 — Email/IMAP reservation ingestion (MVP)
**50 h**
- [ ] M2 zavrsen

### Napomena (2026-02-13)
- Booking.com trenutno pauzira onboardanje novih connectivity integracija.
- Do daljnjeg radimo ingest rezervacija preko mailbox-a `room_reservations@uzorita.hr` (IMAP + parser).
- Booking API sync ostaje planiran, ali je na cekanju dok Booking ne nastavi prihvacati nove integracije.

### Razrada (50 h)
- [x] `M2.1` Definisati `communications` app i modele (`InboundEmail`, `OutboundEmail`, `EmailAttachment`, `ParseError`) — **8 h**
- [x] `M2.2` Dodati IMAP konfiguraciju preko env varijabli (`IMAP_HOST`, `IMAP_PORT`, `IMAP_USER`, `IMAP_PASSWORD`, `IMAP_FOLDER`) — **3 h**
- [x] `M2.3` Implementirati IMAP ingest management komandu (fetch unread + Message-ID dedupe) — **10 h**
- [x] `M2.4` Parsirati Booking reservation email template (new/modify/cancel) u normalizirani payload — **10 h**
- [x] `M2.5` Mapirati parsed payload u `reception.Reservation` + `reception.Guest` (idempotent update) — **8 h**
- [x] `M2.6` Implementirati status workflow (`parsed`, `partial`, `failed`) + retry/reprocess mehanizam — **4 h**
- [ ] `M2.7` Dodati admin review queue za `partial/failed` emailove i ručnu korekciju — **5 h**
- [ ] `M2.8` Dodati audit log i osnovne metrike (broj processed/failed po run-u) — **2 h**
- [x] `M2.9` Periodic worker job: `run_booking_pipeline` (`fetch` + `process`) — **3 h**
- [x] `M2.10` Podrška za multi-room Booking rezervacije (više soba u jednom mailu) — **3 h**
- [x] `M2.11` Otkazivanje multi-room rezervacija (cancel sve `external_id` varijante) — **1 h**
- [x] `M2.12` Guest email + nationality ISO2 (best-effort mapping) — **2 h**

### Deliverables
- [x] `communications` Django app sa migracijama.
- [x] IMAP ingest komanda (`python manage.py fetch_booking_emails`) i parser servis.
- [x] Idempotentan upis rezervacija i gostiju iz emailova (uklj. multi-room).
- [ ] Admin ekran za pregled i ručnu obradu neuspješnih parser slučajeva (workflow).
- [x] Runbook dokumentacija za mailbox setup i operativni troubleshooting (`docs/operations/booking-ingest.md`, `docs/operations/reprocess-emails.md`).

### Acceptance kriteriji
- [x] Sustav povuče nove mailove iz `room_reservations@uzorita.hr` bez duplog upisa.
- [x] Za poznati Booking email template parser uspješno popuni ključna polja rezervacije.
- [x] Izmjena i otkaz rezervacije iz maila ažurira postojeći zapis (po external ID-u).
- [x] `partial/failed` slučajevi su vidljivi u adminu (filter `parse_status`).
- [ ] Postoji log svakog ingest run-a sa brojem obrađenih i neuspjelih poruka.

---

## M3 — Recepcija UI (PWA) + timeline
**70 h**
- [ ] M3 zavrsen

### Status update (2026-02-13)
- M3 je pokrenut.
- Frontend foundation i deploy su gotovi (`Next.js + Tailwind`, `rooms.uzorita.hr`).
- Backend API docs i schema su dostupni na istom hostu (`/api/docs/`, `/api/schema/`).
- Auth flow je implementiran (`/login`, `/api/auth/*`, protected rute).
- Timeline i detalj rezervacije su povezani na backend API (mobile tap -> novi detalj screen).

### Razrada (70 h)
- [x] `M3.1` Postaviti frontend app skeleton (routing, layout, API client, env config) — **10 h**
- [ ] `M3.2` PWA osnova (`manifest`, service worker, installability, icons) — **8 h**
- [x] `M3.3` Auth flow za recepciju (login/logout + protected routes) — **8 h**
- [x] `M3.4` Timeline ekran dolazaka/odlazaka (lista rezervacija po danu) — **12 h**
- [x] `M3.5` Filteri i pretraga (status + search: gost/soba/external ID) — **6 h**
- [x] `M3.6` Detalj rezervacije ekran (gosti, status, ključni podaci) — **8 h**
- [x] `M3.7` UX za mobilni rad na recepciji (responsive, touch-first, brze akcije) — **7 h**
- [x] `M3.8` Error/loading/empty states — **4 h**
- [x] `M3.9` Integracija sa backend endpointima za reservation timeline — **4 h** (foundation: API docs/schema + routing)
- [ ] `M3.10` QA i smoke test na desktop + mobilnim viewportima — **3 h**
- [x] `M3.11` Rooms calendar ekran: `/calendar/rooms` (month nav + modal izbor mjeseca) — **6 h**
- [x] `M3.12` Country flags u timeline karticama (flag-icons) — **1 h**

### Deliverables
- [ ] Frontend recepcija aplikacija sa PWA mogućnošću instalacije.
- [x] Timeline ekran koji prikazuje rezervacije i osnovne statuse.
- [x] Detalj rezervacije ekran povezan na backend podatke.
- [x] Auth za recepcijske korisnike i zaštita ruta.
- [x] Operativni UI states (loading/error/empty) spremni za produkcijski rad.
- [x] Rooms calendar ekran `/calendar/rooms`.
- [x] Dokumentacija za recepcija UI (kratki runbook) (`docs/frontend/reception-ui.md`, `docs/frontend/calendar-rooms.md`).

### Acceptance kriteriji
- [x] Korisnik se može prijaviti i odjaviti kroz recepcija UI.
- [x] Timeline prikazuje postojeće rezervacije (uključujući testni unos `TEST-RES-001`).
- [x] Klik na stavku timeline-a otvara detalj odgovarajuće rezervacije.
- [ ] Aplikacija je instalabilna kao PWA na mobilnom uređaju.
- [ ] Ključni tokovi rade na mobilnom viewportu bez layout lomljenja.

---

## M4 — OCR scan + guest update
**120 h**
- [ ] M4 zavrsen

### Status update (2026-02-13)
- Wizard je izbacen iz scope-a.
- Implementiran je odvojeni scan screen za gosta: `/reservations/[id]/guests/[guestId]/scan`.
- Integriran je Microblink Browser SDK i backend ingest na `/api/reception/reservations/{id}/guests/{guestId}/ocr/`.
- Uklonjen je PassportEye iz aktivnog flowa; provider je standardiziran na `microblink`.
- Guest model i API su prosireni za dodatna dokument/MRZ polja.
- M4 je funkcionalno zavrsen za OCR ingest flow; otvoren je samo formalni QA/runbook cleanup.

### Razrada (120 h)
- [x] `M4.1` Dodati odvojenu OCR scan rutu po gostu i mobile-friendly povratak na detalj gosta — **16 h**
- [x] `M4.2` Integrirati Microblink Browser SDK (kamera + automatsko skeniranje) — **20 h**
- [x] `M4.3` Uspostaviti backend OCR ingest endpoint i validaciju provider-a — **14 h**
- [x] `M4.4` Normalizirati OCR payload i mapirati polja u `Guest` model — **20 h**
- [x] `M4.5` Prosiriti `Guest` model, serializer i guest detail UI za dokument/MRZ polja — **18 h**
- [x] `M4.6` Dodati OCR audit (`OcrScanLog`, lista/statistika endpointi) — **10 h**
- [x] `M4.7` Ukloniti PassportEye iz aktivnog flowa i standardizirati na `microblink` — **6 h**
- [ ] `M4.8` Zavrsni QA smoke test (realni dokumenti + fallback unos) — **8 h**
- [ ] `M4.9` Runbook i operativna dokumentacija za OCR greske/licencu/resources — **8 h**

### M4 Foundation (zavrseno)
- [x] `M4.F1` Ukloniti inline OCR blok sa guest detail ekrana i ostaviti CTA `Skeniraj dokument`.
- [x] `M4.F2` Dodati odvojenu scan rutu `code/frontend/app/reservations/[id]/guests/[guestId]/scan/page.tsx`.
- [x] `M4.F3` Integrirati Microblink Browser SDK (`@microblink/blinkid`) i pokretanje kamere na scan ekranu.
- [x] `M4.F4` Dodati backend OCR ingest endpoint i zapis OCR loga (`OcrScanLog`).
- [x] `M4.F5` Normalizirati i mapirati OCR payload na `Guest` model (ime, dokument, OIB, datumi, country, MRZ).
- [x] `M4.F6` Prosiriti Guest detail formu i API serializer za nova OCR polja.

### Deliverables
- [x] OCR scan screen za gosta sa kamerom i Microblink SDK-om.
- [x] Backend ingest endpoint za OCR payload i auto-update gosta.
- [x] Prosirena guest forma za ručnu korekciju OCR podataka.
- [x] OCR audit log za svaki scan pokusaj.
- [ ] Operativna dokumentacija za OCR error handling i recepcija procedure (`docs/operations/ocr-runbook.md`).

### Acceptance kriteriji
- [x] Za barem jedan testni dokument OCR autopopuni ključna polja gosta.
- [x] Kad OCR ne uspije ili ne vrati sva polja, recepcija može ručno unijeti/korigirati podatke i spremiti.
- [x] OCR rezultat se zapisuje u audit log sa statusom i payload podacima.
- [ ] Tok je potvrden kroz zavrsni smoke test na mobilnom uređaju.

---

## M5 — eVisitor (auto send + potvrda primljeno)
**60 h**
- [ ] M5 zavrsen

---

## M6 — Check-out + račun (R1) + fiskalizacija + PDF
**145 h**
- [ ] M6 zavrsen
- [ ] iznos iz Bookinga + korekcije
- [ ] R1 default iz glavnog gosta + edit
- [ ] numeracija računa (1/1)
- [ ] fiskalizacija + auto retry + checkout bez fiskalizacije
- [ ] PDF odmah + osvjezi nakon fiskalizacije

---

## M7 — Admin & stabilizacija
**40 h**
- [ ] M7 zavrsen

---

## Total (M0–M7)
**491 h**

---

## Roadmap (kasnije) — nije u totalu
- [ ] viva.com Tap on Phone (NFC placanje)
- [ ] vise poslovnih prostora/uredaja
- [ ] Booking write-back (cijene/dostupnost)
