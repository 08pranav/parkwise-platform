from django.core.management.base import BaseCommand

from apps.admin_api import demo


class Command(BaseCommand):
    help = "Seed the fictional demo dataset (3 Mumbai societies, one user per role, bookings in every state)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete all data first, then reseed."
        )

    def handle(self, *args, **options):
        result = demo.seed(reset=options["reset"])
        self.stdout.write(self.style.SUCCESS(str(result)))
        if result.get("seeded"):
            self.stdout.write(f"Demo password for every account: {demo.DEMO_PASSWORD}")
