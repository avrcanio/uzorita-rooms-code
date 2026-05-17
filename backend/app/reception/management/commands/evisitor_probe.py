from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from reception.evisitor.client import EvisitorClient
from reception.evisitor.exceptions import EvisitorApiError, EvisitorConfigError
from reception.evisitor.mapper import _resolve_facility_code
from rooms.models import PropertyInfo


class Command(BaseCommand):
    help = "Provjera pristupa eVisitor test/prod API-ju (login + Country lookup)."

    def handle(self, *args, **options):
        if not settings.EVISITOR_ENABLED:
            raise CommandError("EVISITOR_ENABLED nije true.")

        self.stdout.write(f"ENV={settings.EVISITOR_ENV}")
        self.stdout.write(f"BASE_URL={settings.EVISITOR_BASE_URL}")
        facility = _resolve_facility_code()
        self.stdout.write(f"FACILITY={facility or '(nije postavljeno)'}")
        prop = PropertyInfo.objects.filter(is_active=True).first()
        if prop:
            self.stdout.write(
                f"  PropertyInfo: code={prop.code} facility={prop.evisitor_facility_code or '-'}"
            )

        client = EvisitorClient()
        try:
            client.login()
            self.stdout.write(self.style.SUCCESS("Login: OK"))
            for resource, sort in (
                ("Country", "NameNational asc"),
                ("DocumentTypeLookup", "Code asc"),
                ("FacilityBrowse", "Code asc"),
                ("ArrivalOrganisationLookup", "CodeMI asc"),
            ):
                try:
                    records = client.fetch_records(resource, psize=5, sort=sort)
                    self.stdout.write(f"{resource}: {len(records)} zapisa")
                    if resource == "FacilityBrowse" and records:
                        for row in records[:5]:
                            self.stdout.write(
                                f"  {row.get('Code')} — {row.get('Name') or row.get('FacilityName') or '-'}"
                            )
                    elif resource == "Country" and records:
                        first = records[0]
                        self.stdout.write(
                            f"  primjer: {first.get('CodeTwoLetters')} -> {first.get('CodeThreeLetters')}"
                        )
                except EvisitorApiError as exc:
                    self.stdout.write(self.style.WARNING(f"{resource} preskočen: {exc}"))
        except (EvisitorConfigError, EvisitorApiError) as exc:
            raise CommandError(str(exc)) from exc
        finally:
            try:
                client.logout()
            finally:
                client.close()

        self.stdout.write(self.style.SUCCESS("eVisitor probe završen uspješno."))
