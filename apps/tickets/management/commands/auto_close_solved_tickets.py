from django.core.management.base import BaseCommand

from apps.tickets.services import auto_close_solved_tickets


class Command(BaseCommand):
    """
    US08 KB2: close tickets that have stayed SOLVED for more than 48 hours.

    Run periodically (ADR-005 plans Celery Beat every 15 minutes; until Celery
    is set up in week 08 it can be scheduled with cron):
        python manage.py auto_close_solved_tickets
    """

    help = "Close tickets that have been SOLVED for more than 48 hours."

    def handle(self, *args, **options):
        closed = auto_close_solved_tickets()
        self.stdout.write(self.style.SUCCESS(f"Auto-closed {closed} ticket(s)."))
