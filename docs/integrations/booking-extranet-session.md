# Booking.com extranet — session i login

**Last updated:** 2026-05-17  
**Status:** noVNC + Tailscale exit node

## CAPTCHA i SMS

Booking nakon više automatskih pokušaja traži **SMS** i **CAPTCHA** (uključujući AWS WAF „Human Verification”). Headless Playwright to ne rješava pouzdano.

**Primarni put:** worker `celery-booking-browser` (headed Chromium na `DISPLAY=:99`) + **Tailscale exit node** na laptopu (`TAILSCALE_EXIT_NODE`). Recepcija na **Postavke → Booking** vidi **noVNC iframe**, riješi CAPTCHA, klikne **Nastavi**; isti browser context nastavlja connect / health / dohvat rezervacije.

**Rezervni put:** prijava na laptopu u browseru → export Playwright `storage_state.json` → **Spremi sesiju** u UI (ili `import-state` API).

Automatski connect (`BOOKING_EXTRANET_CONNECT_MODE=automatic`) radi max **1×/24h**; CAPTCHA → `needs_human` + VNC token. U `human_assisted` načinu VNC prijava s servera radi kad je postavljen `TAILSCALE_EXIT_NODE`.

## Ručni uvoz sesije

1. Na laptopu: prijava na Booking extranet (login URL iz `BOOKING_EXTRANET_LOGIN_URL`).
2. Export `storage_state.json` (Playwright ili DevTools).
3. U recepciji: **Postavke → Booking** → **Zalijepi JSON** / **Učitaj datoteku**.
4. **Provjeri sesiju**.

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

Na serveru: `python manage.py upload_booking_storage_state /path/to/storage_state.json`

## Svrha

Održavati **valjanu prijavu** na Booking.com extranet (`admin.booking.com`) iz recepcijskog UI-a, spremiti sesiju (cookies + localStorage) na serveru i obavijestiti kad istekne.

**Ne zamjenjuje:** XLS import, email ingest, iCal.

## Statusi veze

| Status | Značenje | Akcija u UI |
|--------|----------|-------------|
| `disconnected` | Nema spremljene sesije | VNC prijava ili uvezi sesiju |
| `connecting` | Playwright radi login | Pričekaj / poll |
| `needs_2fa` | Treba SMS kod | Unesi kod ili uvezi sesiju s laptopa |
| `needs_human` | CAPTCHA / WAF | noVNC + **Nastavi** |
| `connected` | Sesija valjana | — |
| `expired` | Health check našao login | VNC ili uvezi sesiju |
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
TS_LOGIN_SERVER=https://hs-control.qubitsecured.online
TS_HOSTNAME_BOOKING_BROWSER=tailscale-booking-browser
TS_AUTHKEY_BOOKING_BROWSER=<hskey-auth-...>
TAILSCALE_EXIT_NODE=100.64.0.8
BOOKING_EXTRANET_TAILSCALE_EXIT_NODE=100.64.0.8
```

`op_token` u LOGIN_URL može isteći — generiraj novi iz extraneta (Manage → Reservations).

### Tailscale exit node

1. Na **laptopu:** oglašavanje exit nodea u Headscaleu.
2. Auth key za `tailscale-booking-browser` u `.env`.
3. Odobri rute `0.0.0.0/0,::/0` za exit node uređaj:
   ```bash
   docker exec headscale headscale nodes list-routes --identifier <node-id>
   docker exec headscale headscale nodes approve-routes -i <node-id> -r "0.0.0.0/0,::/0"
   ```
4. Provjera: `docker exec uzorita-celery-booking-browser curl -4 -s https://ifconfig.me` → IP laptop ISP-a.
5. Laptop **online** dok worker radi.

Traefik: `PathPrefix(/booking-vnc)` → websockify na `tailscale-booking-browser`, ForwardAuth → Django.

## API

| Endpoint | Opis |
|----------|------|
| `GET /api/reception/booking-extranet/connection/` | Status za UI |
| `POST /api/reception/booking-extranet/connection/start/` | Pokreni prijavu (VNC) |
| `POST /api/reception/booking-extranet/connection/import-state/` | Upload `storage_state` |
| `POST /api/reception/booking-extranet/vnc/continue/` | Nakon CAPTCHA |
| `POST /api/reception/booking-extranet/connection/check/` | Health check |

## Docker

- `tailscale-booking-browser` + `celery-booking-browser` (`network_mode: service:...`)
- Queue `booking_browser`, volume `booking_browser_data`

## Povezano

- [booking-ingest.md](../operations/booking-ingest.md)
- [booking-ical.md](booking-ical.md)
