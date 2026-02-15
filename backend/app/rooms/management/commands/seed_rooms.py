from django.core.management.base import BaseCommand

from rooms.models import Room, RoomType


class Command(BaseCommand):
    help = "Seed default room types with basic i18n fields (fallback is en)."

    def handle(self, *args, **options):
        # Minimal seed: room codes + English names. Add translations over time.
        items = [
            {
                "code": "R1",
                "name_i18n": {"en": "Deluxe King Room", "hr": "Soba Deluxe s king size krevetom"},
                "beds_i18n": {"en": "1 large double bed", "hr": "1 veliki bračni krevet"},
                "highlights_i18n": {
                    "en": ["Balcony", "Garden view", "Landmark view"],
                    "hr": ["Balkon", "Pogled na vrt", "Pogled na znamenitost"],
                },
                "views_i18n": {"en": ["Inner courtyard view"], "hr": ["Pogled na unutarnje dvorište"]},
                "size_m2": 25,
                "match_aliases": ["r1 deluxe king", "deluxe king", "king size"],
            },
            {
                "code": "R2",
                "name_i18n": {"en": "Deluxe Double Room", "hr": "Dvokrevetna soba Deluxe s bračnim krevetom"},
                "beds_i18n": {"en": "1 large double bed", "hr": "1 veliki bračni krevet"},
                "highlights_i18n": {"en": ["Balcony"], "hr": ["Balkon"]},
                "views_i18n": {"en": ["Garden view"], "hr": ["Pogled na vrt"]},
                "size_m2": 35,
                "match_aliases": ["dvokrevetna", "double", "deluxe double", "bracnim krevetom"],
            },
            {
                "code": "R3",
                "name_i18n": {"en": "Deluxe Triple Room", "hr": "Trokrevetna soba Deluxe"},
                "beds_i18n": {"en": "1 sofa bed and 1 large double bed", "hr": "1 kauč na rasklapanje i 1 veliki bračni krevet"},
                "highlights_i18n": {"en": ["Balcony"], "hr": ["Balkon"]},
                "views_i18n": {"en": ["Garden view"], "hr": ["Pogled na vrt"]},
                "size_m2": 35,
                "match_aliases": ["trokrevetna", "triple", "deluxe triple"],
            },
        ]

        created = 0
        updated = 0
        for item in items:
            rt, was_created = RoomType.objects.get_or_create(code=item["code"], defaults=item)
            if was_created:
                created += 1
                continue
            changed = False
            for k, v in item.items():
                if k == "code":
                    continue
                if getattr(rt, k) != v:
                    setattr(rt, k, v)
                    changed = True
            if changed:
                rt.save()
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"rooms seeded: created={created} updated={updated}"))

        # Physical inventory for Uzorita: 4 units total
        # 2x Deluxe King (R1), 1x Deluxe Double (R2), 1x Deluxe Triple (R3)
        inventory = [
            ("K1", "R1"),
            ("K2", "R1"),
            ("D1", "R2"),
            ("T1", "R3"),
        ]
        inv_created = 0
        inv_updated = 0
        for room_code, type_code in inventory:
            rt = RoomType.objects.filter(code=type_code).first()
            if not rt:
                continue
            room, was_created = Room.objects.get_or_create(
                code=room_code,
                defaults={"room_type": rt, "is_active": True},
            )
            if was_created:
                inv_created += 1
                continue
            if room.room_type_id != rt.id or not room.is_active:
                room.room_type = rt
                room.is_active = True
                room.save()
                inv_updated += 1

        self.stdout.write(self.style.SUCCESS(f"inventory seeded: created={inv_created} updated={inv_updated}"))
