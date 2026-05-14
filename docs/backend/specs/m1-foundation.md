# M1 Foundation Spec (Backend + Infra)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Completed

## Scope
- Django bootstrap i settings sloj (`base/dev/prod`).
- Docker servis za backend aplikaciju.
- Spajanje na postojeci host Postgres/PostGIS.
- Admin i auth osnova za daljnje milestone-e.

## Trenutna implementacija
- Backend path: `code/backend/`.
- Django app path: `code/backend/app/`.
- Health endpoint: `GET /health/`.
- Admin URL: `/admin/`.
- Admin branding: `Uzorita administracija`.
- Static logo/favikon:
  - `/logo.png`
  - `/favicon.ico`

## Runtime konfiguracija
- Compose: `code/backend/docker-compose.yml`
- Env: `code/backend/.env`
- DB host: `127.0.0.1`
- DB port: `5432`
- DB engine: `django.db.backends.postgresql`
- CSRF trusted origins:
  - `https://rooms.uzorita.hr`

## Django Apps
- `django.contrib.admin` - admin panel.
- `django.contrib.auth` - korisnici, grupe i autentikacija.
- `django.contrib.contenttypes` - content type framework (required za permissions).
- `django.contrib.sessions` - session management.
- `django.contrib.messages` - flash poruke u admin/UI.
- `django.contrib.staticfiles` - static file handling.
- `config` - lokalna aplikacija za project-level konfiguracije i management komande.
- `reception` - domen app za rezervacije, goste i ID dokumente.
- `communications` - email ingest/outbound modeli i IMAP management komande.

## Deploy i domain
- Public host: `rooms.uzorita.hr`
- Reverse proxy: Traefik (`/opt/stacks/core-traefik`)
- TLS: ACME DNS challenge preko Cloudflare
- Cloudflare record: `rooms` je proxied (`orange cloud`)

## Operativne komande
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose up -d
```

```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py createsuperuser"
```

```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py bootstrap_roles"
```

## Poznate napomene
- `docker compose run` ne nasleduje service startup `command` logiku iz `up`, zato je u run komandi ukljucen `pip install`.
- Za puni GIS backend (PostGIS engine u Django-u) potreban je custom image sa GDAL/GEOS bibliotekama.

## Povezano
- M2 email ingest runbook: `docs/backend/specs/m2-email-ingest.md`
