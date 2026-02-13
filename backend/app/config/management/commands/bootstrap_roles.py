from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


ROLE_SPECS = {
    "reception": {
        "auth.user": {"view"},
        "reception.reservation": {"view", "add", "change"},
        "reception.guest": {"view", "add", "change"},
        "reception.iddocument": {"view", "add", "change"},
        "communications.inboundemail": {"view"},
        "communications.parseerror": {"view"},
    },
    "manager": {
        "auth.user": {"view"},
        "auth.group": {"view"},
        "reception.reservation": {"view", "add", "change", "delete"},
        "reception.guest": {"view", "add", "change", "delete"},
        "reception.iddocument": {"view", "add", "change", "delete"},
        "communications.inboundemail": {"view", "change"},
        "communications.parseerror": {"view", "change"},
        "communications.emailattachment": {"view"},
        "communications.outboundemail": {"view", "add", "change"},
    },
    "admin": {
        "auth.user": {"view", "add", "change", "delete"},
        "auth.group": {"view", "add", "change", "delete"},
        "auth.permission": {"view"},
        "sessions.session": {"view", "delete"},
        "reception.reservation": {"view", "add", "change", "delete"},
        "reception.guest": {"view", "add", "change", "delete"},
        "reception.iddocument": {"view", "add", "change", "delete"},
        "communications.inboundemail": {"view", "add", "change", "delete"},
        "communications.parseerror": {"view", "add", "change", "delete"},
        "communications.emailattachment": {"view", "add", "change", "delete"},
        "communications.outboundemail": {"view", "add", "change", "delete"},
    },
}


class Command(BaseCommand):
    help = "Create/update baseline Django Groups and permissions."

    def handle(self, *args, **options):
        for role, spec in ROLE_SPECS.items():
            group, _ = Group.objects.get_or_create(name=role)

            # Reset permissions to declared baseline so command stays idempotent.
            group.permissions.clear()

            for target, actions in spec.items():
                app_label, model = target.split(".", 1)
                for action in actions:
                    codename = f"{action}_{model}"
                    try:
                        perm = Permission.objects.get(
                            content_type__app_label=app_label,
                            codename=codename,
                        )
                    except Permission.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Missing permission: {app_label}.{codename}"
                            )
                        )
                        continue
                    group.permissions.add(perm)

            self.stdout.write(self.style.SUCCESS(f"Role ready: {role}"))

        self.stdout.write(self.style.SUCCESS("Roles bootstrap completed."))
