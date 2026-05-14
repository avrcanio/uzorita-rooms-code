# M3 Frontend Foundation Spec (Recepcija UI)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** In Progress

## Scope
- Next.js frontend bootstrap za recepciju.
- Deploy na `rooms.uzorita.hr` iza Traefika.
- Vizualni smjer usklađen s Uzorita logom.
- Povezivanje na backend API i docs endpointe.

## Trenutno implementirano
- Frontend path: `code/frontend/`.
- Stack: Next.js 16 + Tailwind + TypeScript.
- Logo asset:
  - `code/frontend/public/kapa.png`
- Landing/recepcija shell:
  - `code/frontend/app/page.tsx`
- Login/auth flow:
  - `code/frontend/app/login/page.tsx`
  - auth API proxy rute (`/api/auth/*`)
- Timeline + detalj:
  - `code/frontend/app/page.tsx` (timeline lista)
  - `code/frontend/app/reservations/[id]/page.tsx` (detalj rezervacije)
  - `code/frontend/app/reservations/[id]/guests/[guestId]/page.tsx` (detalj gosta)
- OCR scan ekran (M4 foundation):
  - `code/frontend/app/reservations/[id]/guests/[guestId]/scan/page.tsx`
- Globalni stilovi i brand boje:
  - `code/frontend/app/globals.css`
- Metadata i icon postavke:
  - `code/frontend/app/layout.tsx`

## Deploy i routing
- Frontend compose:
  - `code/frontend/docker-compose.yml`
- Frontend image build:
  - `code/frontend/Dockerfile`
- Public host:
  - `https://rooms.uzorita.hr` -> frontend
- Backend path routing (isti host):
  - `/api/*`
  - `/admin/*`
  - `/health/*`
  - `/reception/*`

## API docs
- OpenAPI schema:
  - `GET /api/schema/`
- Swagger UI:
  - `GET /api/docs/`
- ReDoc:
  - `GET /api/redoc/`

## Operativne komande
```bash
cd /opt/stacks/uzorita/rooms/code/frontend
docker compose up -d --build
```

```bash
cd /opt/stacks/uzorita/rooms/code/frontend
npm run lint && npm run build
```

## Otvoreno (M3 sljedece)
- PWA manifest + service worker + installability.
- Globalni error/loading/empty states standardizacija.
- QA smoke test na desktop + mobilnim viewportima.
