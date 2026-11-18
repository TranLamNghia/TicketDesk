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


def get_sla_due_at(ticket: Ticket):
    hours = SLA_HOURS.get(ticket.priority, SLA_HOURS[Ticket.Priority.MEDIUM])
    return ticket.created_at + timedelta(hours=hours)


def is_ticket_overdue(ticket: Ticket, current_status: str, now=None) -> bool:
    if current_status not in SLA_TRACKED_STATUSES:
        return False
    now = now or timezone.now()
    return now > get_sla_due_at(ticket)
