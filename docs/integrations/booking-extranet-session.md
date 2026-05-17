# Booking.com extranet — session i login

**Last updated:** 2026-05-17  
**Status:** Faza A + **Faza B (noVNC)** — CAPTCHA u iframeu na recepciji

## CAPTCHA i SMS

Booking nakon više automatskih pokušaja traži **SMS** i **CAPTCHA** (uključujući AWS WAF „Human Verification”). Headless Playwright to ne rješava pouzdano.

**Primarni put (Faza B):** kad je `BOOKING_EXTRANET_VNC_ENABLED=true` i `BOOKING_EXTRANET_HEADED=true`, worker `celery-booking-browser` pokreće headed Chromium na `DISPLAY=:99`. Recepcija na **Postavke → Booking** vidi **noVNC iframe**, riješi CAPTCHA, klikne **Nastavi**; isti browser context nastavlja connect / health / dohvat rezervacije.

**Rezervni put:** RustDesk na bridge laptop → ručna prijava → uvezite `storage_state` (JSON upload u UI ili `import-state` API).

Automatski connect (`BOOKING_EXTRANET_CONNECT_MODE=automatic`) i dalje radi max **1×/24h** na workeru; CAPTCHA → `needs_human` + VNC token (TTL iz `BOOKING_EXTRANET_VNC_TOKEN_TTL_SECONDS`).

## RustDesk (već na serveru)

Stack: `/opt/stacks/rustdesk` — `rustdesk-hbbs`, `rustdesk-hbbr`, Tailnet `rustdesk-tail`.  
Nije remote desktop sam po sebi. **Bridge:** admin laptop (RustDesk klijent na `rustdesk-tail`) — ručna prijava kad sesija istekne.

### Operativni koraci (human-assisted)

1. Recepcija → [/settings/booking](https://rooms.uzorita.hr/settings/booking) ili banner na `/import`
2. RustDesk → admin laptop
3. Na laptopu: Booking login URL iz `BOOKING_EXTRANET_LOGIN_URL` (`.env`)
4. Ručno: CAPTCHA + SMS u Chrome/Edge
5. Export Playwright `storage_state.json` s bridgea (headed browser) ili DevTools — vidi dolje
6. U recepciji: **Spremi sesiju** (upload JSON) ili na serveru:

```bash
python manage.py upload_booking_storage_state /path/to/storage_state.json
```

7. **Provjeri sesiju** u UI (headless health check, bez novog logina)

### Export state na bridge PC (jednokratno)

```bash
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=False)
    ctx = b.new_context()
    page = ctx.new_page()
    input('Prijavite se u browseru, zatim Enter...')
    ctx.storage_state(path='storage_state.json')
    b.close()
"
```

## Svrha

Održavati **valjanu prijavu** na Booking.com extranet (`admin.booking.com`) iz recepcijskog UI-a, spremiti sesiju (cookies + localStorage) na serveru i obavijestiti kad istekne.

**Faza A ne zamjenjuje:** XLS import, email ingest, iCal.

## Statusi veze

| Status | Značenje | Akcija u UI |
|--------|----------|-------------|
| `disconnected` | Nema spremljene sesije | RustDesk + uvezi sesiju |
| `connecting` | Playwright radi login | Pričekaj / poll |
| `needs_2fa` | Treba SMS kod | Unesi kod ili RustDesk |
| `needs_human` | CAPTCHA / WAF | noVNC iframe + **Nastavi**, ili RustDesk → uvezi sesiju |
| `connected` | Sesija valjana | — |
| `expired` | Health check našao login | Ponovno uvezi sesiju |
| `error` | Neočekivana greška | Pogledaj poruku |

## Konfiguracija

Varijable u `backend/.env`:

```bash
BOOKING_EXTRANET_ENABLED=true
BOOKING_EXTRANET_CONNECT_MODE=human_assisted
BOOKING_EXTRANET_USERNAME=...
BOOKING_EXTRANET_PASSWORD=...
BOOKING_EXTRANET_HOTEL_ID=4181954
BOOKING_EXTRANET_LOGIN_URL=https://account.booking.com/sign-in?op_token=...
BOOKING_EXTRANET_STORAGE_DIR=/data/booking_browser
BOOKING_EXTRANET_FERNET_KEY=<Fernet ključ>
BOOKING_EXTRANET_AUTO_CONNECT_MIN_HOURS=24
BOOKING_EXTRANET_VNC_ENABLED=true
BOOKING_EXTRANET_VNC_PUBLIC_PATH=/booking-vnc
BOOKING_EXTRANET_VNC_TOKEN_TTL_SECONDS=1200
BOOKING_EXTRANET_HEADED=true
```

`op_token` u LOGIN_URL može isteći — generiraj novi iz extraneta (Manage → Reservations).

Traefik: `PathPrefix(/booking-vnc)` → websockify:6080 na `celery-booking-browser`, **ForwardAuth** → `GET /api/reception/booking-extranet/vnc/auth/?token=...` (Django session + Redis token).

## API

| Endpoint | Opis |
|----------|------|
| `GET /api/reception/booking-extranet/connection/` | Status za UI (`vnc_url`, `vnc_active`, `active_job_id`) |
| `POST /api/reception/booking-extranet/connection/start/` | Auto connect (samo `CONNECT_MODE=automatic`, rate limit) |
| `GET /api/reception/booking-extranet/connection/start/<task_id>/` | Poll |
| `POST /api/reception/booking-extranet/connection/verify-2fa/` | `{ "code": "..." }` |
| `POST /api/reception/booking-extranet/connection/import-state/` | Upload `storage_state` JSON ili file |
| `POST /api/reception/booking-extranet/connection/disconnect/` | Obriši sesiju |
| `POST /api/reception/booking-extranet/connection/check/` | Ručni health check |
| `GET /api/reception/booking-extranet/connection/check/<task_id>/` | Poll health check |
| `GET /api/reception/booking-extranet/vnc/auth/` | Traefik ForwardAuth (session + `token` query) |
| `POST /api/reception/booking-extranet/vnc/continue/` | Operator signal nakon CAPTCHA |
| `POST /api/reception/booking-extranet/fetch-reservation/` | `{ inbound_email_id }` ili `{ booking_number }` |
| `GET /api/reception/booking-extranet/fetch-reservation/<task_id>/` | Poll dohvata |

Auth: `IsAuthenticated` + CSRF za POST.

## Frontend

- Stranica: `/settings/booking`
- Banner na `/import` kad je extranet omogućen

## Docker

Servis `celery-booking-browser`:

- Image: `mcr.microsoft.com/playwright/python`
- Queue: `booking_browser`, concurrency **1**
- Volume: `booking_browser_data` → `/data/booking_browser` (djeljen s `django` za import API)

Beat: health check svakih **6h** (`check_booking_extranet_session_task`).

## Email stub → extranet fetch

Nakon ingest emaila koji kreira **stub** rezervaciju (`details_pending=true`), ako je extranet `connected`, enqueue se `fetch_reservation` (Celery, ne blokira ingest). WAF → `needs_human` + VNC; recepcija riješi u iframeu.

## Sigurnost

- Enkriptirani `storage_state` (Fernet); `OptanonConsent` se filtrira pri save/load
- API ne vraća cookie vrijednosti ni lozinku
- Redis lock `booking_extranet:connect` — jedan Playwright connect istovremeno
- VNC token u Redis (`booking_vnc:{token}`), ForwardAuth + Django session

## Povezano

- [booking-ingest.md](../operations/booking-ingest.md)
- [booking-ical.md](booking-ical.md)
