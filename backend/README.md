# Backend (Django) local setup

## Files
- `docker-compose.yml` - Django service in Docker
- `.env` - local environment values
- `.env.example` - env template
- `app/` - Django source code (must contain `manage.py`)

## Start
```bash
cd /opt/stacks/uzorita/rooms/code/backend
docker compose up -d
```

## Notes
- Existing PostGIS is expected on host at `127.0.0.1:5432`.
- From container, DB host must be `127.0.0.1`.
- If `app/manage.py` does not exist yet, create project first:
```bash
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && django-admin startproject config ."
```

- Create Django superuser:
```bash
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py createsuperuser"
```

- Bootstrap roles/groups (`reception`, `manager`, `admin`):
```bash
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py bootstrap_roles"
```

- Fetch unread booking emails from IMAP mailbox:
```bash
docker compose run --rm django sh -lc "pip install --no-cache-dir -r requirements.txt && python manage.py fetch_booking_emails --limit 50"
```
