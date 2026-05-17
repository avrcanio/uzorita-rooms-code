from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from reception.evisitor.client import EvisitorClient
from reception.evisitor.exceptions import EvisitorApiError, EvisitorConfigError


class Command(BaseCommand):
    help = "Provjera pristupa eVisitor test/prod API-ju (login + Country lookup)."

    def handle(self, *args, **options):
        if not settings.EVISITOR_ENABLED:
            raise CommandError("EVISITOR_ENABLED nije true.")

        self.stdout.write(f"ENV={settings.EVISITOR_ENV}")
        self.stdout.write(f"BASE_URL={settings.EVISITOR_BASE_URL}")

        client = EvisitorClient()
        try:
            client.login()
            self.stdout.write(self.style.SUCCESS("Login: OK"))
            countries = client.fetch_records("Country", psize=3)
            self.stdout.write(f"Country sample: {len(countries)} zapisa")
            if countries:
                first = countries[0]
                self.stdout.write(
                    f"  primjer: {first.get('CodeTwoLetters')} -> {first.get('CodeThreeLetters')}"
                )
        except (EvisitorConfigError, EvisitorApiError) as exc:
            raise CommandError(str(exc)) from exc
        finally:
            try:
                client.logout()
            finally:
                client.close()

        self.stdout.write(self.style.SUCCESS("eVisitor probe završen uspješno."))
