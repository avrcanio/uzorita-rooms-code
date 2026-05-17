# eVisitor — test okolina

**Last updated:** 2026-05-17

## Env (backend `.env`, ne commitati tajne)

```env
EVISITOR_ENABLED=true
EVISITOR_ENV=test
EVISITOR_BASE_URL=https://www.evisitor.hr/testApi
EVISITOR_USERNAME=...
EVISITOR_PASSWORD=...
EVISITOR_API_KEY=...
EVISITOR_FACILITY_CODE=...   # ili PropertyInfo.evisitor_facility_code u adminu
```

Produkcija: `EVISITOR_ENV=prod`, URL `https://www.evisitor.hr/eVisitorRhetos_API` (bez `apikey`).

## Deploy

```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker exec uzorita-django python manage.py migrate
docker compose restart django
```

## Provjera

```bash
docker exec uzorita-django python manage.py evisitor_probe
```

## API (Flutter)

`POST /api/reception/reservations/<rid>/guests/<gid>/evisitor-submit/`

- Uspjeh: `200`, `status: sent`, `registration_id`
- Validacija: `400` s poljima
- eVisitor greška: `502` s `user_message`

## Poslovna pravila

- Checkout (`checked_in` → `checked_out`) blokiran dok `evisitor_summary != complete`
- Timeline: sve `checked_in` rezervacije uvijek u listi (i izvan `period_from`/`period_to`)

## Test u eVisitor UI

1. Gost s punim podacima (ime, spol, rođenje, dokument, državljanstvo)
2. App: Gosti → eVisitor → Pošalji
3. Provjera na https://www.evisitor.hr/test
