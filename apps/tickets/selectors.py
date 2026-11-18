from datetime import timedelta
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from apps.tickets.models import Ticket, TicketHistory


# Get lastest status ticket
def get_lastest_status_ticket():
    lastest_status_ticket = (
        TicketHistory.objects.filter(ticket=OuterRef("pk"))
        .order_by("-update_status_at")
        .values("status")[:1]
    )

    return lastest_status_ticket


# Count ticket by status
def count_ticket_by_status():
    stats = (
        Ticket.objects.annotate(current_status=Subquery(get_lastest_status_ticket()))
        .values("current_status")
        .annotate(total=Count("id"))
        .order_by("current_status")
    )

    return stats


# Count solved ticket per IT Support
def count_solved_ticket_per_IT_Support():
    SOLVED_STATUSES = [TicketHistory.Status.SOLVED, TicketHistory.Status.CLOSED]
    solved_tickets = Ticket.objects.annotate(
        current_status=Subquery(get_lastest_status_ticket())
    ).filter(current_status__in=SOLVED_STATUSES)

    stats = (
        solved_tickets.values("assignee__id", "assignee__username")
        .annotate(total_solved=Count("id"))
        .order_by("-total_solved")
    )

    return stats


# Overview KPIs
def get_overview_kpis():
    SOLVED_STATUSES = [TicketHistory.Status.SOLVED, TicketHistory.Status.CLOSED]

    tickets_status = Ticket.objects.annotate(
        current_status=Subquery(get_lastest_status_ticket())
    )

    kpis = tickets_status.aggregate(
        total_tickets=Count("id"),
        urgent_tickets=Count("id", filter=Q(priority=Ticket.Priority.URGENT)),
        unassigned_tickets=Count("id", filter=Q(assignee__isnull=True)),
        solved_tickets=Count("id", filter=Q(current_status__in=SOLVED_STATUSES)),
    )

    return kpis


SLA_HOURS = {
    Ticket.Priority.URGENT: 8,
    Ticket.Priority.HIGH: 24,
    Ticket.Priority.MEDIUM: 48,
    Ticket.Priority.LOW: 72,
}

# Statuses that count toward SLA
SLA_TRACKED_STATUSES = (TicketHistory.Status.NEW, TicketHistory.Status.PROCESSING)

# Statuses after which nothing can change anymore.
TERMINAL_STATUSES = (
    TicketHistory.Status.CLOSED,
    TicketHistory.Status.REJECTED,
    TicketHistory.Status.CANCELLED,
)

# Window during which a SOLVED ticket can be reopened / is auto-closed after.
SOLVED_WINDOW = timedelta(hours=48)


def get_current_status(ticket: Ticket) -> str:
    """Latest status of a ticket. A ticket without history is considered NEW."""
    latest = ticket.status_history.order_by("-update_status_at").first()
    return latest.status if latest else TicketHistory.Status.NEW


def get_latest_solved_at(ticket: Ticket):
    """Time of the most recent transition to SOLVED (None if never solved)."""
    latest_solved = (
        ticket.status_history.filter(status=TicketHistory.Status.SOLVED)
        .order_by("-update_status_at")
        .first()
    )
    return latest_solved.update_status_at if latest_solved else None


def is_solved_window_expired(ticket: Ticket, now=None) -> bool:
    """True when more than 48h have passed since the latest SOLVED transition."""
    solved_at = get_latest_solved_at(ticket)
    if solved_at is None:
        return False
    now = now or timezone.now()
    return now - solved_at > SOLVED_WINDOW


def get_sla_due_at(ticket: Ticket):
    hours = SLA_HOURS.get(ticket.priority, SLA_HOURS[Ticket.Priority.MEDIUM])
    return ticket.created_at + timedelta(hours=hours)


def is_ticket_overdue(ticket: Ticket, current_status: str, now=None) -> bool:
    if current_status not in SLA_TRACKED_STATUSES:
        return False
    now = now or timezone.now()
    return now > get_sla_due_at(ticket)


def tickets_with_current_status():
    return Ticket.objects.annotate(current_status=Subquery(get_lastest_status_ticket()))


def get_processing_tickets_of(support_user):
    return tickets_with_current_status().filter(
        assignee=support_user, current_status=TicketHistory.Status.PROCESSING
    )


def is_support_busy(support_user, exclude_ticket_id=None) -> bool:
    """IT Support is busy when they hold at least one PROCESSING ticket."""
    qs = get_processing_tickets_of(support_user)
    if exclude_ticket_id is not None:
        qs = qs.exclude(pk=exclude_ticket_id)
    return qs.exists()


def get_solved_tickets_to_auto_close(now=None):
    now = now or timezone.now()
    latest_status_at = (
        TicketHistory.objects.filter(ticket=OuterRef("pk"))
        .order_by("-update_status_at")
        .values("update_status_at")[:1]
    )
    return (
        tickets_with_current_status()
        .annotate(status_changed_at=Subquery(latest_status_at))
        .filter(
            current_status=TicketHistory.Status.SOLVED,
            status_changed_at__lte=now - SOLVED_WINDOW,
        )
    )


def count_tickets_created_since(user, since) -> int:
    return Ticket.objects.filter(created_by=user, created_at__gte=since).count()
