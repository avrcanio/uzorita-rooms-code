# Booking.com iCal sinkronizacija

**Last updated:** 2026-05-16  
**Status:** Active (R1)

Dvosmjerna sinkronizacija raspoloživosti između Uzorita sustava i Booking.com listinga **Luxury Room Uzorita - R1**.

## Kako radi

| Smjer | Što | Gdje |
|-------|-----|------|
| **Export** (Uzorita → Booking) | Javni `.ics` URL; Booking poll-a ~svaka 2 h | Booking korak 1 „Importirajte kalendar” |
| **Import** (Booking → Uzorita) | Celery beat povlači Booking export URL | `sync_booking_ical` / `uzorita-celery-beat` |

**Export logika (R1):** Booking se blokira tek kad su **obje** fizičke R1 sobe (K1 i K2) zauzete rezervacijama koje **nisu** s Bookingu (direktna prodaja, drugi kanal, ručno). Rezervacije iz `booking_xls` / `booking_email` se **ne šalju** natrag — Booking ih već ima.

Rezervacije iz iCal-a idu u `Reservation` s `import_source=booking_ical`. Ako isti Booking broj stigne i emailom, `external_id` se poklapa i nema duplikata.

**Važno:** Booking export URL sadrži uglavnom `CLOSED - Not available` blokade (zauzeti datumi), ne prave rezervacije s brojem. Import **preskače** te blokade; prave Booking rezervacije i dalje dolaze **emailom**.

## Postavljanje u Booking.com

### Korak A — Export (naš kalendar u Booking)

1. Django admin → **Booking iCal feeds** → otvorite `r1`.
2. Kopirajte **export token** i sastavite URL:
   ```
   https://<api-host>/api/public/ical/r1/<export_token>.ics
   ```
   Primjer hosta: API koji servira Django (`rooms` backend).
3. U Booking extranetu: **Sinkronizacija kalendara** → korak 1.
4. Zalijepite URL, naziv kalendara npr. `Uzorita`, **Sljedeći korak**.

Ako token kompromitirate: admin akcija **Regenerate export token** (stari URL prestaje raditi).

### Korak B — Import (Booking kalendar kod nas)

1. U Bookingu završite korak 2 **Eksportiranje kalendara** i kopirajte njihov iCal URL.
2. Django admin → `r1` → polje **import url** → spremite.
3. Ručno provjera:
   ```bash
   python manage.py sync_booking_ical --feed=r1
   ```
4. Celery beat (`uzorita-celery-beat`) automatski pokreće `sync_booking_ical_task` svakih **30 min** (uz email pipeline na workeru).

## Operativa

| Naredba | Opis |
|---------|------|
| `python manage.py sync_booking_ical --feed=r1` | Sync jednog feeda |
| `python manage.py sync_booking_ical --feed=all` | Svi aktivni feedovi s `import_url` |
| `python manage.py sync_booking_ical --feed=r1 --dry-run` | Bez upisa u bazu |

Ručni debug (`run_booking_pipeline` management command, ako je potreban):

- `--ical-interval 1800` — interval u sekundama (default 30 min)
- `--skip-ical` — isključi iCal sync u petlji

## Ograničenja

- iCal obično **nema** guest email / iznose — to i dalje dolazi email ingestom.
- Booking poll vanjskog kalendara nije real-time (~2 h).
- Samo **R1** feed u MVP-u; R2/R3 po istom uzorku kasnije.

## Povezani kod

- Model: `reception.models.BookingIcalFeed`
- Export: `reception/ical/export.py`, endpoint `GET /api/public/ical/r1/<token>.ics`
- Import: `reception/ical/import_sync.py`, `sync_booking_ical` command
