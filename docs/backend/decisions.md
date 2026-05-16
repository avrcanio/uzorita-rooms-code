# Backend Decisions

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

Dokument za tehničke odluke vezane uz backend.

## Zapisi odluka

### 2026-02-13 - Django settings su splitani (`base/dev/prod`)
- Odluka: koristiti `config/settings/base.py`, `config/settings/dev.py`, `config/settings/prod.py`.
- Razlog: cistije odvajanje dev/prod ponasanja i laksa env konfiguracija.

### 2026-02-13 - Baza je host Postgres/PostGIS na `127.0.0.1:5432`
- Odluka: Django servis koristi postojecu host bazu; ne podizemo dodatni DB u `code/backend`.
- Razlog: infrastruktura vec postoji i oznacena je kao healthy.

### 2026-02-13 - Django DB engine je `django.db.backends.postgresql`
- Odluka: za M1 koristiti PostgreSQL backend bez GIS backenda.
- Razlog: `django.contrib.gis.db.backends.postgis` u ovom image-u trazi GDAL/GEOS sistemske biblioteke.
- Napomena: prelazak na GIS backend ostaje opcija kasnije uz custom image.

### 2026-02-13 - Docker mreza za Django je `network_mode: host`
- Odluka: Django container radi u host mrezi.
- Razlog: host Postgres slusa na loopback adresi (`127.0.0.1`) i nije dostupan iz standardne Docker bridge mreze.

### 2026-02-13 - Admin branding i static assets
- Odluka: Django admin naziv je `Uzorita administracija`.
- Odluka: `logo.png` i `favicon.ico` se serviraju preko `/logo.png` i `/favicon.ico` redirectom na `/static/...`.

### 2026-02-13 - Public domena i TLS
- Odluka: `rooms.uzorita.hr` ide preko Traefik + Cloudflare proxied.
- Odluka: Traefik koristi ACME DNS challenge preko Cloudflare providera.
- Razlog: stabilan TLS iza Cloudflare proxya bez oslanjanja na HTTP challenge putanju.

### 2026-02-13 - CSRF trusted origin
- Odluka: dodan `DJANGO_CSRF_TRUSTED_ORIGINS=https://rooms.uzorita.hr`.
- Razlog: admin login kroz public host je vracao `403 Origin checking failed`.

### 2026-02-13 - Role bootstrap preko management komande
- Odluka: role baseline (`reception`, `manager`, `admin`) se postavlja kroz `python manage.py bootstrap_roles`.
- Razlog: idempotentno i ponovljivo inicijaliziranje grupa/permisija bez ručnog klikanja kroz admin.

### 2026-02-13 - Uveden zaseban `reception` Django app
- Odluka: reception domen (`Reservation`, `Guest`, `IDDocument`) je izdvojen u poseban app.
- Razlog: cistija modularnost, jasniji scope permisija i laksi nastavak M3/M4 razvoja.

### 2026-02-13 - Uveden `communications` app za mailbox ingest
- Odluka: IMAP/SMTP i email audit modeli su izdvojeni u `communications` app.
- Razlog: odvajanje komunikacijskog sloja od reception domene i laksa evolucija parser pipeline-a.

### 2026-02-13 - Lokalizacija aplikacije na Hrvatsku
- Odluka: `LANGUAGE_CODE=hr` i `TIME_ZONE=Europe/Zagreb`.
- Razlog: operativni korisnici su lokalni i UI treba biti na hrvatskom jeziku sa lokalnim vremenom.

### 2026-02-13 - Mail sync raspored preko cron-a (superseded)
- Odluka (MVP): umjesto Celery-ja koristili smo `run_booking_pipeline` petlju u `booking-worker`.
- Superseded: vidi 2026-05-16 — Celery + infra-redis.

### 2026-05-16 - Celery + shared infra-redis
- Odluka: booking email pipeline i iCal sync preko Celery workera/beat-a; broker `redis://infra-redis:6379/1`.
- Razlog: isti uzorak kao Mozart, pouzdaniji retry/raspored, bez host-mode petlje.
- Napomena: `run_booking_pipeline` ostaje za ručni `--once` debug.

### 2026-05-16 - Django na `hetzner_net` + `proxy` (bez host mode)
- Odluka: `uzorita-django` na `hetzner_net` (postgis, infra-redis, OCR) i `proxy` (Traefik labels).
- Razlog: `postgis` i `infra-redis` nisu na host loopbacku iz bridge mreže; Traefik gađa kontejner direktno.
- Env: `DB_HOST=postgis`, `PADDLE_OCR_BASE_URL=http://paddle-ocr-fastapi:8866`.

### 2026-02-13 - OCR provider je standardiziran na Microblink
- Odluka: aktivni OCR provider u backendu je samo `microblink`.
- Razlog: PassportEye je uklonjen iz aktivnog toka nakon nestabilnih rezultata na ciljanim dokumentima.

### 2026-02-13 - OCR ingest automatski popunjava prosirena Guest polja
- Odluka: `ReservationGuestOcrView` normalizira payload i upisuje prepoznata dokument/MRZ polja direktno u `Guest`.
- Razlog: recepcija dobiva odmah popunjen form i manje ručnog unosa.
- Posljedica: `Guest` model je prosiren (npr. OIB/personal ID, issuing authority, issue/expiry, country metadata, `mrz_raw_text`, `mrz_verified`).

### 2026-02-13 - OCR audit ostaje obavezan kroz OcrScanLog
- Odluka: svaki OCR pokušaj se zapisuje u `OcrScanLog` sa `raw_payload`, statusom i trajanjem.
- Razlog: treba postojati audit i osnova za kasniju evaluaciju kvalitete OCR-a.
