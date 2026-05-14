# Field schema (kanonska polja)

Ovaj dokument definira polja koja sustav pokušava izvući iz osobnog dokumenta (automatski ili ručnim unosom).

## Kanonska polja

| key | tip | obavezno | napomena / validacija |
|---|---|---:|---|
| `first_name` | string | ✅ | Ime (given name). Trim + normalizacija razmaka. |
| `last_name` | string | ✅ | Prezime (surname/family name). |
| `document_number` | string | ✅ | Čuvati i original i normalizirani (bez razmaka). |
| `sex` | enum | ✅ | `M` / `F` / `X` / `U` (unknown). |
| `nationality` | string | ✅ | Preferirano ISO kod (alpha-2 ili alpha-3), ali dozvoli free-text + kasnije mapiranje. |
| `issuing_country` | string | ✅ | Država izdavatelj (preferirano ISO kod). |
| `document_type` | enum | ✅ | `ID_CARD` / `PASSPORT` / `DRIVER_LICENSE` / `RESIDENCE_PERMIT` / `OTHER`. |
| `address` | string | ⛔ | Često ne postoji na putovnicama; čuvati kao slobodan tekst. |
| `date_of_birth` | date | ✅ | Normalizirati na `YYYY-MM-DD`. |
| `date_of_issue` | date | ⛔ | Ako postoji; `YYYY-MM-DD`. |
| `date_of_expiry` | date | ⛔ | Ako postoji; `YYYY-MM-DD`. |
| `oib` | string | ⛔ | HR OIB (11 znamenki). Najčešće ručni unos; validirati kontrolnu znamenku ako je uneseno. |

## Metapodaci

- `source_provider`: `microblink` / `custom_ocr` / `manual`
- `confidence`: 0–1 po polju (ako provider daje)
- `raw_payload`: originalni output providera (osjetljivo; ograničiti pristup)

## Pravila spremanja (privatnost)

- Slike dokumenata i `raw_payload` su osjetljivi podaci.
- Ograničiti pristup (role-based) + audit log pristupa.
- Definirati retention (brisanje/anonimizacija nakon X dana).