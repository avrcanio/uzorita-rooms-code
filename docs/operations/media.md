# Media uploads (RoomType photos) — Runbook

**Last updated:** 2026-02-15
**Status:** Active

RoomType fotografije se spremaju kroz Django admin i servaju preko `/media/*` na domeni `rooms.uzorita.hr`.

## Gdje se datoteke spremaju
Backend `MEDIA_ROOT`:
- `/opt/stacks/uzorita/rooms/code/backend/app/media`

Primjer puta:
- `media/room_types/photos/2026/02/15/1658407021.jpg`

## Kako se servaju na webu
Za host `rooms.uzorita.hr` postoji odvojeni nginx container:
- `uzorita-media`

On serva host folder:
- `../backend/app/media` -> `/usr/share/nginx/html/media`

Routing:
- `https://rooms.uzorita.hr/media/...` ide na `uzorita-media`

Konfiguracija je u:
- `code/frontend/docker-compose.yml`

## Troubleshooting
### 404 na `/media/...`
Najčešći razlog: `/media/*` je išao na Next.js router.

Provjeri:
```bash
cd /opt/stacks/uzorita/rooms/code/frontend
docker compose ps
```

Trebaš vidjeti:
- `uzorita-media` running

### Datoteka postoji ali se ne učitava
Provjeri da file postoji na hostu:
```bash
ls -la /opt/stacks/uzorita/rooms/code/backend/app/media/room_types/photos/...
```

Provjeri HTTP:
```bash
curl -I https://rooms.uzorita.hr/media/room_types/photos/...
```

## Backup
Za backup je dovoljno kopirati cijeli folder:
- `/opt/stacks/uzorita/rooms/code/backend/app/media`

