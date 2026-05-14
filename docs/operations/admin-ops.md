# Django Admin (MVP) — operativni pregled

**Owner:** TBD
**Last updated:** 2026-02-15
**Status:** Draft

## Odluka
Za MVP koristimo Django Admin za:
- pregled izdanih računa
- pregled statusa fiskalizacije (FISCALIZED / FAILED / RETRYING)
- pregled eVisitor statusa (PENDING / SENT / FAILED)
 - pregled ingest-a emailova (InboundEmail: parsed/partial/failed)
 - uređivanje tipova soba, soba i fotografija

## Što recepcija radi u aplikaciji
- check-in / gosti / eVisitor
- check-out / izdavanje računa / preuzimanje PDF-a

## Što admin radi u Django Adminu
- pregled i kontrola “problematičnih” stavki (npr. fiskalizacija u retry/failed)
- ručne korekcije ako treba (ovisno o dopuštenjima)

## Communications (email ingest)
- `InboundEmail`:
  - filter `parse_status`: `pending/parsed/partial/failed`
  - inline: attachments + parse errors

## Rooms (room types + photos)
- `RoomType`:
  - i18n fields (name/subtitle/amenities/...)
  - inline upload fotografija (thumbnail preview)
- `Room`:
  - fizičke jedinice (`K1`, `K2`, `D1`, `T1`)
