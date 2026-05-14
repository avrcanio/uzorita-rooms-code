# Plaćanje (MVP + budući razvoj)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

## MVP
- Podržavamo **1 poslovni prostor / 1 naplatni uređaj**.
- Na check-outu recepcija odabire način plaćanja:
  - Plaćeno preko Bookinga
  - Gotovina
  - Kartica (za MVP ručno označavanje)

## Budući razvoj — kartično plaćanje preko mobitela (NFC)
- Plan: integracija s **viva.com (Tap on Phone)** za iOS/Android.
- Cilj: iz recepcijske aplikacije pokrenuti naplatu na mobitelu i dobiti rezultat transakcije (success/fail) + referencu.

### Što ćemo spremati kad dođe viva.com
- payment provider: viva.com
- transaction id / reference
- status transakcije
- iznos i valuta
- vrijeme transakcije

## Napomena
Detalji integracije i flow naplate definiraju se u fazi implementacije, nakon što su izdavanje računa i fiskalizacija stabilni.
