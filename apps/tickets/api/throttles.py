from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import Throttled

from apps.tickets.models import Ticket
from apps.users.models import User


def _limits():
    return (
        (
            timedelta(hours=1),
            getattr(settings, "TICKET_CREATE_LIMIT_PER_HOUR", 5),
            "tickets per hour",
        ),
        (
            timedelta(days=1),
            getattr(settings, "TICKET_CREATE_LIMIT_PER_DAY", 20),
            "tickets per day",
        ),
    )


def enforce_ticket_creation_quota(user) -> None:
    """
    US06 KB4: a Requester may create at most 5 tickets per hour and
    20 tickets per day. Counted from the tickets table itself, so the limit is
    exact and does not depend on the cache backend. Raises 429 when exceeded.
    """
    if user.is_superuser or user.role != User.Role.REQUESTER:
        return

    now = timezone.now()

    for window, limit, label in _limits():
        recent = Ticket.objects.filter(
            created_by=user, created_at__gte=now - window
        ).order_by("created_at")

        if recent.count() >= limit:
            oldest = recent.values_list("created_at", flat=True).first()
            wait = max(0, int((oldest + window - now).total_seconds()))
            raise Throttled(
                wait=wait,
                detail=f"You have exceeded the limit of {limit} {label}.",
            )
