from celery import shared_task
from apps.tickets.services import (
    auto_close_solved_tickets,
)


@shared_task
def auto_close_solved_tickets_task() -> int:
    count = auto_close_solved_tickets()
    return count
