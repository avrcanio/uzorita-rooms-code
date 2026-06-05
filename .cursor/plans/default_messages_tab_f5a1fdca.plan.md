---
name: Default Messages tab
overview: Srednji bottom-nav tab (Recenzije/Poruke) neka pri svakom pokretanju aplikacije defaultno prikaže **Poruke**, promjenom početnog stanja u Riverpod provideru.
todos:
  - id: default-messages-mode
    content: Promijeniti middleTabModeProvider.build() default u MiddleTabMode.messages
    status: completed
isProject: false
---

# Default: Poruke umjesto Recenzija na srednjem tabu

## Trenutno ponašanje

Srednji slot (index 3) koristi [`MiddleHubScreen`](c:/Users/avrca/Documents/Projects/Uzorita_all/uzorita_flutter/lib/features/messages/presentation/middle_hub_screen.dart) koji čita [`middleTabModeProvider`](c:/Users/avrca/Documents/Projects/Uzorita_all/uzorita_flutter/lib/features/messages/presentation/middle_tab_mode_provider.dart):

```dart
MiddleTabMode build() => MiddleTabMode.reviews;
```

[`ReceptionShellScaffold`](c:/Users/avrca/Documents/Projects/Uzorita_all/uzorita_flutter/lib/app/reception_shell_scaffold.dart) ikona/label i re-tap toggle već rade ispravno — samo početno stanje je `reviews`.

## Promjena (1 linija)

U [`middle_tab_mode_provider.dart`](c:/Users/avrca/Documents/Projects/Uzorita_all/uzorita_flutter/lib/features/messages/presentation/middle_tab_mode_provider.dart):

```dart
MiddleTabMode build() => MiddleTabMode.messages;
```

## Što se ne mijenja

- **Re-tap toggle** ostaje: ponovni tap na srednji tab i dalje prebacuje Poruke ↔ Recenzije.
- **Nema persistencije** između sesija — svaki cold start otvara Poruke; ako kasnije želiš „zapamti zadnji izbor”, to bi bio zaseban zadatak (`SharedPreferences`).
- **L10n / backend** — nije potrebno.

## Ručna provjera

1. `flutter run` (cold start)
2. Tap srednji tab → vidi **Poruke** (inbox), ikona chat + label `navMessages`
3. Re-tap → prebaci na Recenzije
4. Hot restart → opet Poruke
