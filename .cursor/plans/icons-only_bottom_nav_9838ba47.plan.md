---
name: Icons-only bottom nav
overview: Sakriti tekstualne labele u donjem tab baru recepcije, ostaviti samo ikone. Jedna izmjena u `NavigationBar` widgetu; l10n stringovi ostaju za pristupačnost (screen reader).
todos:
  - id: add-label-behavior
    content: "U reception_shell_scaffold.dart dodati labelBehavior: NavigationDestinationLabelBehavior.alwaysHide na NavigationBar"
    status: completed
  - id: visual-verify
    content: Pokrenuti app i provjeriti icons-only bar na svim tabovima (badge, calendar long-press)
    status: completed
isProject: false
---

# Icons-only bottom navigation

## Kontekst

Donji tab bar je definiran u [`lib/app/reception_shell_scaffold.dart`](c:\Users\avrca\Documents\Projects\Uzorita_all\uzorita_flutter\lib\app\reception_shell_scaffold.dart) — jedini `NavigationBar` u aplikaciji. Koristi Material 3 `NavigationDestination` s `label` za svaki tab (Timeline, Calendar, Messages/Reviews, Statistics, More).

```65:96:c:\Users\avrca\Documents\Projects\Uzorita_all\uzorita_flutter\lib\app\reception_shell_scaffold.dart
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: (index) => _onDestinationSelected(index, ref),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.schedule),
            label: context.l10n.navTimeline,
          ),
          // ... ostali tabovi s labelama
        ],
      ),
```

## Rješenje

Dodati **`labelBehavior: NavigationDestinationLabelBehavior.alwaysHide`** na `NavigationBar`.

To je službeni Material 3 način za skrivanje labela — ne treba brisati `label` parametre niti l10n stringove (`navTimeline`, `navCalendar`, itd.). Labele ostaju za **semantiku / screen reader** (TalkBack, VoiceOver), ali se vizualno ne prikazuju.

```dart
bottomNavigationBar: NavigationBar(
  labelBehavior: NavigationDestinationLabelBehavior.alwaysHide,
  selectedIndex: navigationShell.currentIndex,
  // ...
),
```

## Što se ne mijenja

| Stavka | Razlog |
|--------|--------|
| `label:` na svakom `NavigationDestination` | Pristupačnost |
| `tool/l10n/strings.json` i `.arb` datoteke | Isti stringovi za a11y |
| Ikone, badge na Messages, long-press na Calendar | Postojeće ponašanje ostaje |
| [`lib/app/app.dart`](c:\Users\avrca\Documents\Projects\Uzorita_all\uzorita_flutter\lib\app\app.dart) | Samo koristi scaffold, nema vlastiti nav bar |

## Očekivani UI rezultat

- Donji bar prikazuje samo 5 ikona (s pill pozadinom na aktivnom tabu)
- Bar je nešto niži (Flutter automatski smanjuje visinu kad su labele skrivene)
- Messages badge (`needsReplyCount`) i toggle Messages/Reviews na srednjem tabu rade kao i dosad

## Test plan

1. `flutter run` na uređaju/emulatoru
2. Provjeri svih 5 tabova — samo ikone, bez teksta ispod
3. Aktivni tab ima pill highlight (kao na screenshotu, ali bez labela)
4. Srednji tab: Messages badge + toggle ikona (chat/star) i dalje rade
5. Calendar: long-press i dalje otvara filter
6. (Opcionalno) TalkBack/VoiceOver: tabovi se i dalje najavljuju po imenu (Timeline, Calendar, …)
