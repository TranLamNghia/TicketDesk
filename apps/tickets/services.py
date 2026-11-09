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
