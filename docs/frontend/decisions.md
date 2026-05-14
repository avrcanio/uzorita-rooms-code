# Frontend Decisions

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Active

Dokument za tehničke odluke vezane uz frontend.

## Zapisi odluka
- **2026-02-13 - Frontend stack je Next.js + Tailwind.**
  - Razlog: brz start za web + PWA roadmap, dobar SSR/SEO i jednostavno hostanje iza Traefika.
  - Posljedica: frontend runtime je Node.js 20+.

- **2026-02-13 - Primarni frontend host je `rooms.uzorita.hr`.**
  - Razlog: jedan javni URL za recepciju, bez zasebnog subdomenskog razdvajanja API-ja.
  - Posljedica: backend ide preko path-based routinga (`/api`, `/admin`, `/health`, `/reception`).

- **2026-02-13 - API dokumentacija se izlaže kroz backend na istom hostu.**
  - Razlog: frontend i backend timovi imaju jedinstven endpoint za OpenAPI/Swagger.
  - Posljedica: dostupno na `/api/schema/`, `/api/docs/`, `/api/redoc/`.

- **2026-02-13 - OCR UX je odvojen u poseban scan screen po gostu.**
  - Razlog: mobilni UX je bolji kad kamera radi na dedicated ekranu bez dodatnog formularskog šuma.
  - Posljedica: guest detail sadrzi samo CTA `Skeniraj dokument`, a kamera/OCR su na `/reservations/[id]/guests/[guestId]/scan`.

- **2026-02-13 - Frontend OCR provider je standardiziran na Microblink Browser SDK.**
  - Razlog: PassportEye flow nije davao stabilne rezultate za ciljane dokumente i uklonjen je iz aktivnog toka.
  - Posljedica: frontend trazi `NEXT_PUBLIC_MICROBLINK_LICENSE_KEY` i `NEXT_PUBLIC_MICROBLINK_RESOURCES`.
