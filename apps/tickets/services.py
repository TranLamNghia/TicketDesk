from django.db import transaction
from django.core.exceptions import ValidationError

from apps.tickets.models import Ticket, TicketHistory, AssignmentHistory
from apps.users.models import User


class TicketAlreadyCloseError(ValidationError):
    pass


@transaction.atomic
def claim_ticket(ticket_id, support_user: User) -> Ticket:
    """
    IT Support claim ticket from queue (NEW -> PROCESSING).
    """
    # Lock row
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    # Check assignee
    if ticket.assignee is not None:
        raise ValidationError("Ticket has been assigned.")

    latest_history = ticket.status_history.first()
    if not latest_history or latest_history.status != TicketHistory.Status.NEW:
        raise ValidationError("Only ticket in NEW status can be accepted.")

    # Claim
    ticket.assignee = support_user
    ticket.save(update_fields=["assignee"])

    # Change ticket status: PROCESSING
    TicketHistory.objects.create(
        ticket=ticket,
        status=TicketHistory.Status.PROCESSING,
    )

    return ticket


@transaction.atomic
def reassign_ticket(ticket_id, sent_by: User, received_by: User, reason: str) -> Ticket:
    """
    Transfer the ticket to another IT Support.
    """
    if not reason.strip():
        raise ValidationError("Reason is required.")

    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.assignee is None:
        raise ValidationError(
            "Ticket has not been assigned yet. Use claim or assign instead."
        )

    if ticket.assignee == received_by:
        raise ValidationError("Cannot reassign ticket to the current assignee.")

    latest_history = ticket.status_history.first()
    terminal_statuses = [
        TicketHistory.Status.CLOSED,
        TicketHistory.Status.CANCELLED,
        TicketHistory.Status.REJECTED,
    ]
    if latest_history and latest_history.status in terminal_statuses:
        raise ValidationError(
            f"Cannot reassign a ticket that is already {latest_history.status}."
        )

    # Change assignee
    ticket.assignee = received_by
    ticket.save(update_fields=["assignee"])

    # Write history change log
    AssignmentHistory.objects.create(
        ticket=ticket,
        sent_by=sent_by,
        received_by=received_by,
        reason=reason,
    )

    return ticket


@transaction.atomic
def assign_ticket(ticket_id, support_user: User, assigned_by: User) -> Ticket:
    """
    Manager assigns a NEW ticket to an IT Support (NEW -> PROCESSING).
    """
    ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

    if ticket.assignee is not None:
        raise ValidationError("Ticket has already been assigned. Use reassign instead.")

    latest_history = ticket.status_history.first()
    if not latest_history or latest_history.status not in [TicketHistory.Status.NEW]:
        raise ValidationError("Only tickets in NEW status can be assigned.")

    ticket.assignee = support_user
    ticket.save(update_fields=["assignee"])

    TicketHistory.objects.create(
        ticket=ticket,
        status=TicketHistory.Status.PROCESSING,
    )

    AssignmentHistory.objects.create(
        ticket=ticket,
        sent_by=assigned_by,
        received_by=support_user,
        reason="Initial assignment by Manager.",
    )

    return ticket
