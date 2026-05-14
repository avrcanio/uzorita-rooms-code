# Otkaz rezervacije — politika (MVP)

**Last updated:** 2026-02-16  
**Status:** Active (MVP)

## MVP pravilo
- Otkaz je moguć **bilo kada**.
- Naknada za otkaz: **0%** (free cancellation).

## Impl. napomena
- Public cancel flow ostaje (email link), ali `cancel/preview` uvijek vraća `fee_percent=0` (i `fee_amount=0`).