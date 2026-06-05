---
name: Fix WhatsApp launch Android
overview: Backend handoff radi (poruka u timelineu), ali Android ne otvara WhatsApp jer manifest nema package visibility queries za wa.me, a Flutter tiho preskače launch kad canLaunchUrl vrati false.
todos:
  - id: android-queries
    content: "AndroidManifest.xml: queries za wa.me, api.whatsapp.com, whatsapp://, com.whatsapp paketi"
    status: completed
  - id: flutter-launch
    content: whatsapp_launch.dart helper + _sendWhatsApp bez tihog faila + fallback whatsapp://
    status: completed
  - id: l10n-launch-failed
    content: L10n channelWhatsAppLaunchFailed + gen_arb
    status: completed
  - id: device-test
    content: Full rebuild test na Pixelu s WhatsApp Business
    status: completed
isProject: false
---

# Fix: WhatsApp se ne otvara nakon handoffa (Android)

## Dijagnoza

Log:
```
I/UrlLauncher: component name for https://wa.me/385976713511?text=... is null
```

**Backend je OK** — u UI-u se vidi outbound bubble „WhatsApp handoff” (poruka spremljena u audit).

**Problem je na Androidu:**
1. [`AndroidManifest.xml`](c:/Users/avrca/Documents/Projects/Uzorita_all/uzorita_flutter/android/app/src/main/AndroidManifest.xml) ima `<queries>` samo za `PROCESS_TEXT`, **ne** za `https://wa.me` niti paket WhatsAppa.
2. Od Android 11, `canLaunchUrl()` vraća **false** bez tih deklaracija → handler se ne pronađe (`component name ... is null`).
3. [`reservation_messages_section.dart`](c:/Users/avrca/Documents/Projects/Uzorita_all/uzorita_flutter/lib/features/reception/presentation/widgets/reservation_messages_section.dart) tiho preskače launch:

```dart
if (await canLaunchUrl(uri)) {
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}
// nema else — korisnik ne vidi grešku
```

iOS [`Info.plist`](c:/Users/avrca/Documents/Projects/Uzorita_all/uzorita_flutter/ios/Runner/Info.plist) već ima `whatsapp` scheme — ovaj bug je **Android-specifičan**.

---

## Fix 1 — AndroidManifest `<queries>` (obavezno)

U [`android/app/src/main/AndroidManifest.xml`](c:/Users/avrca/Documents/Projects/Uzorita_all/uzorita_flutter/android/app/src/main/AndroidManifest.xml), proširiti postojeći `<queries>` blok:

```xml
<queries>
    <!-- postojeći PROCESS_TEXT ... -->

    <!-- wa.me / WhatsApp (Android 11+ package visibility) -->
    <intent>
        <action android:name="android.intent.action.VIEW" />
        <data android:scheme="https" android:host="wa.me" />
    </intent>
    <intent>
        <action android:name="android.intent.action.VIEW" />
        <data android:scheme="https" android:host="api.whatsapp.com" />
    </intent>
    <intent>
        <action android:name="android.intent.action.VIEW" />
        <data android:scheme="whatsapp" />
    </intent>
    <package android:name="com.whatsapp" />
    <package android:name="com.whatsapp.w4b" />
</queries>
```

**Napomena:** promjena manifesta zahtijeva **pun rebuild** (`flutter run` stop/start), ne hot restart.

---

## Fix 2 — Flutter launch logika (obavezno)

Novi mali helper npr. [`lib/core/utils/whatsapp_launch.dart`](c:/Users/avrca/Documents/Projects/Uzorita_all/uzorita_flutter/lib/core/utils/whatsapp_launch.dart):

```dart
Future<bool> launchWhatsAppUrl(String waMeUrl) async {
  final uri = Uri.parse(waMeUrl);
  // Pokušaj direktno — canLaunchUrl na Androidu laže bez queries prije fixa
  final launched = await launchUrl(uri, mode: LaunchMode.externalApplication);
  if (launched) return true;

  // Fallback: whatsapp://send?phone=&text= iz wa.me URL-a
  ...
}
```

U `_sendWhatsApp`:
- pozvati helper umjesto `canLaunchUrl` + `launchUrl`
- ako `false` → SnackBar s novim stringom `channelWhatsAppLaunchFailed` (npr. „WhatsApp nije otvoren. Provjerite je li instaliran.”)
- **ne** brisati composer tekst ako launch padne (korisnik može retry)

---

## Fix 3 — L10n

Dodati u [`tool/l10n/strings.json`](c:/Users/avrca/Documents/Projects/Uzorita_all/uzorita_flutter/tool/l10n/strings.json):

- `channelWhatsAppLaunchFailed` — HR/EN (+ es/it/fr/de)

`python tool/gen_arb.py` + `flutter gen-l10n`

---

## Test plan

| # | Korak | Očekivano |
|---|--------|-----------|
| 1 | `flutter run` **full rebuild** na Pixelu s WhatsApp Business | |
| 2 | Rezervacija #833 → Generiraj → WhatsApp | WhatsApp se otvori s brojem + tekstom |
| 3 | Logcat | Nema `component name ... is null` za wa.me (ili launch uspije unatoč logu) |
| 4 | Bez WhatsAppa (emulator) | SnackBar „WhatsApp nije otvoren…” |

---

## Nije potrebno

- Backend promjene — `wa_me_url` i handoff već rade
- iOS promjene — već ima `LSApplicationQueriesSchemes`

---

## Redoslijed

1. AndroidManifest queries
2. Flutter helper + SnackBar na failure
3. L10n
4. Full rebuild na uređaju
