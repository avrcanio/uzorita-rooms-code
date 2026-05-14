# PaddleOCR + MRZ scan API (backend)

**Last updated:** 2026-05-14  
**Status:** Implemented

## Svrha

- Primati **sliku dokumenta** (multipart) i poslati je na **PaddleOCR** HTTP servis u Docker mreži.
- Iz OCR tekstova izvući **MRZ**, validirati **ICAO checksum** Python bibliotekom `mrz`, uz ograničenu korekciju tipičnih OCR zamjena znakova.
- Zapisati **audit** u `DocumentScanLog`.
- **Ne ažurirati** `Guest` u ovom koraku — klijent (Flutter) prikazuje rezultat; nakon korisničke potvrde šalje se postojeći `POST .../document-scan/` s JSON payloadom (Microblink oblik).

## Endpoint

- **URL:** `POST /api/v1/scan/`
- **Auth:** `IsAuthenticated` (session ili basic, kao ostatak reception API-ja).
- **Content-Type:** `multipart/form-data`

### Polja forme

| Polje            | Obavezno | Opis |
|------------------|----------|------|
| `file`           | da       | Slika dokumenta (JPEG/PNG…). Maks. veličina: `PADDLE_OCR_SCAN_MAX_BYTES` (default 8 MiB). |
| `guest_id`       | da       | ID gosta; rezervacija se uzima iz `guest.reservation_id` za audit FK. |
| `reservation_id` | ne       | Ako je poslan, mora se podudarati s `guest.reservation_id` (zaštita od zloupotrebe). |

### Odgovor (200)

| Polje              | Tip    | Opis |
|--------------------|--------|------|
| `scan_log_id`      | int    | ID zapisa u `DocumentScanLog`. |
| `scan_status`      | string | `ok` ili `failed` (`DocumentScanStatus`). |
| `duration_ms`      | int    | Trajanje obrade na serveru. |
| `ocr`              | object | `items` (lista `{text, confidence?, box?}`), `http_status`, `configured`. |
| `mrz`              | object | `lines`, `format` (`TD1`/`TD2`/`TD3` ili `null`), `checksum_valid`, `parsed`, `corrected`, `correction`. |
| `suggested_fields` | object | Polja usklađena s `Guest` / preview modelom (npr. `first_name`, `last_name`, `document_number`, datumi, `nationality`, `mrz_raw_text`, …) kad je MRZ valjan. |
| `raw_payload`      | object | `provider: paddleocr`, odgovor Paddle servisa (`paddle_response`), MRZ meta. |
| `error`            | string | Poruka za UI; prazno ako je `scan_status=ok`. |

### Greške

- **400** — validacija forme ili nepodudaranje `reservation_id`.
- **404** — `guest_id` ne postoji.
- **503** — PaddleOCR URL nije postavljen ili HTTP poziv nije uspio.

## Okruženje (env)

U [`backend/.env.example`](../../../backend/.env.example):

- `PADDLE_OCR_BASE_URL` — baza URL-a servisa, npr. `http://127.0.0.1:8866` ili IP kontejnera na bridge mreži (vidi `docker inspect paddleocr`).
- `PADDLE_OCR_PREDICT_PATH` — putanja POST rute. **PaddleHub Serving** (službeni PaddleOCR `deploy/hubserving`): npr. `/predict/ocr_system` (port tipično **8866** ako je jedan modul). Multipart API-ji često koriste `/predict`.
- `PADDLE_OCR_REQUEST_FORMAT` — `multipart` (default) ili `json_images` za PaddleHub (`{"images":["<base64>"]}`, `Content-Type: application/json`).
- `PADDLE_OCR_FILE_FIELD` — ime multipart polja za sliku (default `file`), koristi se samo kod `multipart`.
- `PADDLE_OCR_TIMEOUT_SECONDS` — timeout HTTP klijenta (default `90`).
- `PADDLE_OCR_SCAN_MAX_BYTES` — limit uploada (default `8388608`).

### Docker napomena

Lokalni [`backend/docker-compose.yml`](../../../backend/docker-compose.yml) koristi `network_mode: host` za Django. U tom modu **hostname drugih stackova** (npr. `paddleocr`) često **nije** rješiv — koristite `127.0.0.1` s objavljenim portom ili uskladite Docker mrežu (isti user-defined network).

**Ugrađeni FastAPI PaddleOCR** (`paddle-ocr-fastapi` u istom composeu): build iz [`ocr_service`](../../../ocr_service) (Python 3.10, port **8866**). Endpointi: `GET /health`, `POST /predict` s JSON `{"images":["<base64>", ...]}` (do 4 slike). Odgovor: `{"results": [[{"text","confidence","text_region"}, ...], ...]}` — usklađeno s `PADDLE_OCR_REQUEST_FORMAT=json_images` i `normalize_paddle_response` u backendu. Primjer env: `PADDLE_OCR_BASE_URL=http://127.0.0.1:8866`, `PADDLE_OCR_PREDICT_PATH=/predict`.

## Paddle HTTP kontrakt (implementacija)

### Način `multipart` (default)

```http
POST {PADDLE_OCR_BASE_URL}{PADDLE_OCR_PREDICT_PATH}
Content-Type: multipart/form-data
```

Polje datoteke: `{PADDLE_OCR_FILE_FIELD}`.

### Način `json_images` (PaddleHub Serving)

```http
POST {PADDLE_OCR_BASE_URL}{PADDLE_OCR_PREDICT_PATH}
Content-Type: application/json

{"images": ["<base64>"]}
```

Primjer URL-a (PaddleHub): `http://<host>:8866/predict/ocr_system` (vidi [PaddleOCR hubserving readme](https://github.com/PaddlePaddle/PaddleOCR/blob/main/deploy/hubserving/readme_en.md)). Za ugrađeni FastAPI servis koristite `/predict` na portu **8866** bez PaddleHuba.

### Odgovor

Očekivani JSON odgovor je **fleksibilno** parsiran: traže se ugniježđeni objekti s ključem `text`; za PaddleHub dodatno se čita `results[0]` kao lista linija s `text_region` kao bbox.

## MRZ

- Modul: `reception/services/mrz_pipeline.py`
- Biblioteka: `mrz` (ICAO checksum).
- Podržani formati: **TD3** (pasoš, 2×44), **TD2**, **TD1**.
- Ograničena korekcija: jedna zamjena znaka iz mape tipičnih OCR zamjena; odabir kandidata minimizira udaljenost od OCR linija koje su ušle u MRZ blok.

## OpenAPI

Šema je opisana u `drf-spectacular` (`@extend_schema` na viewu). Pregled: `/api/docs/` (Swagger) i `/api/schema/`.
